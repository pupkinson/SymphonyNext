defmodule SymphonyControl.Auth.ValidityTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Actor, Clock, RequestContext, Store, Validity}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Repo}

  test "actual checked envelope binds exact actor config epoch key request and both lifetime axes" do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    request = RequestContext.deadline()
    assert {:ok, {actor, witness}} = Store.local_actor(f.config, handle, Clock.now(), request)
    assert Validity.current?(witness, f.config, actor, request)
    refute Validity.current?(witness, f.config, %{actor | subject: "foreign"}, request)
    refute Validity.current?(witness, %{f.config | generation: "foreign"}, actor, request)
    refute Validity.current?(witness, f.config, actor, request + 1)
    expired = System.monotonic_time() - 1
    refute Validity.current?(%{witness | deadline: expired}, f.config, actor, expired)
    refute Validity.current?(nil, f.config, actor, request)
    refute Validity.current?(%{}, f.config, actor, request)
    refute Validity.current?(%{witness | kind: :unknown}, f.config, actor, request)
    refute Validity.current?(%{witness | bounds: %{}}, f.config, actor, request)

    for clock <- [
          nil,
          %{},
          %{witness.clock | sample_valid: false},
          %{witness.clock | utc_ms: witness.clock.utc_ms - 1},
          %{witness.clock | monotonic_ms: witness.clock.monotonic_ms - 1},
          %{witness.clock | epoch: "foreign"},
          %{witness.clock | native_clock: self()},
          %{witness.clock | native_unit: 1},
          %{witness.clock | native_anchor: System.monotonic_time() + 1_000_000_000}
        ] do
      if clock == nil do
        refute Validity.current?(%{witness | clock: nil}, f.config, actor, request)
      else
        refute Validity.current?(witness, f.config, actor, request, clock)
      end
    end

    changed = %{witness.bounds | credential_expiry: witness.clock.utc_ms - 1}
    refute Validity.current?(%{witness | bounds: changed}, f.config, actor, request)
    changed = %{witness.bounds | expiry: witness.clock.utc_ms - 1}
    refute Validity.current?(%{witness | bounds: changed}, f.config, actor, request)
    key = File.read!(f.config.session_key_ref)
    File.write!(f.config.session_key_ref, :crypto.strong_rand_bytes(32))
    refute Validity.current?(witness, f.config, actor, request)
    File.write!(f.config.session_key_ref, key)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    assert {:ok, {material, material_witness}} = Store.session_material(f.config, actor, Clock.now(), request)
    assert material.actor == actor
    assert Validity.current?(material_witness, f.config, actor, request)
    refute Map.has_key?(Map.from_struct(actor), :tokens)
    refute inspect(witness) =~ "synthetic-access-canary"
    assert {:error, _} = Store.local_actor(f.config, handle, Clock.now(), RequestContext.deadline() - System.convert_time_unit(6000, :millisecond, :native))
    assert {:error, _} = Store.local_actor(f.config, handle, Clock.now(), "bad")
    assert {:error, _} = Store.session_material(f.config, struct(Actor), Clock.now(), request)
    assert {:error, _} = Store.permissions(f.config, actor, "bad", Clock.now(), request)
    assert {:error, _} = Store.revoke(f.config, {:session, actor.session_id}, Clock.now(), %{})
    other = %{witness | binding: %{actor | session_id: Ecto.UUID.generate()}}
    assert {:error, _} = Store.revoke(f.config, {:session, actor.session_id}, Clock.now(), other)
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[0]]
  end

  test "key witness bounds its read and treats absent short oversized references as invalid" do
    f = AuthDbFixture.start!()
    cfg = f.config
    assert is_binary(Validity.key_id(cfg))
    refute Validity.key_id(%{cfg | session_key_ref: cfg.session_key_ref <> "-missing"})
    key = File.read!(cfg.session_key_ref)

    for value <- [<<>>, <<1>>, key <> <<1>>] do
      File.write!(cfg.session_key_ref, value)
      refute Validity.key_id(cfg)
    end

    File.write!(cfg.session_key_ref, key)
  end

  @tag :continuation_wait
  test "owned condition polling retains predicate priority across a delayed deadline read" do
    owner = self()
    ref = make_ref()
    truth = :ets.new(:owned_condition, [:public, :set])
    :ets.insert(truth, {:ready, false})

    caller =
      Task.async(fn ->
        started = System.monotonic_time(:millisecond)

        condition = fn ->
          if Process.get(ref, false) do
            :ets.lookup_element(truth, :ready, 2)
          else
            Process.put(ref, true)
            sampled = :ets.lookup_element(truth, :ready, 2)
            send(owner, {:condition_sampled_false, ref, self(), started})

            receive do
              {:release_condition, ^ref} -> sampled
            after
              500 -> sampled
            end
          end
        end

        try do
          AuthDbFixture.await!(condition, 200)
        rescue
          error -> {:error, Exception.message(error)}
        end
      end)

    assert_receive {:condition_sampled_false, ^ref, waiter, started}, 1000
    :ets.insert(truth, {:ready, true})
    assert System.monotonic_time(:millisecond) - started < 200
    Process.sleep(220)
    send(waiter, {:release_condition, ref})
    assert Task.await(caller, 1000) == :ok
    assert_raise RuntimeError, "owned fixture barrier timed out", fn -> AuthDbFixture.await!(fn -> false end, 10) end
  end

  @tag :continuation_metadata
  test "local key witness does not queue behind the VM file server" do
    f = AuthDbFixture.start!()
    server = Process.whereis(:file_server_2)
    :ok = :sys.suspend(server)
    caller = Task.async(fn -> Validity.key_id(f.config) end)

    result =
      try do
        Task.yield(caller, 100)
      after
        :ok = :sys.resume(server)
      end

    if result == nil, do: Task.await(caller, 1000)
    assert match?({:ok, key} when is_binary(key), result)
  end

  test "signed witness retains actual native delivery age exact selector and original request" do
    f = AuthDbFixture.start!()
    clock = Clock.now()
    request = RequestContext.deadline()
    selector = {:subject, f.config.issuer, "known"}
    claims = %{jti: "owned-jti", issued_ms: clock.utc_ms, expires_ms: clock.utc_ms + 5000, not_before_ms: nil}
    witness = Validity.signed(claims, clock, f.config, selector, request)
    assert Validity.current?(witness, f.config, {claims.jti, selector}, request)
    refute Validity.current?(witness, f.config, {"foreign-jti", selector}, request)
    invalid = %{witness | bounds: %{claims | expires_ms: clock.utc_ms}}
    refute Validity.current?(invalid, f.config, witness.binding, request)
    invalid = %{witness | bounds: %{claims | issued_ms: clock.utc_ms - 300_001}}
    refute Validity.current?(invalid, f.config, witness.binding, request)
    invalid = %{witness | bounds: %{claims | not_before_ms: clock.utc_ms + 1}}
    refute Validity.current?(invalid, f.config, witness.binding, request)
    delayed = %{clock | native_anchor: clock.native_anchor - System.convert_time_unit(6000, :millisecond, :native)}
    refute Validity.current?(%{witness | clock: delayed}, f.config, witness.binding, request)
    assert {:error, _} = Store.accept_logout(f.config, claims.jti, selector, clock.utc_ms + 3_605_000, clock, %{})
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[0]]
  end

  test "internal read refuses exact local UTC expiry at final caller sample without releasing an envelope" do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    clock = Clock.now()
    expiry = Repo.query!("SELECT expires_at_ms FROM control_auth_sessions", [], log: false).rows |> hd() |> hd()
    AuthDbFixture.hold_clock_reply!({:stack, Store, :accept_fresh, 1, expiry + 20})
    assert {:error, :forbidden} = Store.local_actor(f.config, handle, clock, RequestContext.deadline())
  end

  @tag :key_fifo
  test "private key witness rejects a named pipe without starting an unbounded IO server wait" do
    f = AuthDbFixture.start!()
    path = f.config.session_key_ref
    backup = path <> "-owned-backup"
    File.rename!(path, backup)

    on_exit(fn ->
      File.rm(path)
      File.rename(backup, path)
    end)

    {_, 0} = System.cmd("mkfifo", [path])
    caller = Task.async(fn -> Validity.key_id(f.config) end)
    result = Task.yield(caller, 500)
    if result == nil, do: Task.shutdown(caller, :brutal_kill)
    assert result == {:ok, nil}, "FIFO must refuse before a new consumer wait"
  end
end
