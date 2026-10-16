defmodule SymphonyControl.Auth.StoreTest do
  use ExUnit.Case, async: false
  import ExUnit.CaptureLog
  alias SymphonyControl.Auth.{Actor, Store, TokenVault}
  alias SymphonyControl.{AuthDbFixture, Repo}

  setup do
    f = AuthDbFixture.start!()
    %{f: f, cfg: f.config}
  end

  test "wrong browser cannot spend flow; parallel consumption has one durable winner", %{f: f, cfg: cfg} do
    flow = AuthDbFixture.flow(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, id} = Store.put_login(cfg, "browser-A", flow, now)
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser-B", now)
    results = 1..2 |> Enum.map(fn _ -> Task.async(fn -> Store.consume_login(cfg, flow.state, "browser-A", now) end) end) |> Enum.map(&Task.await/1)
    assert Enum.count(results, &match?({:ok, %{nonce: "synthetic-nonce", verifier: "synthetic-verifier"}}, &1)) == 1
    assert Enum.count(results, &(&1 == {:error, :forbidden})) == 1
    assert %{rows: [[_]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins WHERE id=$1 AND consumed_at_ms IS NOT NULL", [AuthDbFixture.uuid(id)])
    AuthDbFixture.restart_control!(f)
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser-A", AuthDbFixture.clock(f))
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser-A", now)
  end

  test "flow300s exact boundary, generation/epoch/rollback and invalid input", %{f: f, cfg: cfg} do
    for elapsed <- [299_999, 300_000] do
      flow = AuthDbFixture.flow(f)
      now = AuthDbFixture.clock(f)
      assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
      later = %{now | utc_ms: now.utc_ms + elapsed, monotonic_ms: now.monotonic_ms + elapsed}
      AuthDbFixture.set_clock!(f, later)
      result = Store.consume_login(cfg, flow.state, "browser", later)
      if elapsed == 299_999, do: assert(match?({:ok, _}, result)), else: assert(result == {:error, :forbidden})
    end

    flow = AuthDbFixture.flow(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)

    stale = [%{now | epoch: "wrong"}, %{now | utc_ms: now.utc_ms - 1}, %{now | monotonic_ms: now.monotonic_ms - 1}]

    for {config, clock} <- [{%{cfg | generation: "changed"}, now} | Enum.map(stale, &{cfg, &1})] do
      assert {:error, :forbidden} = Store.consume_login(config, flow.state, "browser", clock)
    end

    assert {:error, :invalid_request} = Store.put_login(cfg, "browser", %{flow | issued_ms: now.utc_ms - 1}, now)
    assert {:error, :invalid_request} = Store.put_login(cfg, "browser", %{flow | verifier: <<255>>}, now)
    assert {:error, :invalid_request} = Store.put_login(nil, nil, nil, nil)
    assert {:error, :invalid_request} = Store.consume_login(nil, nil, nil, nil)
    assert {:error, :invalid_request} = Store.consume_login(cfg, String.duplicate("x", 257), "browser", now)
  end

  test "exact active local binding only; claims/email do not create accounts or rights", %{f: f, cfg: cfg} do
    user = AuthDbFixture.seed_user!(f, email: "same@example.invalid")
    now = AuthDbFixture.clock(f)

    for attrs <- [[subject: "unknown", email: "same@example.invalid", groups: ["admin"]], [issuer: cfg.issuer <> "/"], [subject: ""], [credential_expires_at_ms: now.utc_ms]] do
      assert {:error, :forbidden} = Store.open_session(cfg, AuthDbFixture.identity(f, attrs), nil, now)
    end

    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM control_auth_users", [])
    Repo.query!("UPDATE control_auth_users SET active=false WHERE id=$1", [AuthDbFixture.uuid(user)])
    assert {:error, :forbidden} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:error, :invalid_request} = Store.open_session(nil, nil, nil, nil)
  end

  test "opaque handle is hashed; Actor contains no authority; plaintext absent from DB/log", %{f: f, cfg: cfg} do
    user = AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)

    log =
      capture_log(fn ->
        assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
        assert byte_size(Base.url_decode64!(handle, padding: false)) >= 32
        assert {:ok, %Actor{local_user_id: ^user} = actor} = Store.local_actor(cfg, handle, now)
        assert Map.keys(Map.from_struct(actor)) |> Enum.sort() == Enum.sort([:session_id, :local_user_id, :issuer, :subject, :config_generation, :boot_epoch])
        assert Store.actor_current?(cfg, actor, now)
        assert {:ok, permissions} = Store.permissions(cfg, actor, :platform, now)
        assert permissions == MapSet.new()
        assert %{rows: [[hash, cipher]]} = Repo.query!("SELECT handle_hash,tokens_ciphertext FROM control_auth_sessions", [])
        assert hash == :crypto.hash(:sha256, handle)
        refute cipher == :erlang.term_to_binary(AuthDbFixture.identity(f).tokens)
        assert :binary.match(cipher, "synthetic-token") == :nomatch
      end)

    refute String.contains?(log, "synthetic-token")
  end

  test "sessions never slide; UTC/monotonic bounds, clock drift, generation, epoch, revocation", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)

    for lifetime <- [2000, 3_600_000, 7_200_000] do
      id = AuthDbFixture.identity(f, credential_expires_at_ms: now.utc_ms + lifetime)
      assert {:ok, handle} = Store.open_session(cfg, id, nil, now)
      limit = min(lifetime, 3_600_000)
      before = %{now | utc_ms: now.utc_ms + limit - 1, monotonic_ms: now.monotonic_ms + limit - 1}
      AuthDbFixture.set_clock!(f, before)
      assert {:ok, _} = Store.local_actor(cfg, handle, before)
      at = %{before | utc_ms: before.utc_ms + 1, monotonic_ms: before.monotonic_ms + 1}
      AuthDbFixture.set_clock!(f, at)
      assert {:error, :forbidden} = Store.local_actor(cfg, handle, at)
      AuthDbFixture.set_clock!(f, now)
    end

    assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, actor} = Store.local_actor(cfg, handle, now)

    for {config, clock} <- [
          {%{cfg | generation: "next"}, now},
          {cfg, %{now | epoch: "stale"}},
          {cfg, %{now | utc_ms: now.utc_ms - 1}},
          {cfg, %{now | monotonic_ms: now.monotonic_ms - 1}},
          {cfg, %{now | utc_ms: now.utc_ms + 1000, monotonic_ms: now.monotonic_ms + 2000, sample_valid: false}}
        ] do
      assert {:error, :forbidden} = Store.local_actor(config, handle, clock)
      refute Store.actor_current?(config, actor, clock)
    end

    assert :ok = Store.revoke(cfg, {:session, actor.session_id}, now)
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, now)
    AuthDbFixture.restart_control!(f)
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, AuthDbFixture.clock(f))
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, now)
    assert %{rows: [[_]]} = Repo.query!("SELECT revoked_at_ms FROM control_auth_sessions WHERE id=$1", [AuthDbFixture.uuid(actor.session_id)])
    assert {:error, :invalid_request} = Store.local_actor(nil, nil, nil)
    refute Store.actor_current?(cfg, %{}, now)
    assert {:error, :invalid_request} = Store.permissions(nil, nil, nil, nil)
  end

  test "current membership and platform grant are independent; deletion and inactive user deny", %{f: f, cfg: cfg} do
    user = AuthDbFixture.seed_user!(f)
    project = AuthDbFixture.seed_project!()
    other = AuthDbFixture.seed_project!()
    now = AuthDbFixture.clock(f)
    assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, actor} = Store.local_actor(cfg, handle, now)

    for role <- [:viewer, :contributor, :operator, :approver, :project_admin] do
      Repo.query!("DELETE FROM control_auth_memberships", [])
      AuthDbFixture.seed_membership!(f, user, project, [role])
      assert {:ok, rights} = Store.permissions(cfg, actor, project, now)
      assert MapSet.member?(rights, :project_read)
      assert {:ok, empty} = Store.permissions(cfg, actor, other, now)
      assert empty == MapSet.new()
      assert {:ok, empty} = Store.permissions(cfg, actor, :platform, now)
      assert empty == MapSet.new()
    end

    Repo.query!("UPDATE control_auth_memberships SET revoked_at_ms=$1", [now.utc_ms])
    assert {:ok, empty} = Store.permissions(cfg, actor, project, now)
    assert empty == MapSet.new()
    Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), AuthDbFixture.uuid(user)])
    assert {:ok, rights} = Store.permissions(cfg, actor, :platform, now)
    assert rights == MapSet.new([:runtime_identity_read])
    Repo.query!("DELETE FROM control_auth_platform_grants", [])
    assert {:ok, empty} = Store.permissions(cfg, actor, :platform, now)
    assert empty == MapSet.new()
    Repo.query!("UPDATE control_auth_users SET active=false", [])
    refute Store.actor_current?(cfg, actor, now)
    assert {:error, :forbidden} = Store.permissions(cfg, actor, project, now)
    assert {:error, :invalid_request} = Store.permissions(cfg, actor, "invalid-project", now)
  end

  test "rotation confirms transaction; restart old unrevoked session is denied", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, old} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, new} = Store.open_session(cfg, AuthDbFixture.identity(f), old, now)
    refute old == new
    assert {:error, :forbidden} = Store.local_actor(cfg, old, now)
    assert {:ok, _} = Store.local_actor(cfg, new, now)
    AuthDbFixture.restart_control!(f)
    assert {:error, :forbidden} = Store.local_actor(cfg, new, AuthDbFixture.clock(f))
  end

  test "logout exact issuer/jti and sid/sub intersection, replay survives restart", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    AuthDbFixture.seed_user!(f, subject: "other")
    now = AuthDbFixture.clock(f)
    assert {:ok, a} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, b} = Store.open_session(cfg, AuthDbFixture.identity(f, subject: "other"), nil, now)
    selector = {:sid, cfg.issuer, "sid-1", "known"}
    assert :ok = Store.accept_logout(cfg, "exact-jti", selector, now.utc_ms + 3_600_000, now)
    assert {:error, :forbidden} = Store.local_actor(cfg, a, now)
    assert {:ok, _} = Store.local_actor(cfg, b, now)
    assert {:error, :forbidden} = Store.accept_logout(cfg, "exact-jti", selector, now.utc_ms + 3_600_000, now)
    AuthDbFixture.restart_control!(f)
    assert {:error, :forbidden} = Store.accept_logout(cfg, "exact-jti", selector, now.utc_ms + 3_600_000, AuthDbFixture.clock(f))
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [])
    assert {:error, :invalid_request} = Store.revoke(cfg, {:subject, cfg.issuer <> "/", "known"}, now)
    assert {:error, :invalid_request} = Store.accept_logout(cfg, "jti", selector, now.utc_ms, now)
    assert {:error, :invalid_request} = Store.revoke(nil, nil, nil)
  end

  @tag capture_log: true
  test "stalled pool and transaction timeout never publish handle or plaintext", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)

    try do
      started = System.monotonic_time(:millisecond)
      assert {:error, :unknown_outcome} = Store.consume_login(cfg, flow.state, "browser", now)
      assert System.monotonic_time(:millisecond) - started < 1100
      assert {:error, :unknown_outcome} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
      assert {:error, :dependency_unavailable} = Store.local_actor(cfg, "handle", now)
    after
      :sys.resume(pool)
    end
  end

  @tag capture_log: true
  test "deferred COMMIT delay is unknown, never a handle or decrypted flow; rotation rolls back", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, old} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    Repo.query!("CREATE FUNCTION delay_commit() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN PERFORM pg_sleep(2); RETURN NEW; END'", [])
    Repo.query!("CREATE CONSTRAINT TRIGGER session_commit_delay AFTER INSERT ON control_auth_sessions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION delay_commit()", [])
    Repo.query!("CREATE CONSTRAINT TRIGGER flow_commit_delay AFTER UPDATE ON control_auth_pending_logins DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION delay_commit()", [])
    started = System.monotonic_time(:millisecond)
    assert {:error, :unknown_outcome} = Store.open_session(cfg, AuthDbFixture.identity(f), old, now)
    assert System.monotonic_time(:millisecond) - started < 1100
    started = System.monotonic_time(:millisecond)
    assert {:error, :unknown_outcome} = Store.consume_login(cfg, flow.state, "browser", now)
    assert System.monotonic_time(:millisecond) - started < 1100
    Repo.query!("DROP TRIGGER session_commit_delay ON control_auth_sessions", [], timeout: 3000)
    Repo.query!("DROP TRIGGER flow_commit_delay ON control_auth_pending_logins", [], timeout: 3000)
    assert {:ok, _} = Store.local_actor(cfg, old, now)
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM control_auth_sessions", [])
    assert %{rows: [[nil]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins", [])
  end

  test "cipher/key/config corruption refuses local candidates; consumption still durable", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, actor} = Store.local_actor(cfg, handle, now)
    assert {:error, :forbidden} = Store.permissions(cfg, %{actor | subject: "forged"}, :platform, now)
    refute Store.actor_current?(cfg, %{actor | subject: "forged"}, now)
    assert Store.actor_current?(cfg, actor, now)
    refute Store.actor_current?(cfg, %{actor | session_id: "invalid-uuid"}, now)
    Repo.query!("UPDATE control_auth_sessions SET tokens_ciphertext=set_byte(tokens_ciphertext,28,1-get_byte(tokens_ciphertext,28)%2)", [])
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, now)
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    File.write!(cfg.session_key_ref, :crypto.strong_rand_bytes(32))
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser", now)
    assert %{rows: [[_]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins", [])
    File.rm!(cfg.session_key_ref)
    assert {:error, :dependency_unavailable} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:error, :dependency_unavailable} = Store.put_login(cfg, "browser", AuthDbFixture.flow(f), now)
    assert {:error, :dependency_unavailable} = Store.local_actor(cfg, handle, now)
  end

  test "subject and sid-only selectors revoke exact bindings; malformed selectors and unavailable repo close", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, a} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert :ok = Store.revoke(cfg, {:sid, cfg.issuer, "sid-1", nil}, now)
    assert {:error, :forbidden} = Store.local_actor(cfg, a, now)
    assert {:ok, b} = Store.open_session(cfg, AuthDbFixture.identity(f, sid: nil), nil, now)
    assert :ok = Store.revoke(cfg, {:subject, cfg.issuer, "known"}, now)
    assert {:error, :forbidden} = Store.local_actor(cfg, b, now)
    assert {:error, :invalid_request} = Store.revoke(cfg, {:session, "invalid"}, now)
    assert {:error, :forbidden} = Store.open_session(cfg, AuthDbFixture.identity(f), "nonexistent-old-handle", now)
    assert {:error, :invalid_request} = Store.open_session(cfg, AuthDbFixture.identity(f), false, now)
    assert {:error, :invalid_request} = Store.put_login(cfg, "browser", %{}, now)
    ExUnit.Callbacks.stop_supervised!(SymphonyControl.Application)
    assert {:error, :dependency_unavailable} = Store.local_actor(cfg, "handle", now)
    assert {:error, :dependency_unavailable} = Store.consume_login(cfg, "state", "browser", now)
  end

  test "a damaged roles row cannot turn an unknown role into project read", %{f: f, cfg: cfg} do
    user = AuthDbFixture.seed_user!(f)
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f, user, project, [:viewer])
    now = AuthDbFixture.clock(f)
    assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, actor} = Store.local_actor(cfg, handle, now)
    Repo.query!("ALTER TABLE control_auth_memberships DROP CONSTRAINT control_auth_memberships_roles_check", [])
    Repo.query!("UPDATE control_auth_memberships SET roles=ARRAY['unknown_role']", [])
    assert {:ok, rights} = Store.permissions(cfg, actor, project, now)
    refute MapSet.member?(rights, :project_read)
  end

  test "authenticated malformed flow payload remains consumed and never escapes", %{f: f, cfg: cfg} do
    now = AuthDbFixture.clock(f)
    flow = AuthDbFixture.flow(f)
    assert {:ok, id} = Store.put_login(cfg, "browser", flow, now)
    aad = :erlang.term_to_binary({1, :flow, id, cfg.generation})
    assert {:ok, cipher} = TokenVault.seal(cfg, "{}", aad)
    Repo.query!("UPDATE control_auth_pending_logins SET flow_ciphertext=$1", [cipher])
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser", now)
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser", now)
  end

  test "a session UUID selector still cannot revoke another exact issuer", %{f: f, cfg: cfg} do
    foreign = %{cfg | issuer: cfg.issuer <> "/other"}
    AuthDbFixture.seed_user!(f, issuer: foreign.issuer)
    now = AuthDbFixture.clock(f)
    identity = AuthDbFixture.identity(f, issuer: foreign.issuer)
    assert {:ok, handle} = Store.open_session(foreign, identity, nil, now)
    assert {:ok, actor} = Store.local_actor(foreign, handle, now)
    assert :ok = Store.revoke(cfg, {:session, actor.session_id}, now)
    assert {:ok, _} = Store.local_actor(foreign, handle, now)
  end

  @tag capture_log: true
  test "pool death during checkout sanitizes the exit and never confirms consumption", %{f: f, cfg: cfg} do
    now = AuthDbFixture.clock(f)
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)
    task = Task.async(fn -> Store.consume_login(cfg, flow.state, "browser", now) end)

    try do
      assert checkout_pending?(pool, System.monotonic_time(:millisecond) + 300)
      Process.exit(pool, :kill)
      assert {:error, :unknown_outcome} = Task.await(task, 1500)
    after
      if Process.alive?(pool), do: :sys.resume(pool)
    end
  end

  defp checkout_pending?(pool, deadline) do
    {:messages, messages} = Process.info(pool, :messages)

    cond do
      Enum.any?(messages, &match?({:db_connection, _, {:checkout, _, _, _}}, &1)) ->
        true

      System.monotonic_time(:millisecond) >= deadline ->
        false

      true ->
        Process.sleep(1)
        checkout_pending?(pool, deadline)
    end
  end
