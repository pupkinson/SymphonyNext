defmodule SymphonyControl.Auth.SchemaTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.Store
  alias SymphonyControl.{AuthDbFixture, Health, Repo}

  test "enabled auth refuses the previously supported legacy-only schema" do
    f = AuthDbFixture.start!(migrate: false)
    AuthDbFixture.migrate_legacy!(f)
    assert Health.readiness().ready
    Application.put_env(:symphony_elixir, :control_auth_enabled, true)
    on_exit(fn -> Application.delete_env(:symphony_elixir, :control_auth_enabled) end)
    refute Health.readiness().ready
  end

  test "both migrations repeat and preserve existing project rows" do
    f = AuthDbFixture.start!(migrate: false)
    AuthDbFixture.migrate_legacy!(f)
    project = AuthDbFixture.seed_project!()
    assert AuthDbFixture.migrate!(f) == [20_261_004_000_000]
    assert AuthDbFixture.migrate!(f) == []
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM projects WHERE id=$1", [AuthDbFixture.uuid(project)])
    assert Health.readiness().ready
    Application.put_env(:symphony_elixir, :control_auth_enabled, true)
    on_exit(fn -> Application.delete_env(:symphony_elixir, :control_auth_enabled) end)
    assert Health.readiness().ready
  end

  test "direct SQL enforces every required NOT NULL, primary key, foreign key, unique and check" do
    f = AuthDbFixture.start!()
    user = AuthDbFixture.seed_user!(f)
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f, user, project, [:viewer])
    cfg = f.config
    now = AuthDbFixture.clock(f)
    assert {:ok, _} = Store.open_session(cfg, AuthDbFixture.identity(f), nil, now)
    assert {:ok, _} = Store.put_login(cfg, "browser", AuthDbFixture.flow(f), now)
    Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), AuthDbFixture.uuid(user)])
    Repo.query!("INSERT INTO control_auth_logout_jtis(id,issuer,jti,issued_at_ms,retain_until_ms) VALUES($1,$2,'jti',0,3600000)", [Ecto.UUID.bingenerate(), cfg.issuer])

    %{rows: columns} =
      Repo.query!("""
      SELECT t.relname,a.attname FROM pg_class t JOIN pg_attribute a ON a.attrelid=t.oid
      WHERE t.relnamespace=current_schema()::regnamespace AND t.relname LIKE 'control_auth_%'
        AND a.attnum>0 AND NOT a.attisdropped AND a.attnotnull ORDER BY t.relname,a.attname
      """)

    assert length(columns) == 42

    for [table, col] <- columns do
      assert_violation("UPDATE #{table} SET #{col}=NULL", :not_null_violation)
    end

    for table <- ~w(users identities sessions pending_logins memberships platform_grants logout_jtis) do
      assert_violation("INSERT INTO control_auth_#{table} SELECT * FROM control_auth_#{table}", :unique_violation)
    end

    for {table, col} <- [{"identities", "user_id"}, {"sessions", "user_id"}, {"memberships", "user_id"}, {"memberships", "project_id"}, {"platform_grants", "user_id"}] do
      assert_violation("UPDATE control_auth_#{table} SET #{col}='00000000-0000-4000-8000-999999999999'", :foreign_key_violation)
    end

    assert_violation("UPDATE control_auth_sessions SET subject='foreign-subject'", :foreign_key_violation)

    for {table, col, expression} <- [
          {"identities", "issuer", "''"},
          {"identities", "subject", "''"},
          {"sessions", "handle_hash", "'short'::bytea"},
          {"sessions", "tokens_ciphertext", "''::bytea"},
          {"sessions", "config_generation", "''"},
          {"sessions", "session_generation", "0"},
          {"sessions", "boot_epoch", "''::bytea"},
          {"sessions", "expires_at_ms", "issued_at_ms"},
          {"sessions", "expires_at_ms", "issued_at_ms+3600001"},
          {"sessions", "credential_expires_at_ms", "expires_at_ms-1"},
          {"sessions", "revoked_at_ms", "issued_at_ms-1"},
          {"pending_logins", "state_hash", "''::bytea"},
          {"pending_logins", "browser_hash", "''::bytea"},
          {"pending_logins", "flow_ciphertext", "''::bytea"},
          {"pending_logins", "config_generation", "''"},
          {"pending_logins", "boot_epoch", "''::bytea"},
          {"pending_logins", "expires_at_ms", "issued_at_ms+299999"},
          {"pending_logins", "consumed_at_ms", "issued_at_ms-1"},
          {"memberships", "roles", "ARRAY['idp_admin']"},
          {"memberships", "roles", "ARRAY[]::text[]"},
          {"memberships", "roles", "ARRAY[NULL]::text[]"},
          {"memberships", "revision", "0"},
          {"platform_grants", "permission", "'platform_admin'"},
          {"platform_grants", "revision", "0"},
          {"logout_jtis", "issuer", "''"},
          {"logout_jtis", "jti", "''"},
          {"logout_jtis", "retain_until_ms", "issued_at_ms+3599999"}
        ] do
      assert_violation("UPDATE control_auth_#{table} SET #{col}=#{expression}", :check_violation)
    end

    for {table, columns} <- [
          {"identities", "user_id,issuer,subject"},
          {"sessions", "user_id,issuer,subject,handle_hash,tokens_ciphertext,config_generation,session_generation,boot_epoch,issued_at_ms,monotonic_issued_ms,expires_at_ms,credential_expires_at_ms"},
          {"pending_logins", "state_hash,browser_hash,flow_ciphertext,config_generation,boot_epoch,issued_at_ms,monotonic_issued_ms,expires_at_ms"},
          {"memberships", "user_id,project_id,roles,revision"},
          {"platform_grants", "user_id,permission,revision"},
          {"logout_jtis", "issuer,jti,issued_at_ms,retain_until_ms"}
        ] do
      assert_violation("INSERT INTO control_auth_#{table}(id,#{columns}) SELECT '00000000-0000-4000-8000-111111111111',#{columns} FROM control_auth_#{table}", :unique_violation)
    end

    assert Health.readiness().ready
  end

  for {table, constraint} <- [
        {"identities", "user_id_fkey"},
        {"identities", "issuer_subject_key"},
        {"identities", "issuer_check"},
        {"sessions", "issuer_subject_user_id_fkey"},
        {"sessions", "handle_hash_key"},
        {"sessions", "check"},
        {"memberships", "project_id_fkey"},
        {"memberships", "user_id_project_id_key"},
        {"memberships", "roles_check"},
        {"platform_grants", "user_id_permission_key"},
        {"platform_grants", "permission_check"},
        {"pending_logins", "state_hash_key"},
        {"pending_logins", "check"},
        {"logout_jtis", "issuer_jti_key"},
        {"logout_jtis", "check"}
      ] do
    test "missing auth constraint blocks readiness: #{table}/#{constraint}" do
      AuthDbFixture.start!()
      assert Health.readiness().ready
      Repo.query!("ALTER TABLE control_auth_#{unquote(table)} DROP CONSTRAINT control_auth_#{unquote(table)}_#{unquote(constraint)}", [])
      refute Health.readiness().ready
    end
  end

  test "weakened/unvalidated checks, nullable columns and foreign versions block readiness" do
    AuthDbFixture.start!()
    assert Health.readiness().ready

    for sql <- [
          "ALTER TABLE control_auth_memberships DROP CONSTRAINT control_auth_memberships_roles_check",
          "ALTER TABLE control_auth_memberships ADD CONSTRAINT control_auth_memberships_roles_check CHECK(true)",
          "ALTER TABLE control_auth_users ALTER COLUMN active DROP NOT NULL",
          "DELETE FROM schema_migrations WHERE version=20261004000000",
          "INSERT INTO schema_migrations(version,inserted_at) VALUES(99999999999999,now())"
        ] do
      Repo.query!(sql, [])
      refute Health.readiness().ready
    end
  end

  defp assert_violation(sql, code) do
    assert {:error, %Postgrex.Error{postgres: %{code: ^code}}} = Repo.query(sql, [], log: false)
  end
end
