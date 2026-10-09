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
      assert {:ok, _} = Store.local_actor(cfg, handle, before)
      at = %{before | utc_ms: before.utc_ms + 1, monotonic_ms: before.monotonic_ms + 1}
      assert {:error, :forbidden} = Store.local_actor(cfg, handle, at)
    end

    assert {:ok, handle} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, actor} = Store.local_actor(cfg, handle, now)

    for {config, clock} <- [
          {%{cfg | generation: "next"}, now},
          {cfg, %{now | epoch: "stale"}},
          {cfg, %{now | utc_ms: now.utc_ms - 1}},
          {cfg, %{now | monotonic_ms: now.monotonic_ms - 1}},
          {cfg, %{now | utc_ms: now.utc_ms + 1000, monotonic_ms: now.monotonic_ms + 2000}}
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