end

defmodule SymphonyControl.Auth.StoreRepairTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Clock, Store, TokenVault}
  alias SymphonyControl.{AuthDbFixture, Repo}
  @moduletag :repair_regression

  setup do
    f = AuthDbFixture.start!()
    %{f: f, cfg: f.config}
  end

  test "F1 late real worker reply after yield timeout is discarded", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    shutdown_ref = AuthDbFixture.hold_task_shutdown!(f)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = traced_caller(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert task.pid == worker
    caller_pid = caller.pid
    assert_receive {:trace, ^caller_pid, :return_from, {Task, :yield, 2}, nil}, 1000
    assert_receive {:shutdown_held, ^shutdown_ref, ^caller_pid, debugger}, 500

    try do
      send(worker, {:release_query, ref})
      await_reply!(caller, task)
      send(debugger, {:continue_shutdown, shutdown_ref})
      result = Task.await(caller, 1500)
      assert result == {:error, :dependency_unavailable}
    after
      send(debugger, {:continue_shutdown, shutdown_ref})
      release_owned(caller, worker, ref)
    end
  end

  test "F1 on-time committed reply queued until after absolute deadline is discarded", %{f: f, cfg: cfg} do
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, AuthDbFixture.clock(f))
    ref = AuthDbFixture.barrier!("COMMIT")
    caller = traced_caller(fn -> Store.consume_login(cfg, flow.state, "browser", AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert task.pid == worker
    :erlang.suspend_process(caller.pid)

    try do
      send(worker, {:release_query, ref})
      await_reply!(caller, task)
      assert %{rows: [[_]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false)
      Process.sleep(820)
      :erlang.resume_process(caller.pid)
      assert {:error, :unknown_outcome} = Task.await(caller, 1500)
    after
      release_owned(caller, worker, ref)
    end
  end

  test "F1 immediate barrier release accepts real on-time results", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = Task.async(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    send(worker, {:release_query, ref})
    assert {:ok, _} = Task.await(caller, 1500)
  end

  test "F2 row lock crosses flow expiry; committed consumption releases no plaintext", %{f: f, cfg: cfg} do
    flow = AuthDbFixture.flow(f)
    assert {:ok, id} = Store.put_login(cfg, "browser", flow, AuthDbFixture.clock(f))
    AuthDbFixture.advance!(f, 299_999)
    owner = self()
    lock_ref = make_ref()

    locker =
      Task.async(fn ->
        Repo.transaction(
          fn ->
            Repo.query!("SELECT id FROM control_auth_pending_logins WHERE id=$1 FOR UPDATE", [AuthDbFixture.uuid(id)], log: false)
            send(owner, {:row_locked, lock_ref})

            receive do
              {:unlock, ^lock_ref} -> :ok
            after
              1500 -> :abandoned
            end
          end,
          timeout: 2000,
          log: false
        )
      end)

    assert_receive {:row_locked, ^lock_ref}, 1000
    caller = Task.async(fn -> Store.consume_login(cfg, flow.state, "browser", AuthDbFixture.clock(f)) end)

    try do
      AuthDbFixture.await!(
        fn ->
          Repo.query!("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND query LIKE 'UPDATE control_auth_pending_logins%'", [], log: false).rows ==
            [[1]]
        end,
        300
      )

      AuthDbFixture.advance!(f, 1)
      send(locker.pid, {:unlock, lock_ref})
      assert {:ok, :ok} = Task.await(locker, 1500)
      result = Task.await(caller, 1500)
      assert %{rows: [[_]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins WHERE id=$1 AND consumed_at_ms IS NOT NULL", [AuthDbFixture.uuid(id)], log: false)
      assert result == {:error, :forbidden}
    after
      send(locker.pid, {:unlock, lock_ref})
      Task.shutdown(locker, :brutal_kill)
      Task.shutdown(caller, :brutal_kill)
    end
  end

  for operation <- [:actor, :current, :permissions] do
    @operation operation
    test "F2 credential expires after SELECT before #{operation} publication", %{f: f, cfg: cfg} do
      {user, handle, actor} = session!(f, 50)
      project = AuthDbFixture.seed_project!()
      AuthDbFixture.seed_membership!(f, user, project, [:viewer])
      ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
      operation = @operation

      caller =
        Task.async(fn ->
          now = AuthDbFixture.clock(f)
          read_operation(operation, cfg, handle, actor, project, now)
        end)

      assert_receive {:query_result_held, ^ref, worker}, 1000
      AuthDbFixture.advance!(f, 50)
      send(worker, {:release_query, ref})
      result = Task.await(caller, 1500)
      assert_expired(operation, result)
    end
  end

  test "F2 handle is withheld when credential expires at confirmed COMMIT", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    identity = AuthDbFixture.identity(f, credential_expires_at_ms: AuthDbFixture.clock(f).utc_ms + 50)
    ref = AuthDbFixture.barrier!("COMMIT")
    caller = Task.async(fn -> Store.open_session(cfg, identity, nil, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    AuthDbFixture.advance!(f, 50)
    send(worker, {:release_query, ref})
    result = Task.await(caller, 1500)
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM control_auth_sessions", [], log: false)
    assert result == {:error, :forbidden}
  end

  test "F2 queued valid actor is checked against fresh clock at caller acceptance", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f, 50)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = traced_caller(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert task.pid == worker
    :erlang.suspend_process(caller.pid)

    try do
      send(worker, {:release_query, ref})
      await_reply!(caller, task)
      AuthDbFixture.advance!(f, 50)
      :erlang.resume_process(caller.pid)
      assert {:error, :forbidden} = Task.await(caller, 1500)
    after
      release_owned(caller, worker, ref)
    end
  end

  for scope <- [:project, :platform], change <- [:revoke, :inactive] do
    @scope scope
    @change change
    test "F3 #{scope} rights cannot combine a session with atomic #{@change} plus grant", %{f: f, cfg: cfg} do
      {user, _handle, actor} = session!(f)
      project = AuthDbFixture.seed_project!()
      scope = @scope
      target = target(scope, project)
      assert {:ok, empty} = Store.permissions(cfg, actor, target, AuthDbFixture.clock(f))
      assert empty == MapSet.new()
      ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
      caller = Task.async(fn -> Store.permissions(cfg, actor, target, AuthDbFixture.clock(f)) end)
      assert_receive {:query_result_held, ^ref, worker}, 1000

      assert {:ok, :ok} =
               Repo.transaction(
                 fn ->
                   invalidate!(@change, user, actor)
                   grant!(scope, f, user, project)
                   :ok
                 end,
                 log: false
               )

      grant_table = grant_table(scope)

      assert %{rows: [[false, true]]} =
               Repo.query!(
                 "SELECT u.active AND s.revoked_at_ms IS NULL, EXISTS(SELECT 1 FROM #{grant_table} g WHERE g.user_id=u.id) FROM control_auth_users u JOIN control_auth_sessions s ON s.user_id=u.id WHERE s.id=$1",
                 [AuthDbFixture.uuid(actor.session_id)],
                 log: false
               )

      send(worker, {:release_query, ref})
      result = Task.await(caller, 1500)
      assert result in [{:error, :forbidden}, {:ok, MapSet.new()}]
    end
  end

  test "F4 ordinary independent millisecond sampling skew is usable", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    flow = AuthDbFixture.flow(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    later = %{now | utc_ms: now.utc_ms + 100, monotonic_ms: now.monotonic_ms + 101}
    AuthDbFixture.set_clock!(f, later)
    assert {:ok, _} = Store.local_actor(cfg, handle, later)
    assert {:ok, _} = Store.consume_login(cfg, flow.state, "browser", later)
  end

  test "F4 real production Clock snapshots allow a normal round trip", %{f: f, cfg: cfg} do
    stop_supervised!(AuthDbFixture.SnapshotClock)
    start_supervised!({Clock, []})
    now = Clock.now()
    flow = %{AuthDbFixture.flow(f) | issued_ms: now.utc_ms}
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    Process.sleep(5)
    assert {:ok, _} = Store.consume_login(cfg, flow.state, "browser", Clock.now())
  end

  @tag :bc_harness
  test "F5 own stalled key resource cannot precede the operation deadline", %{f: f, cfg: cfg} do
    receipt = with_fifo_writer(cfg, [], &assert_fifo_product(f, cfg, &1))
    assert_fifo_completed(receipt)
  end

  @tag :bc_harness
  test "F5 writer350 preserves product assertions and completes within one cleanup budget", %{f: f, cfg: cfg} do
    receipt = with_fifo_writer(cfg, [hold_ms: 350], &assert_fifo_product(f, cfg, &1))
    assert_fifo_completed(receipt)
  end

  @tag :bc_harness
  test "F5 intentional nonzero writer is classified and reaped", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [exit_status: 7], fn _ -> :ok end)
    assert receipt.report["classification"] == "nonzero_exit"
    assert receipt.report["child_exit"] == 7
    assert_fifo_terminated(receipt)
  end

  @tag :bc_harness
  test "F5 helper budget cancels and reaps an over-budget real writer", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [hold_ms: 3_500], fn _ -> :ok end)
    assert receipt.report["classification"] == "budget_exceeded"
    assert receipt.report["child_exit"] != 0
    assert_fifo_terminated(receipt)
  end

  @tag :bc_harness
  test "F5 primary assertion failure survives cleanup with FIFO removed", %{cfg: cfg} do
    assert_raise ExUnit.AssertionError, "\n\nintentional primary assertion\n", fn ->
      with_fifo_writer(cfg, [], fn _ -> flunk("intentional primary assertion") end)
    end

    assert_fifo_completed(Process.get(:last_fifo_cleanup))
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 delayed supervisor800 still runs the real writer and product assertions", %{f: f, cfg: cfg} do
    receipt = with_fifo_writer(cfg, [supervisor_ready_delay_ms: 800], &assert_fifo_product(f, cfg, &1))
    assert_fifo_completed(receipt)
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 delayed supervisor2600 cannot launch after spending the original reserve", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [supervisor_ready_delay_ms: 2_600, writer_required: false], fn _ -> :ok end)
    assert_fifo_no_child(receipt, "readiness_deadline")
    refute Enum.any?(receipt.events, &(&1.message["event"] == "supervisor_ready"))
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 ready supervisor with insufficient reserve confirms no child", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [supervisor_ready_delay_ms: 2_250, writer_required: false], fn _ -> :ok end)
    assert_fifo_no_child(receipt, "insufficient_reserve")
    assert Enum.any?(receipt.events, &(&1.message["event"] == "supervisor_ready"))
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 launch delivery delay consumes the fixed Python endpoint", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [launch_delay_ms: 2_200, writer_required: false], fn _ -> :ok end)
    assert_fifo_no_child(receipt, "insufficient_reserve")
    launch = Enum.find(receipt.events, &(&1.message["event"] == "launch_received"))
    assert launch.message["command"] == "launch"
    sent = Enum.find(receipt.commands, &(&1.command.event == "launch"))
    assert sent.result == true
    assert sent.command.end_ns == receipt.helper.python_deadline
    ready = Enum.find(receipt.events, &(&1.message["event"] == "supervisor_ready"))
    assert launch.message["at_ns"] - ready.message["at_ns"] >= 2_200_000_000
    assert launch.message["end_ns"] == receipt.helper.python_deadline
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 absent supervisor readiness terminates without fabricated writer receipts", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [suppress_ready: true, writer_required: false], fn _ -> :ok end)
    assert_fifo_no_child(receipt, "readiness_absent")
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 launched writer without readiness is cancelled and actually reaped", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [writer_ready_delay_ms: 3_500, writer_required: false], fn _ -> :ok end)
    assert receipt.ready == nil
    assert receipt.report["classification"] == "budget_exceeded"
    assert receipt.report["child_exit"] != 0
    assert_fifo_terminated(receipt)
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 supervisor readiness scheduled beyond endpoint is bounded before child launch", %{cfg: cfg} do
    receipt = with_fifo_writer(cfg, [supervisor_ready_delay_ms: 3_500, writer_required: false], fn _ -> :ok end)
    assert_fifo_no_child(receipt, "readiness_deadline")
    refute Enum.any?(receipt.events, &(&1.message["event"] == "supervisor_ready"))
  end

  @tag :bc_harness
  @tag :c_deadline
  test "F5 lost Port remains nonqualified and cannot hide the primary assertion", %{cfg: cfg} do
    assert_raise ExUnit.AssertionError, "\n\nprimary assertion after Port loss\n", fn ->
      with_fifo_writer(cfg, [hold_ms: 3_500], fn path ->
        state = Process.get({:fifo_helper, path})
        assert Port.close(state.helper.port)
        flunk("primary assertion after Port loss")
      end)
    end

    receipt = Process.get(:last_fifo_cleanup)
    refute receipt.qualified
    assert receipt.classification == :terminal_unknown
    assert receipt.report == nil
    assert receipt.port_exit == nil
    assert receipt.down == :normal
    assert receipt.removal == {:returned, {:ok, {:error, :enoent}}}
    refute File.exists?(receipt.helper.path)
    # Lost terminal transport cannot prove the child's actual wait/reap. This
    # expected UNKNOWN is never counted as a normally completed writer/helper.
  end

  defp assert_fifo_product(f, cfg, path) do
    start = System.monotonic_time(:millisecond)
    result = Store.put_login(%{cfg | session_key_ref: path}, "browser", AuthDbFixture.flow(f), AuthDbFixture.clock(f))
    elapsed = System.monotonic_time(:millisecond) - start
    assert result in [{:error, :dependency_unavailable}, {:error, :unknown_outcome}]
    assert elapsed < 800
    assert {:error, :dependency_unavailable} = TokenVault.seal(%{cfg | session_key_ref: path}, "synthetic-fifo-canary", "AAD")
    assert {:error, :dependency_unavailable} = TokenVault.open(%{cfg | session_key_ref: path}, "invalid", "AAD")
  end

  defp with_fifo_writer(cfg, opts, assertion) do
    path = cfg.session_key_ref <> "-fifo"
    assert {_, 0} = System.cmd("mkfifo", ["-m", "600", path])
    key = {:fifo_helper, path}

    outcome =
      fifo_capture(fn ->
        try do
          fifo_start(key, path, cfg, opts)
          primary = fifo_capture(fn -> fifo_assertion(key, opts, assertion) end)
          cleanup = fifo_capture(fn -> fifo_wait(key, :done) end)
          {primary, cleanup}
        after
          fifo_finalize(key, path)
        end
      end)

    receipt = Process.get(:last_fifo_cleanup)
    IO.puts("FIFO bounded cleanup " <> inspect(fifo_safe_receipt(receipt), limit: :infinity))
    fifo_result(outcome, receipt)
  end

  defp fifo_start(key, path, cfg, opts) do
    args = ["-u", "-c", fifo_supervisor_script(), path, cfg.session_key_ref, Jason.encode!(Map.new(opts))]
    started = System.monotonic_time(:nanosecond)
    port = Port.open({:spawn_executable, System.find_executable("python3")}, [:binary, :exit_status, {:line, 4096}, args: args])
    monitor = :erlang.monitor(:port, port)

    helper = %{
      port: port,
      monitor: monitor,
      started: started,
      deadline: started + 3_000_000_000,
      python_deadline: nil,
      path: path,
      supervisor: nil
    }

    state = %{helper: helper, ready: nil, child: nil, report: nil, port_exit: nil, down: nil, events: [], commands: []}
    Process.put(key, state)
    {:os_pid, supervisor} = Port.info(port, :os_pid)
    Process.put(key, put_in(state.helper.supervisor, supervisor))
  end

  defp fifo_assertion(key, opts, assertion) do
    state = fifo_wait(key, :ready)
    if Keyword.get(opts, :writer_required, true), do: assert(is_map(state.ready), "writer startup not confirmed")
    assert fifo_remaining(state.helper) > 0, "helper deadline expired before assertion dispatch"
    assertion.(state.helper.path)
  end

  # Cleanup errors remain values until the primary exception and its original
  # stack have been selected. Finalization itself cannot replace that exception.
  defp fifo_result({:returned, {{:failed, kind, reason, stack}, _}}, _receipt), do: :erlang.raise(kind, reason, stack)
  defp fifo_result({:returned, {_, {:failed, kind, reason, stack}}}, _receipt), do: :erlang.raise(kind, reason, stack)
  defp fifo_result({:failed, kind, reason, stack}, _receipt), do: :erlang.raise(kind, reason, stack)
  defp fifo_result({:returned, _}, receipt), do: receipt

  defp fifo_capture(fun) do
    {:returned, fun.()}
  catch
    kind, reason -> {:failed, kind, reason, __STACKTRACE__}
  end

  defp fifo_finalize(key, path) do
    state = Process.delete(key)

    close =
      try do
        fifo_capture(fn -> fifo_close(state) end)
      after
        # This owned path is removed even when Port cleanup raises. File.rm and
        # the absence check precede the final elapsed sample, including failures.
        Process.put({key, :removal}, fifo_capture(fn -> {File.rm(path), File.lstat(path)} end))
      end

    removal = Process.delete({key, :removal})
    finished = System.monotonic_time(:nanosecond)
    receipt = fifo_receipt(state, close, removal, finished)
    Process.put(:last_fifo_cleanup, receipt)
  end

  defp fifo_close(nil), do: :not_started

  defp fifo_close(state) do
    port = state.helper.port

    try do
      # Port.close is containment only. It supplies neither child wait/reap nor
      # the missing supervisor exit status; such a receipt is nonqualified.
      if Port.info(port), do: Port.close(port), else: :already_closed
    after
      Process.demonitor(state.helper.monitor, [:flush])
    end
  end

  defp fifo_receipt(nil, close, removal, finished) do
    %{classification: :launch_unknown, close: close, removal: removal, finished: finished, qualified: false}
  end

  defp fifo_receipt(state, close, removal, finished) do
    elapsed = div(finished - state.helper.started + 999_999, 1_000_000)
    terminal = fifo_terminal_known?(state)
    removed = removal == {:returned, {:ok, {:error, :enoent}}}
    qualified = terminal and removed and close == {:returned, :already_closed} and elapsed <= 3_000

    classification = if state.report, do: state.report["classification"], else: :terminal_unknown
    Map.merge(state, %{elapsed_ms: elapsed, finished: finished, close: close, removal: removal, qualified: qualified, classification: classification})
  end

  defp fifo_terminal_known?(%{report: nil}), do: false

  defp fifo_terminal_known?(state) do
    state.port_exit == 0 and state.down == :normal and
      state.report["end_ns"] == state.helper.python_deadline and
      state.report["at_ns"] <= state.helper.python_deadline and fifo_child_known?(state)
  end

  defp fifo_child_known?(%{report: %{"child_launched" => false}} = state) do
    state.child == nil and state.ready == nil and state.report["child_exit"] == nil and
      state.report["child_reaped"] == false
  end

  defp fifo_child_known?(state) do
    state.report["child_reaped"] == true and is_integer(state.report["wait_return_ns"]) and
      state.report["wait_return_ns"] <= state.helper.python_deadline
  end

  defp fifo_wait(key, phase) do
    state = Process.get(key)

    cond do
      phase == :ready and is_map(state.ready) ->
        state

      not is_nil(state.down) and not is_nil(state.port_exit) ->
        state

      fifo_remaining(state.helper) == 0 ->
        state

      true ->
        fifo_receive(key, state)
        fifo_wait(key, phase)
    end
  end

  defp fifo_remaining(helper) do
    max(div(helper.deadline - System.monotonic_time(:nanosecond), 1_000_000), 0)
  end

  defp fifo_receive(key, state) do
    %{port: port, monitor: monitor} = state.helper

    receive do
      {^port, {:data, {:eol, line}}} ->
        message = Jason.decode!(line)
        received = System.monotonic_time(:nanosecond)
        event = %{message: message, received: received}
        state = %{state | events: state.events ++ [event]}
        Process.put(key, fifo_event(state, message, received))

      {^port, {:exit_status, status}} ->
        Process.put(key, %{state | port_exit: status})

      {:DOWN, ^monitor, :port, ^port, reason} ->
        Process.put(key, %{state | down: reason})
    after
      fifo_remaining(state.helper) -> :ok
    end
  end

  defp fifo_event(state, %{"event" => "supervisor_started", "at_ns" => anchor}, received) do
    # The anchor was emitted BEFORE owner receipt R. In Python's scale,
    # anchor + (D-R-200ms) is no later than D-200ms. Monotonic origins need not
    # agree; only elapsed nanoseconds are transferred. Delivery consumes this
    # fixed endpoint, never adds a duration at receipt. The reserve is inside D.
    endpoint = anchor + max(state.helper.deadline - received - 200_000_000, 0)
    state = put_in(state.helper.python_deadline, endpoint)
    command = fifo_command(state.helper, %{event: "deadline", end_ns: endpoint})
    %{state | commands: state.commands ++ [command]}
  end

  defp fifo_event(state, %{"event" => "supervisor_ready"}, _received) do
    event = if fifo_remaining(state.helper) >= 1_000, do: "launch", else: "cancel"
    command = fifo_command(state.helper, %{event: event, end_ns: state.helper.python_deadline})
    %{state | commands: state.commands ++ [command]}
  end

  defp fifo_event(state, %{"event" => "writer_started"} = message, _), do: %{state | child: message}
  defp fifo_event(state, %{"event" => "writer_ready"} = message, _), do: %{state | ready: message}
  defp fifo_event(state, %{"event" => "supervisor_terminal"} = message, _), do: %{state | report: message}
  defp fifo_event(state, _message, _received), do: state

  defp fifo_command(helper, command) do
    # Fresh check after every receive and immediately before external dispatch.
    payload = Jason.encode!(command) <> "\n"
    sent = System.monotonic_time(:nanosecond)
    result = if sent < helper.deadline, do: Port.command(helper.port, payload), else: :deadline_expired
    %{command: command, sent: sent, result: result}
  end

  defp assert_fifo_completed(receipt) do
    assert receipt.report["classification"] == "completed"
    assert receipt.report["child_exit"] == 0
    assert is_map(receipt.ready)
    assert_fifo_terminated(receipt)
  end

  defp assert_fifo_terminated(receipt) do
    assert_fifo_terminal(receipt)
    assert receipt.report["child_launched"] == true
    assert receipt.report["child_reaped"] == true
    assert receipt.report["wait_return_ns"] <= receipt.helper.python_deadline
    refute fifo_pid_current?(receipt.child["pid"], receipt.child["start_ticks"])
  end

  defp assert_fifo_no_child(receipt, classification) do
    assert_fifo_terminal(receipt)
    assert receipt.report["classification"] == classification
    assert receipt.report["child_launched"] == false
    assert receipt.report["child_reaped"] == false
    assert receipt.report["child_exit"] == nil
    assert receipt.child == nil
    assert receipt.ready == nil
  end

  defp assert_fifo_terminal(receipt) do
    assert receipt.qualified
    assert receipt.elapsed_ms <= 3_000
    assert receipt.report["at_ns"] <= receipt.helper.python_deadline
    assert receipt.report["end_ns"] == receipt.helper.python_deadline
    assert receipt.port_exit == 0
    assert receipt.down == :normal
    assert Port.info(receipt.helper.port) == nil
    refute File.exists?(receipt.helper.path)
    refute File.exists?("/proc/#{receipt.helper.supervisor}")
  end

  defp fifo_pid_current?(pid, ticks) do
    case File.read("/proc/#{pid}/stat") do
      {:ok, stat} ->
        fields = stat |> String.split(") ", parts: 2) |> List.last() |> String.split()
        actual = Enum.at(fields, 19)
        assert is_binary(actual) and actual != "", "owned process identity UNKNOWN"
        actual == ticks

      {:error, :enoent} ->
        false
    end
  end

  defp fifo_safe_receipt(%{helper: _} = receipt) do
    Map.take(receipt, [:events, :commands, :ready, :child, :report, :port_exit, :down, :elapsed_ms, :finished, :removal, :qualified, :classification])
    |> Map.put(:bounds, Map.take(receipt.helper, [:started, :deadline, :python_deadline]))
  end

  defp fifo_safe_receipt(receipt), do: receipt

  defp fifo_supervisor_script do
    ~S"""
    import errno,json,os,pathlib,select,subprocess,sys,time
    opts=json.loads(sys.argv[3])
    def emit(event,**data):
        try: print(json.dumps(dict(data,event=event,at_ns=time.monotonic_ns())),flush=True)
        except BrokenPipeError: pass
    def remaining(end,reserve=0):
        return max((end-time.monotonic_ns())/1e9-reserve,0)
    def command(end):
        left=remaining(end)
        if not left: return {'event':'budget_exceeded'}
        readable,_,_=select.select([sys.stdin],[],[],left)
        if not readable: return {'event':'budget_exceeded'}
        line=sys.stdin.readline()
        return json.loads(line) if line else {'event':'owner_lost'}
    def gate(delay_ms,end):
        target=time.monotonic_ns()+delay_ms*1_000_000
        while time.monotonic_ns()<target:
            left=remaining(min(target,end-350_000_000))
            if not left: return 'budget_exceeded'
            readable,_,_=select.select([sys.stdin],[],[],left)
            if readable:
                return 'owner_lost' if not sys.stdin.readline() else 'cancelled'
        return None
    def delivery_gate(delay_ms,end):
        target=time.monotonic_ns()+delay_ms*1_000_000
        while time.monotonic_ns()<target:
            left=remaining(min(target,end-350_000_000))
            if not left: return 'launch_deadline'
            select.select([],[],[],left)
        return None
    def no_child(classification,end):
        emit('supervisor_terminal',classification=classification,end_ns=end,
             child_launched=False,child_exit=None,child_reaped=False)
    # No child is possible before a fixed, owner-derived endpoint arrives.
    emit('supervisor_started')
    initial=command(time.monotonic_ns()+500_000_000)
    if initial.get('event')!='deadline':
        no_child('deadline_unconfirmed',None);sys.exit(0)
    end=initial['end_ns']
    emit('deadline_received',end_ns=end)
    delay=3_500 if opts.get('suppress_ready') else opts.get('supervisor_ready_delay_ms',0)
    stopped=gate(delay,end)
    if not stopped and not remaining(end,0.35): stopped='budget_exceeded'
    if stopped:
        classification='readiness_absent' if opts.get('suppress_ready') else 'readiness_deadline'
        no_child(stopped if stopped!='budget_exceeded' else classification,end);sys.exit(0)
    emit('supervisor_ready',end_ns=end)
    stopped=delivery_gate(opts.get('launch_delay_ms',0),end)
    if stopped:
        no_child(stopped,end);sys.exit(0)
    launch=command(end-350_000_000)
    emit('launch_received',command=launch['event'],end_ns=end)
    if launch.get('event')!='launch' or launch.get('end_ns')!=end:
        no_child('insufficient_reserve' if launch['event']=='cancel' else launch['event'],end);sys.exit(0)
    if remaining(end)<0.8:
        no_child('insufficient_reserve',end);sys.exit(0)
    writer='''import errno,json,os,pathlib,sys,time
    opts=json.loads(sys.argv[3])
    time.sleep(opts.get('writer_ready_delay_ms',0)/1000)
    ticks=pathlib.Path('/proc/self/stat').read_text().rsplit(') ',1)[1].split()[19]
    print(json.dumps({'event':'writer_ready','pid':os.getpid(),'start_ticks':ticks}),flush=True)
    time.sleep(opts.get('hold_ms',0)/1000)
    time.sleep(0.85)
    end=time.monotonic()+0.4
    while time.monotonic()<end:
        try:
            fd=os.open(sys.argv[1],os.O_WRONLY|os.O_NONBLOCK)
            try: os.write(fd,pathlib.Path(sys.argv[2]).read_bytes())
            finally: os.close(fd)
            break
        except OSError as e:
            if e.errno!=errno.ENXIO: raise
            time.sleep(0.005)
    sys.exit(opts.get('exit_status',0))
    '''
    child=subprocess.Popen([sys.executable,'-u','-c',writer,*sys.argv[1:]],stdout=subprocess.PIPE,text=True)
    ticks=pathlib.Path(f'/proc/{child.pid}/stat').read_text().rsplit(') ',1)[1].split()[19]
    emit('writer_started',pid=child.pid,start_ticks=ticks,end_ns=end)
    classification=None
    ready=False
    status=None
    waited=None
    try:
        while child.poll() is None:
            left=remaining(end,0.4)
            if not left:
                classification='budget_exceeded';break
            readers=[sys.stdin]+([] if ready else [child.stdout])
            readable,_,_=select.select(readers,[],[],min(0.02,left))
            if child.stdout in readable:
                line=child.stdout.readline()
                if line:
                    message=json.loads(line)
                    if message.pop('event')!='writer_ready': raise RuntimeError('protocol')
                    emit('writer_ready',**message);ready=True
            if sys.stdin in readable:
                classification='owner_lost' if not sys.stdin.readline() else 'cancelled';break
    finally:
        try:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=min(0.15,remaining(end,0.15)))
                except subprocess.TimeoutExpired:
                    if remaining(end,0.1): child.kill()
            # An actual wait return is separate from Port close/process absence.
            status=child.wait(timeout=remaining(end,0.1))
            waited=time.monotonic_ns()
            emit('writer_reaped',child_exit=status,wait_return_ns=waited,end_ns=end)
        except subprocess.TimeoutExpired:
            classification='reap_unknown'
        finally:
            child.stdout.close()
    classification=classification or ('completed' if status==0 and ready else 'nonzero_exit')
    emit('supervisor_terminal',classification=classification,end_ns=end,
         child_launched=True,child_exit=status,child_reaped=waited is not None,wait_return_ns=waited)
    sys.exit(0 if waited is not None else 73)
    """
  end

  test "F2 independent session limit expires while credentials remain valid", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f, 7_200_000)
    AuthDbFixture.advance!(f, 3_599_999)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = Task.async(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    AuthDbFixture.advance!(f, 1)
    send(worker, {:release_query, ref})
    assert {:error, :forbidden} = Task.await(caller, 1500)
    assert %{rows: [[true]]} = Repo.query!("SELECT credential_expires_at_ms>expires_at_ms FROM control_auth_sessions", [], log: false)
  end

  test "F4 unsupported uncertain absent and suspended fresh clock all deny", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    now = AuthDbFixture.clock(f)
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, Map.delete(now, :sample_valid))
    AuthDbFixture.set_clock!(f, %{now | sample_valid: false})
    assert {:error, :forbidden} = Store.local_actor(cfg, handle, now)
    AuthDbFixture.set_clock!(f, now)
    :ok = :sys.suspend(Clock)

    try do
      assert {:error, :dependency_unavailable} = Store.local_actor(cfg, handle, now)
    after
      :sys.resume(Clock)
    end

    assert {:ok, _} = Store.local_actor(cfg, handle, now)
    stop_supervised!(AuthDbFixture.SnapshotClock)
    assert {:error, :dependency_unavailable} = Store.local_actor(cfg, handle, now)
  end

  test "F1 caller checks deadline after its last real clock reply", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = traced_caller(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert worker == task.pid
    clock_ref = AuthDbFixture.hold_clock_reply!(caller.pid)
    send(worker, {:release_query, ref})
    assert_receive {:clock_reply_held, ^clock_ref, {caller_pid, tag}, clock_pid}, 1000
    assert caller_pid == caller.pid
    refute Process.alive?(worker)
    :erlang.suspend_process(caller.pid)

    try do
      Process.sleep(820)
      send(clock_pid, {:release_clock, clock_ref})

      AuthDbFixture.await!(fn ->
        {:messages, messages} = Process.info(caller.pid, :messages)
        Enum.any?(messages, &match?({reply_tag, _} when reply_tag == tag, &1))
      end)

      :erlang.resume_process(caller.pid)
      assert {:error, :dependency_unavailable} = Task.await(caller, 1500)
    after
      send(clock_pid, {:release_clock, clock_ref})
      release_owned(caller, worker, ref)
    end
  end

  @tag capture_log: true
  test "F1 next SQL inherits exhausted budget and cannot insert a session", %{f: f, cfg: cfg} do
    AuthDbFixture.seed_user!(f)
    ref = AuthDbFixture.barrier!("SELECT u.id FROM control_auth_identities")
    caller = traced_caller(fn -> Store.open_session(cfg, AuthDbFixture.identity(f), nil, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert worker == task.pid
    :erlang.suspend_process(caller.pid)

    try do
      Process.sleep(820)
      send(worker, {:release_query, ref})
      await_reply!(caller, task)
      :erlang.resume_process(caller.pid)
      assert {:error, :unknown_outcome} = Task.await(caller, 1500)
      assert %{rows: [[0]]} = Repo.query!("SELECT count(*) FROM control_auth_sessions", [], log: false)
    after
      release_owned(caller, worker, ref)
    end
  end

  test "F2 clock loss after confirmed consumption releases no plaintext", %{f: f, cfg: cfg} do
    flow = AuthDbFixture.flow(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, AuthDbFixture.clock(f))
    ref = AuthDbFixture.barrier!("COMMIT")
    caller = Task.async(fn -> Store.consume_login(cfg, flow.state, "browser", AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    stop_supervised!(AuthDbFixture.SnapshotClock)
    send(worker, {:release_query, ref})
    assert {:error, :dependency_unavailable} = Task.await(caller, 1500)
    assert %{rows: [[_]]} = Repo.query!("SELECT consumed_at_ms FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false)
  end

  for failure <- [:absent, :uncertain] do
    @failure failure
    test "F2 queued committed revoke checks #{@failure} clock at caller", %{f: f, cfg: cfg} do
      {_user, _handle, actor} = session!(f)
      ref = AuthDbFixture.barrier!("COMMIT")
      caller = traced_caller(fn -> Store.revoke(cfg, {:session, actor.session_id}, AuthDbFixture.clock(f)) end)
      assert_receive {:query_result_held, ^ref, worker}, 1000
      task = yield_task(caller)
      assert worker == task.pid
      :erlang.suspend_process(caller.pid)

      try do
        send(worker, {:release_query, ref})
        await_reply!(caller, task)
        fail_clock!(@failure, f)
        :erlang.resume_process(caller.pid)
        assert Task.await(caller, 1500) == clock_error(@failure)
        assert %{rows: [[_]]} = Repo.query!("SELECT revoked_at_ms FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false)
      after
        release_owned(caller, worker, ref)
      end
    end
  end

  test "F2 queued actor is withheld if fresh clock disappears", %{f: f, cfg: cfg} do
    {_user, handle, _actor} = session!(f)
    ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
    caller = traced_caller(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
    assert_receive {:query_result_held, ^ref, worker}, 1000
    task = yield_task(caller)
    assert worker == task.pid
    :erlang.suspend_process(caller.pid)

    try do
      send(worker, {:release_query, ref})
      await_reply!(caller, task)
      stop_supervised!(AuthDbFixture.SnapshotClock)
      :erlang.resume_process(caller.pid)
      assert {:error, :dependency_unavailable} = Task.await(caller, 1500)
    after
      release_owned(caller, worker, ref)
    end
  end

  for {family, basis} <-
        [{:flow, :flow}, {:open, :credential}] ++
          for(family <- [:actor, :current, :project, :platform], basis <- [:credential, :session], do: {family, basis}),
      delivery <- [:send, :queue],
      timing <- [:expired, :timely] do
    @family family
    @basis basis
    @delivery delivery
    @timing timing
    @tag :f2_last_sample
    test "F2 last measured sample #{@family}/#{@basis} #{@delivery} #{@timing}", %{f: f, cfg: cfg} do
      family = @family
      {operation, needle, expiry} = last_sample_operation(f, cfg, family, @basis)
      {base, origin} = AuthDbFixture.ticking_clock!(f)
      expires_native = origin + System.convert_time_unit(expiry - base.utc_ms, :millisecond, :native)
      query_ref = AuthDbFixture.barrier!(needle)
      started = System.monotonic_time()
      caller = traced_caller(operation)
      assert_receive {:query_result_held, ^query_ref, worker}, 500
      task = yield_task(caller)
      assert task.pid == worker
      clock_ref = AuthDbFixture.hold_clock_reply!(caller.pid)
      send(worker, {:release_query, query_ref})
      assert_receive {:clock_sample_measured, ^clock_ref, {caller_pid, tag}, clock_pid, sample, measured}, 500
      assert caller_pid == caller.pid
      refute Process.alive?(worker)
      assert sample.sample_valid
      assert sample.utc_ms < expiry
      assert measured < expires_native, "fixture failure: final sample already expired"
      assert %{rows: [[^expiry]]} = last_sample_readback(family)
      :erlang.trace(clock_pid, true, [:send, {:tracer, self()}])

      try do
        if @delivery == :queue do
          :erlang.suspend_process(caller.pid)
          send(clock_pid, {:release_clock, clock_ref})

          AuthDbFixture.await!(
            fn ->
              {:messages, messages} = Process.info(caller.pid, :messages)
              Enum.any?(messages, &(&1 == {tag, sample}))
            end,
            100
          )
        end

        if @timing == :expired do
          AuthDbFixture.await!(
            fn ->
              System.monotonic_time() >= expires_native + System.convert_time_unit(20, :millisecond, :native)
            end,
            400
          )
        end

        send(clock_pid, {:release_clock, clock_ref})
        if @delivery == :queue, do: :erlang.resume_process(caller.pid)
        result = Task.await(caller, 1000)
        finished = System.monotonic_time()
        assert_receive {:trace, ^clock_pid, :send, {^tag, ^sample}, _destination}, 100
        elapsed = System.convert_time_unit(finished - started, :native, :microsecond) / 1000
        assert elapsed < 750, "fixture failure: F2 control exceeded the overall750ms deadline"

        IO.puts(
          Jason.encode!(%{
            control: "F2_last_sample",
            family: family,
            basis: @basis,
            delivery: @delivery,
            timing: @timing,
            expected: if(@timing == :expired, do: "lifetime_refusal", else: "success"),
            actual: result_kind(result),
            elapsed_ms: elapsed,
            measurement_ms: System.convert_time_unit(measured - origin, :native, :microsecond) / 1000,
            remaining_ms_at_sample: expiry - sample.utc_ms,
            order: ["SQL/COMMIT", "worker_check", "caller_Clock_measurement", "same_reply", "caller_decision"]
          })
        )

        if @timing == :expired do
          assert finished >= expires_native
          assert_last_sample_expired(family, result)
        else
          assert_timely(family, result)
        end

        # This is real committed readback, not a rollback inference from refusal.
        assert %{rows: [[^expiry]]} = last_sample_readback(family)
        assert_flow_retry(family, cfg, f)
      after
        :erlang.trace(clock_pid, false, [:send])
        send(clock_pid, {:release_clock, clock_ref})
        release_owned(caller, worker, query_ref)
      end
    end
  end

  for fault <- [:missing, :future, :domain, :units] do
    @fault fault
    @tag :f2_last_sample
    test "F2 invalid native anchor #{@fault} denies the final caller decision", %{f: f, cfg: cfg} do
      {_user, handle, _actor} = session!(f)
      ref = AuthDbFixture.barrier!("FROM control_auth_sessions s")
      caller = traced_caller(fn -> Store.local_actor(cfg, handle, AuthDbFixture.clock(f)) end)
      assert_receive {:query_result_held, ^ref, worker}, 500
      task = yield_task(caller)
      assert task.pid == worker
      patch = native_sample_fault(@fault)
      :ok = AuthDbFixture.patch_clock_sample!(patch)
      send(worker, {:release_query, ref})
      assert {:error, :forbidden} = Task.await(caller, 1000)
    end
  end

  defp last_sample_operation(f, cfg, :flow, :flow) do
    flow = AuthDbFixture.flow(f)
    now = AuthDbFixture.clock(f)
    assert {:ok, _} = Store.put_login(cfg, "browser", flow, now)
    Process.put(:last_sample_flow, flow)
    AuthDbFixture.advance!(f, 299_800)
    {fn -> Store.consume_login(cfg, flow.state, "browser", AuthDbFixture.clock(f)) end, "COMMIT", now.utc_ms + 300_000}
  end

  defp last_sample_operation(f, cfg, :open, :credential) do
    AuthDbFixture.seed_user!(f)
    expiry = AuthDbFixture.clock(f).utc_ms + 200
    identity = AuthDbFixture.identity(f, credential_expires_at_ms: expiry)
    {fn -> Store.open_session(cfg, identity, nil, AuthDbFixture.clock(f)) end, "COMMIT", expiry}
  end

  defp last_sample_operation(f, cfg, family, basis) do
    lifetime = if basis == :credential, do: 200, else: 7_200_000
    {user, handle, actor} = session!(f, lifetime)
    project = AuthDbFixture.seed_project!()
    grant!(:project, f, user, project)
    grant!(:platform, f, user, project)
    expiry = AuthDbFixture.clock(f).utc_ms + min(lifetime, 3_600_000)
    if basis == :session, do: AuthDbFixture.advance!(f, 3_599_800)

    operation = fn ->
      now = AuthDbFixture.clock(f)

      case family do
        :actor -> Store.local_actor(cfg, handle, now)
        :current -> Store.actor_current?(cfg, actor, now)
        :project -> Store.permissions(cfg, actor, project, now)
        :platform -> Store.permissions(cfg, actor, :platform, now)
      end
    end

    {operation, "FROM control_auth_sessions s", expiry}
  end

  defp last_sample_readback(:flow), do: Repo.query!("SELECT expires_at_ms FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false)
  defp last_sample_readback(_family), do: Repo.query!("SELECT expires_at_ms FROM control_auth_sessions WHERE revoked_at_ms IS NULL", [], log: false)
  defp result_kind({:ok, _}), do: "success"
  defp result_kind(true), do: "success"
  defp result_kind(false), do: "false"
  defp result_kind({:error, reason}), do: Atom.to_string(reason)
  defp assert_timely(:current, result), do: assert(result == true)
  defp assert_timely(:flow, result), do: assert(match?({:ok, %{nonce: "synthetic-nonce", verifier: "synthetic-verifier"}}, result))
  defp assert_timely(:open, result), do: assert(match?({:ok, handle} when is_binary(handle), result))
  defp assert_timely(:actor, result), do: assert(match?({:ok, %SymphonyControl.Auth.Actor{}}, result))
  defp assert_timely(:project, result), do: assert(result == {:ok, MapSet.new([:project_read])})
  defp assert_timely(:platform, result), do: assert(result == {:ok, MapSet.new([:runtime_identity_read])})
  defp native_sample_fault(:missing), do: %{native_anchor: nil}
  defp native_sample_fault(:future), do: %{native_anchor: System.monotonic_time() + System.convert_time_unit(60, :second, :native)}
  defp native_sample_fault(:domain), do: %{native_clock: self()}
  defp native_sample_fault(:units), do: %{native_unit: :millisecond}
  defp assert_last_sample_expired(:current, result), do: refute(result)
  defp assert_last_sample_expired(_family, result), do: assert(result == {:error, :forbidden})

  defp assert_flow_retry(:flow, cfg, f) do
    flow = Process.get(:last_sample_flow)
    assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser", AuthDbFixture.clock(f))
  end

  defp assert_flow_retry(_family, _cfg, _f), do: :ok

  defp session!(f, lifetime \\ 3_600_000) do
    user = AuthDbFixture.seed_user!(f)
    now = AuthDbFixture.clock(f)
    identity = AuthDbFixture.identity(f, credential_expires_at_ms: now.utc_ms + lifetime)
    {:ok, handle} = Store.open_session(f.config, identity, nil, now)
    {:ok, actor} = Store.local_actor(f.config, handle, now)
    {user, handle, actor}
  end

  defp read_operation(:actor, cfg, handle, _actor, _project, now), do: Store.local_actor(cfg, handle, now)
  defp read_operation(:current, cfg, _handle, actor, _project, now), do: Store.actor_current?(cfg, actor, now)
  defp read_operation(:permissions, cfg, _handle, actor, project, now), do: Store.permissions(cfg, actor, project, now)
  defp assert_expired(:current, result), do: refute(result)
  defp assert_expired(_operation, result), do: assert(result == {:error, :forbidden})
  defp target(:platform, _project), do: :platform
  defp target(:project, project), do: project
  defp grant_table(:platform), do: "control_auth_platform_grants"
  defp grant_table(:project), do: "control_auth_memberships"
  defp fail_clock!(:absent, _f), do: stop_supervised!(AuthDbFixture.SnapshotClock)
  defp fail_clock!(:uncertain, f), do: AuthDbFixture.set_clock!(f, %{AuthDbFixture.clock(f) | sample_valid: false})
  defp clock_error(:absent), do: {:error, :dependency_unavailable}
  defp clock_error(:uncertain), do: {:error, :forbidden}
  defp invalidate!(:revoke, _user, actor), do: Repo.query!("UPDATE control_auth_sessions SET revoked_at_ms=issued_at_ms WHERE id=$1", [AuthDbFixture.uuid(actor.session_id)], log: false)
  defp invalidate!(:inactive, user, _actor), do: Repo.query!("UPDATE control_auth_users SET active=false WHERE id=$1", [AuthDbFixture.uuid(user)], log: false)

  defp grant!(:platform, _f, user, _project),
    do: Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), AuthDbFixture.uuid(user)], log: false)

  defp grant!(:project, f, user, project), do: AuthDbFixture.seed_membership!(f, user, project, [:viewer])

  defp traced_caller(operation) do
    :erlang.trace_pattern({Task, :yield, 2}, [{:_, [], [{:return_trace}]}], [:local])

    caller =
      Task.async(fn ->
        receive do
          :run -> operation.()
        end
      end)

    :erlang.trace(caller.pid, true, [:call, {:tracer, self()}])
    on_exit(fn -> :erlang.trace_pattern({Task, :yield, 2}, false, [:local]) end)
    send(caller.pid, :run)
    caller
  end

  defp yield_task(caller) do
    pid = caller.pid
    assert_receive {:trace, ^pid, :call, {Task, :yield, [%Task{} = task, _timeout]}}, 1000
    task
  end

  defp await_reply!(caller, task) do
    AuthDbFixture.await!(fn ->
      case Process.info(caller.pid, :messages) do
        {:messages, messages} -> Enum.any?(messages, &match?({ref, _} when ref == task.ref, &1))
        _ -> false
      end
    end)

    refute Process.alive?(task.pid)
  end

  defp release_owned(caller, worker, ref) do
    send(worker, {:release_query, ref})

    if Process.alive?(caller.pid) do
      try do
        :erlang.resume_process(caller.pid)
      rescue
        ArgumentError -> :ok
      end

      Task.shutdown(caller, :brutal_kill)
    end

    if Process.alive?(worker), do: Process.exit(worker, :kill)
  end
end
