defmodule SymphonyControl.Auth.EligibilityTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Access, Clock, Eligibility, OidcFixture, Store}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture}

  defp fixture do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Access.authenticate(f.config, handle, Clock.now())
    {f, login, handle, actor}
  end

  test "queued fresh-clock reply cannot publish an observation after its measured remaining lifetime" do
    {f, _login, _handle, actor} = fixture()
    receipt = :sys.get_state(Eligibility).cache |> Map.values() |> hd()
    AuthDbFixture.set_clock!(f.db, receipt.clock)
    AuthDbFixture.advance!(f.db, 49_999)
    deadline = System.monotonic_time(:millisecond) + 2000
    caller = Task.async(fn -> receive do: (:go -> Eligibility.current?(receipt, f.config, actor, deadline)) end)
    ref = AuthDbFixture.hold_clock_reply!(caller.pid)
    send(caller.pid, :go)
    assert_receive {:clock_reply_held, ^ref, _from, producer}, 1000
    assert_receive {:clock_sample_measured, ^ref, _from, ^producer, sample, _measured}, 1000
    assert sample.monotonic_ms - receipt.clock.monotonic_ms == 49_999
    Process.sleep(20)
    send(producer, {:release_clock, ref})
    refute Task.await(caller, 1000)
  end

  test "singleflight joins concurrent actual requests and retains no token material in cache" do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    owner = self()
    ref = make_ref()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligibility_barrier, {owner, ref})})
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    callers = for _ <- 1..2, do: Task.async(fn -> Access.authenticate(f.config, handle, Clock.now()) end)
    assert_receive {:eligibility_accepted, ^ref, provider}, 2000
    AuthDbFixture.await!(fn -> :sys.get_state(Eligibility).inflight |> Map.values() |> Enum.any?(&(length(&1.waiters) == 2)) end)
    send(provider, {ref, :release})
    assert Enum.all?(Enum.map(callers, &Task.await(&1, 3000)), &match?({:ok, _}, &1))
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    state = :sys.get_state(Eligibility)
    assert state.inflight == %{}
    assert map_size(state.cache) == 1
    refute :erlang.term_to_binary(state.cache) =~ "synthetic-access-canary"
    refute :erlang.term_to_binary(state.cache) =~ "synthetic-client-secret-canary"
  end

  test "different local sessions never share an observation even with the same IdP sid" do
    {f, _login, first, _actor} = fixture()
    second_login = AuthHttpFixture.login!(f)
    [_, second] = String.split(second_login.cookie, "=", parts: 2)
    assert {:ok, _} = Access.authenticate(f.config, first, Clock.now())
    assert {:ok, _} = Access.authenticate(f.config, second, Clock.now())
    assert OidcFixture.calls(f.provider, :eligibility) == 2
    assert map_size(:sys.get_state(Eligibility).cache) == 2
  end

  test "unproved live evidence and malformed adapter outputs fail closed" do
    {f, _login, handle, actor} = fixture()
    assert :ok = Eligibility.invalidate(f.config, {:session, actor.session_id}, deadline())
    original = :sys.get_state(Eligibility).observer

    for observer <- [
          fn _, _, _ -> :ok end,
          fn _, _, _ -> {:ok, %{}} end,
          fn _, _, _ -> raise "owned observer failure" end,
          fn _, _, _ -> throw(:owned_failure) end,
          fn _, _, _ -> exit(:owned_failure) end
        ] do
      :sys.replace_state(Eligibility, &%{&1 | observer: observer})
      assert {:error, _} = Access.authenticate(f.config, handle, Clock.now())
      assert :sys.get_state(Eligibility).cache == %{}
    end

    :sys.replace_state(Eligibility, &%{&1 | observer: original})
    assert {:ok, _} = Access.authenticate(f.config, handle, Clock.now())
    cfg = %{f.config | live_evidence: true, eligible_mechanism: "userinfo"}
    :sys.replace_state(Eligibility, &%{&1 | observer: nil, config: cfg, cache: %{}})
    assert {:ok, _} = Store.local_actor(cfg, handle, Clock.now())
    assert {:error, :forbidden} = Eligibility.confirm(cfg, actor, Clock.now(), deadline())
  end

  test "key replacement and clock rollback close fresh cached access" do
    {f, _login, handle, _actor} = fixture()
    key = File.read!(f.config.session_key_ref)
    File.write!(f.config.session_key_ref, :crypto.strong_rand_bytes(32))
    assert {:error, _} = Access.authenticate(f.config, handle, Clock.now())
    File.write!(f.config.session_key_ref, key)
    assert {:ok, _} = Access.authenticate(f.config, handle, Clock.now())
    now = Clock.now()
    AuthDbFixture.set_clock!(f.db, %{now | utc_ms: now.utc_ms - 20_000})
    assert {:error, _} = Access.authenticate(f.config, handle, Clock.now())
  end

  test "a different observed provider version cannot confirm the configured binding" do
    {f, _login, handle, actor} = fixture()
    assert :ok = Eligibility.invalidate(f.config, {:session, actor.session_id}, deadline())
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :observation_patch, %{"version" => "foreign-version"})})
    assert {:error, :forbidden} = Access.authenticate(f.config, handle, Clock.now())
    assert :sys.get_state(Eligibility).cache == %{}
  end

  test "a refresh result queued beyond its original deadline cannot republish success" do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    owner = self()
    ref = make_ref()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligibility_barrier, {owner, ref})})
    deadline = System.monotonic_time() + System.convert_time_unit(2000, :millisecond, :native)
    request = Task.async(fn -> Access.authenticate(f.config, handle, Clock.now(), deadline) end)
    assert_receive {:eligibility_accepted, ^ref, provider}, 1500
    :ok = :sys.suspend(Eligibility)
    on_exit(fn -> if Process.whereis(Eligibility), do: :sys.resume(Eligibility) end)
    send(provider, {ref, :release})
    assert {:error, _} = Task.await(request, 2500)
    Process.sleep(1200)
    :ok = :sys.resume(Eligibility)
    AuthDbFixture.await!(fn -> :sys.get_state(Eligibility).inflight == %{} end)
    assert :sys.get_state(Eligibility).cache == %{}
  end

  test "receipt binding invalid selectors missing dependencies and worker loss remain closed" do
    {f, _login, handle, actor} = fixture()
    entry = :sys.get_state(Eligibility).cache |> Map.values() |> hd()
    refute Eligibility.current?(nil, f.config, actor, deadline())
    refute Eligibility.current?(entry, %{f.config | generation: "foreign"}, actor, deadline())
    refute Eligibility.current?(entry, f.config, actor, "bad deadline")
    refute Eligibility.current?(%{entry | clock: nil}, f.config, actor, deadline())
    assert {:error, :forbidden} = Eligibility.confirm(f.config, actor, Clock.now(), "bad deadline")
    assert {:error, :forbidden} = Eligibility.invalidate(f.config, :invalid, deadline())
    foreign = %{f.config | generation: "foreign"}
    assert {:error, :forbidden} = Eligibility.invalidate(foreign, {:session, actor.session_id}, deadline())
    assert :ok = Eligibility.invalidate(f.config, {:sid, f.config.issuer, "foreign", nil}, deadline())
    assert map_size(:sys.get_state(Eligibility).cache) == 1
    assert :ok = Eligibility.invalidate(f.config, {:sid, f.config.issuer, "session-1", nil}, deadline())
    assert :sys.get_state(Eligibility).cache == %{}
    original = :sys.get_state(Eligibility).observer
    :sys.replace_state(Eligibility, &%{&1 | observer: fn _, _, _ -> {:ok, :malformed} end})
    assert {:error, :forbidden} = Eligibility.confirm(f.config, actor, Clock.now(), deadline())
    :sys.replace_state(Eligibility, &%{&1 | observer: original})
    owner = self()
    ref = make_ref()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligibility_barrier, {owner, ref})})
    request = Task.async(fn -> Access.authenticate(f.config, handle, Clock.now()) end)
    assert_receive {:eligibility_accepted, ^ref, provider}, 1500
    job = :sys.get_state(Eligibility).inflight |> Map.values() |> hd()
    Process.exit(job.pid, :kill)
    assert {:error, _} = Task.await(request, 2000)
    send(provider, {ref, :release})
    send(Eligibility, {:DOWN, make_ref(), :process, self(), :normal})
    ignored = {:observed, entry.key, make_ref(), {:error, :forbidden}}
    send(Eligibility, ignored)
    assert :sys.get_state(Eligibility).inflight == %{}
    stop_supervised!(Eligibility)
    selector = {:session, actor.session_id}
    assert {:error, :dependency_unavailable} = Eligibility.invalidate(f.config, selector, deadline())

    starter =
      Task.async(fn ->
        Process.flag(:trap_exit, true)
        Eligibility.start_link(config: f.config, observer: original)
      end)

    assert {:error, :invalid_auth_options} = Task.await(starter)
    stop_supervised!(SymphonyControl.Application)
    assert {:error, :dependency_unavailable} = Eligibility.confirm(f.config, actor, Clock.now(), deadline())
  end

  test "a measured observation outside the native freshness window is never cached" do
    {f, _login, handle, actor} = fixture()
    assert :ok = Eligibility.invalidate(f.config, {:session, actor.session_id}, deadline())
    anchor = System.monotonic_time() - System.convert_time_unit(60_000, :millisecond, :native)
    AuthDbFixture.patch_clock_sample!(%{native_anchor: anchor})
    assert {:error, _} = Access.authenticate(f.config, handle, Clock.now())
    assert :sys.get_state(Eligibility).cache == %{}
  end

  test "malformed receipts and dependency loss cannot disclose a queued success" do
    {f, _login, _handle, actor} = fixture()
    entry = :sys.get_state(Eligibility).cache |> Map.values() |> hd()
    malformed = Map.delete(entry, :until_native)
    refute Eligibility.current?(malformed, f.config, actor, deadline())
    stop_supervised!(SymphonyControl.AuthDbFixture.SnapshotClock)
    refute Eligibility.current?(entry, f.config, actor, deadline())
  end

  test "an on-time cache acceptance queued at its caller cannot exceed the original deadline" do
    {f, _login, _handle, actor} = fixture()
    entry = :sys.get_state(Eligibility).cache |> Map.values() |> hd()
    owner = self()
    deadline = System.monotonic_time(:millisecond) + 300
    caller = Task.async(fn -> receive do: (:go -> Eligibility.current?(entry, f.config, actor, deadline)) end)
    target = caller.pid

    debug = fn state, event, _extra ->
      case event do
        {:out, :ok, {^target, _tag}, _server_state} ->
          :erlang.suspend_process(target)
          send(owner, {:cache_acceptance_measured, System.monotonic_time(:millisecond)})

        {:out, :ok, {^owner, _tag}, _server_state} ->
          :erlang.resume_process(target)

        _ ->
          :ok
      end

      state
    end

    :ok = :sys.install(Eligibility, {debug, :owned})
    send(target, :go)
    assert_receive {:cache_acceptance_measured, measured}, 1000
    assert measured < deadline
    Process.sleep(350)
    assert :ok = GenServer.call(Eligibility, {:accept, f.config, entry.key, entry.ref})
    refute Task.await(caller, 1000)
    :ok = :sys.remove(Eligibility, debug)
    assert {:error, :forbidden} = Eligibility.confirm(f.config, actor, Clock.now(), 1_000_000_000_000_000_000_000)
  end

  test "a hung observer is bounded and capacity exhaustion never becomes eligibility" do
    {f, _login, handle, actor} = fixture()
    assert :ok = Eligibility.invalidate(f.config, {:session, actor.session_id}, deadline())
    owner = self()

    observer = fn _, _, _ ->
      send(owner, {:hung_observer, self()})
      receive do: (:never -> {:error, :forbidden})
    end

    :sys.replace_state(Eligibility, &%{&1 | observer: observer})
    request = Task.async(fn -> Eligibility.confirm(f.config, actor, Clock.now(), System.monotonic_time(:millisecond) + 900) end)
    assert_receive {:hung_observer, worker}, 1000
    assert {:error, _} = Task.await(request, 1500)
    AuthDbFixture.await!(fn -> not Process.alive?(worker) and :sys.get_state(Eligibility).inflight == %{} end)
    request = Task.async(fn -> Access.authenticate(f.config, handle, Clock.now()) end)
    assert_receive {:hung_observer, worker}, 1000
    state = :sys.get_state(Eligibility)
    {key, job} = Enum.at(state.inflight, 0)
    :sys.replace_state(Eligibility, &%{&1 | inflight: Map.put(&1.inflight, key, %{job | waiters: List.duplicate(hd(job.waiters), 32)})})
    assert {:error, _} = Eligibility.confirm(f.config, actor, Clock.now(), deadline())
    assert :ok = Eligibility.invalidate(f.config, {:session, actor.session_id}, deadline())
    assert {:error, _} = Task.await(request, 2000)
    refute Process.alive?(worker)
  end

  defp deadline, do: System.monotonic_time(:millisecond) + 2000
end
