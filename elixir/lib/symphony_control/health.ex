defmodule SymphonyControl.Health do
  @moduledoc """
  Bounded, read-only liveness and PostgreSQL schema readiness.

  Readiness never creates Ecto's migration table, applies migrations or opens
  execution admission. SQL and connection errors remain inside the boundary.
  """

  alias SymphonyControl.Repo

  @timeout_ms 500
  @legacy_versions [[20_260_925_000_000]]
  @auth_versions [[20_260_925_000_000], [20_261_004_000_000]]

  # This is the required contract of CreateProjects, not a general schema audit.
  # Catalog expressions use PostgreSQL's non-pretty deparser representation.
  @projects_contract_sql """
  WITH relation AS (
    SELECT oid FROM pg_catalog.pg_class
    WHERE oid = pg_catalog.to_regclass('projects') AND relkind = 'r'
  ), expected_columns (name, type, modifier, default_expression) AS (
    VALUES
      ('id', 'uuid'::pg_catalog.regtype, -1, NULL::text),
      ('key', 'text'::pg_catalog.regtype, -1, NULL::text),
      ('name', 'text'::pg_catalog.regtype, -1, NULL::text),
      ('lock_version', 'integer'::pg_catalog.regtype, -1, '1'),
      ('inserted_at', 'timestamp'::pg_catalog.regtype, -1, NULL::text),
      ('updated_at', 'timestamp'::pg_catalog.regtype, -1, NULL::text)
  ), expected_checks (name, expression) AS (
    VALUES
      ('projects_key_not_blank', '(length(btrim(key)) > 0)'),
      ('projects_name_not_blank', '(length(btrim(name)) > 0)'),
      ('projects_lock_version_positive', '(lock_version > 0)')
  )
  SELECT EXISTS (SELECT FROM relation)
    AND NOT EXISTS (
      SELECT FROM expected_columns e
      LEFT JOIN pg_catalog.pg_attribute a
        ON a.attrelid = (SELECT oid FROM relation)
        AND a.attname = e.name AND a.attnum > 0 AND NOT a.attisdropped
      LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE a.attname IS NULL OR NOT a.attnotnull
        OR a.atttypid IS DISTINCT FROM e.type
        OR a.atttypmod IS DISTINCT FROM e.modifier
        OR a.attidentity <> '' OR a.attgenerated <> ''
        OR pg_catalog.pg_get_expr(d.adbin, d.adrelid, false) IS DISTINCT FROM e.default_expression
    )
    AND NOT EXISTS (
      SELECT FROM (VALUES ('id', true), ('key', false)) AS required_key (name, primary_key)
      WHERE NOT EXISTS (
        SELECT FROM pg_catalog.pg_index i
        JOIN pg_catalog.pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
        WHERE i.indrelid = (SELECT oid FROM relation) AND a.attname = required_key.name
          AND i.indnkeyatts = 1 AND i.indisunique AND i.indimmediate
          AND i.indisvalid AND i.indisready AND i.indislive
          AND i.indpred IS NULL AND i.indexprs IS NULL
          AND (NOT required_key.primary_key OR i.indisprimary)
      )
    )
    AND NOT EXISTS (
      SELECT FROM expected_checks e
      LEFT JOIN pg_catalog.pg_constraint c
        ON c.conrelid = (SELECT oid FROM relation) AND c.conname = e.name AND c.contype = 'c'
      WHERE c.oid IS NULL OR NOT c.convalidated
        OR pg_catalog.pg_get_expr(c.conbin, c.conrelid, false) IS DISTINCT FROM e.expression
    )
  """

  # Fixed auth migration contract: types/nullability/defaults and exact catalog constraints.
  @auth_columns [
    ["control_auth_identities", "id", "uuid", true, nil],
    ["control_auth_identities", "issuer", "text", true, nil],
    ["control_auth_identities", "subject", "text", true, nil],
    ["control_auth_identities", "user_id", "uuid", true, nil],
    ["control_auth_logout_jtis", "id", "uuid", true, nil],
    ["control_auth_logout_jtis", "issued_at_ms", "bigint", true, nil],
    ["control_auth_logout_jtis", "issuer", "text", true, nil],
    ["control_auth_logout_jtis", "jti", "text", true, nil],
    ["control_auth_logout_jtis", "retain_until_ms", "bigint", true, nil],
    ["control_auth_memberships", "id", "uuid", true, nil],
    ["control_auth_memberships", "project_id", "uuid", true, nil],
    ["control_auth_memberships", "revision", "integer", true, nil],
    ["control_auth_memberships", "revoked_at_ms", "bigint", false, nil],
    ["control_auth_memberships", "roles", "text[]", true, nil],
    ["control_auth_memberships", "user_id", "uuid", true, nil],
    ["control_auth_pending_logins", "boot_epoch", "bytea", true, nil],
    ["control_auth_pending_logins", "browser_hash", "bytea", true, nil],
    ["control_auth_pending_logins", "config_generation", "text", true, nil],
    ["control_auth_pending_logins", "consumed_at_ms", "bigint", false, nil],
    ["control_auth_pending_logins", "expires_at_ms", "bigint", true, nil],
    ["control_auth_pending_logins", "flow_ciphertext", "bytea", true, nil],
    ["control_auth_pending_logins", "id", "uuid", true, nil],
    ["control_auth_pending_logins", "issued_at_ms", "bigint", true, nil],
    ["control_auth_pending_logins", "monotonic_issued_ms", "bigint", true, nil],
    ["control_auth_pending_logins", "state_hash", "bytea", true, nil],
    ["control_auth_platform_grants", "id", "uuid", true, nil],
    ["control_auth_platform_grants", "permission", "text", true, nil],
    ["control_auth_platform_grants", "revision", "integer", true, nil],
    ["control_auth_platform_grants", "revoked_at_ms", "bigint", false, nil],
    ["control_auth_platform_grants", "user_id", "uuid", true, nil],
    ["control_auth_sessions", "boot_epoch", "bytea", true, nil],
    ["control_auth_sessions", "config_generation", "text", true, nil],
    ["control_auth_sessions", "credential_expires_at_ms", "bigint", true, nil],
    ["control_auth_sessions", "expires_at_ms", "bigint", true, nil],
    ["control_auth_sessions", "handle_hash", "bytea", true, nil],
    ["control_auth_sessions", "id", "uuid", true, nil],
    ["control_auth_sessions", "issued_at_ms", "bigint", true, nil],
    ["control_auth_sessions", "issuer", "text", true, nil],
    ["control_auth_sessions", "monotonic_issued_ms", "bigint", true, nil],
    ["control_auth_sessions", "revoked_at_ms", "bigint", false, nil],
    ["control_auth_sessions", "session_generation", "integer", true, nil],
    ["control_auth_sessions", "sid", "text", false, nil],
    ["control_auth_sessions", "subject", "text", true, nil],
    ["control_auth_sessions", "tokens_ciphertext", "bytea", true, nil],
    ["control_auth_sessions", "user_id", "uuid", true, nil],
    ["control_auth_users", "active", "boolean", true, nil],
    ["control_auth_users", "id", "uuid", true, nil]
  ]
  @auth_constraints [
    ["control_auth_identities", "control_auth_identities_issuer_check", "c", "CHECK ((length(issuer) > 0))", true, false, false],
    ["control_auth_identities", "control_auth_identities_issuer_subject_key", "u", "UNIQUE (issuer, subject)", true, false, false],
    ["control_auth_identities", "control_auth_identities_issuer_subject_user_id_key", "u", "UNIQUE (issuer, subject, user_id)", true, false, false],
    ["control_auth_identities", "control_auth_identities_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_identities", "control_auth_identities_subject_check", "c", "CHECK ((length(subject) > 0))", true, false, false],
    ["control_auth_identities", "control_auth_identities_user_id_fkey", "f", "FOREIGN KEY (user_id) REFERENCES control_auth_users(id)", true, false, false],
    ["control_auth_logout_jtis", "control_auth_logout_jtis_check", "c", "CHECK ((retain_until_ms >= (issued_at_ms + 3600000)))", true, false, false],
    ["control_auth_logout_jtis", "control_auth_logout_jtis_issuer_check", "c", "CHECK ((length(issuer) > 0))", true, false, false],
    ["control_auth_logout_jtis", "control_auth_logout_jtis_issuer_jti_key", "u", "UNIQUE (issuer, jti)", true, false, false],
    ["control_auth_logout_jtis", "control_auth_logout_jtis_jti_check", "c", "CHECK ((length(jti) > 0))", true, false, false],
    ["control_auth_logout_jtis", "control_auth_logout_jtis_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_memberships", "control_auth_memberships_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_memberships", "control_auth_memberships_project_id_fkey", "f", "FOREIGN KEY (project_id) REFERENCES projects(id)", true, false, false],
    ["control_auth_memberships", "control_auth_memberships_revision_check", "c", "CHECK ((revision > 0))", true, false, false],
    [
      "control_auth_memberships",
      "control_auth_memberships_roles_check",
      "c",
      "CHECK (((cardinality(roles) > 0) AND (array_position(roles, NULL::text) IS NULL) AND (roles <@ ARRAY['viewer'::text, 'contributor'::text, 'operator'::text, 'approver'::text, 'project_admin'::text])))",
      true,
      false,
      false
    ],
    ["control_auth_memberships", "control_auth_memberships_user_id_fkey", "f", "FOREIGN KEY (user_id) REFERENCES control_auth_users(id)", true, false, false],
    ["control_auth_memberships", "control_auth_memberships_user_id_project_id_key", "u", "UNIQUE (user_id, project_id)", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_boot_epoch_check", "c", "CHECK ((octet_length(boot_epoch) = 32))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_browser_hash_check", "c", "CHECK ((octet_length(browser_hash) = 32))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_check", "c", "CHECK ((expires_at_ms = (issued_at_ms + 300000)))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_check1", "c", "CHECK ((consumed_at_ms >= issued_at_ms))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_config_generation_check", "c", "CHECK ((length(config_generation) > 0))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_flow_ciphertext_check", "c", "CHECK ((octet_length(flow_ciphertext) >= 29))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_state_hash_check", "c", "CHECK ((octet_length(state_hash) = 32))", true, false, false],
    ["control_auth_pending_logins", "control_auth_pending_logins_state_hash_key", "u", "UNIQUE (state_hash)", true, false, false],
    ["control_auth_platform_grants", "control_auth_platform_grants_permission_check", "c", "CHECK ((permission = 'runtime_identity_read'::text))", true, false, false],
    ["control_auth_platform_grants", "control_auth_platform_grants_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_platform_grants", "control_auth_platform_grants_revision_check", "c", "CHECK ((revision > 0))", true, false, false],
    ["control_auth_platform_grants", "control_auth_platform_grants_user_id_fkey", "f", "FOREIGN KEY (user_id) REFERENCES control_auth_users(id)", true, false, false],
    ["control_auth_platform_grants", "control_auth_platform_grants_user_id_permission_key", "u", "UNIQUE (user_id, permission)", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_boot_epoch_check", "c", "CHECK ((octet_length(boot_epoch) = 32))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_check", "c", "CHECK (((expires_at_ms > issued_at_ms) AND (expires_at_ms <= (issued_at_ms + 3600000))))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_check1", "c", "CHECK ((expires_at_ms <= credential_expires_at_ms))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_check2", "c", "CHECK ((revoked_at_ms >= issued_at_ms))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_config_generation_check", "c", "CHECK ((length(config_generation) > 0))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_handle_hash_check", "c", "CHECK ((octet_length(handle_hash) = 32))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_handle_hash_key", "u", "UNIQUE (handle_hash)", true, false, false],
    [
      "control_auth_sessions",
      "control_auth_sessions_issuer_subject_user_id_fkey",
      "f",
      "FOREIGN KEY (issuer, subject, user_id) REFERENCES control_auth_identities(issuer, subject, user_id)",
      true,
      false,
      false
    ],
    ["control_auth_sessions", "control_auth_sessions_pkey", "p", "PRIMARY KEY (id)", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_session_generation_check", "c", "CHECK ((session_generation > 0))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_tokens_ciphertext_check", "c", "CHECK ((octet_length(tokens_ciphertext) >= 29))", true, false, false],
    ["control_auth_sessions", "control_auth_sessions_user_id_fkey", "f", "FOREIGN KEY (user_id) REFERENCES control_auth_users(id)", true, false, false],
    ["control_auth_users", "control_auth_users_pkey", "p", "PRIMARY KEY (id)", true, false, false]
  ]
  @auth_columns_sql """
  SELECT t.relname,a.attname,pg_catalog.format_type(a.atttypid,a.atttypmod),a.attnotnull,
    pg_catalog.pg_get_expr(d.adbin,d.adrelid,false)
  FROM pg_catalog.pg_class t JOIN pg_catalog.pg_attribute a ON a.attrelid=t.oid
    LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid=t.oid AND d.adnum=a.attnum
  WHERE t.relnamespace=pg_catalog.to_regnamespace(current_schema()) AND t.relname LIKE 'control_auth_%'
    AND t.relkind='r' AND a.attnum>0 AND NOT a.attisdropped AND a.attidentity='' AND a.attgenerated=''
  ORDER BY t.relname,a.attname
  """
  @auth_constraints_sql """
  SELECT t.relname,c.conname,c.contype::text,pg_catalog.pg_get_constraintdef(c.oid,false),
    c.convalidated,c.condeferrable,c.condeferred
  FROM pg_catalog.pg_constraint c JOIN pg_catalog.pg_class t ON c.conrelid=t.oid
  WHERE t.relnamespace=pg_catalog.to_regnamespace(current_schema()) AND t.relname LIKE 'control_auth_%'
  ORDER BY t.relname,c.conname
  """
  @auth_indexes_sql """
  SELECT NOT EXISTS (
    SELECT FROM pg_catalog.pg_constraint c JOIN pg_catalog.pg_class t ON c.conrelid=t.oid
    LEFT JOIN pg_catalog.pg_index i ON i.indexrelid=c.conindid
    WHERE t.relnamespace=pg_catalog.to_regnamespace(current_schema()) AND t.relname LIKE 'control_auth_%'
      AND c.contype IN ('p','u') AND (i.indexrelid IS NULL OR NOT i.indisunique OR NOT i.indimmediate
        OR NOT i.indisvalid OR NOT i.indisready OR NOT i.indislive OR i.indpred IS NOT NULL OR i.indexprs IS NOT NULL)
  )
  """

  @spec live?() :: boolean()
  def live? do
    SymphonyControl.Application
    |> GenServer.call(:count_children, @timeout_ms)
    |> Keyword.has_key?(:specs)
  catch
    :exit, _reason -> false
  end

  @spec readiness() :: %{ready: boolean(), database: boolean(), schema: boolean()}
  def readiness do
    database = live?() and query("SELECT 1") == {:ok, [[1]]}
    schema = database and schema_ready?()
    %{ready: schema, database: database, schema: schema}
  end

  defp schema_ready? do
    versions = query("SELECT version FROM schema_migrations ORDER BY version")
    enabled = Application.get_env(:symphony_elixir, :control_auth_enabled, false)

    supported_versions?(versions, enabled) and
      query("SELECT id, key, name, lock_version, inserted_at, updated_at FROM projects LIMIT 0") == {:ok, []} and
      query(@projects_contract_sql) == {:ok, [[true]]} and auth_contract?(versions)
  end

  defp supported_versions?({:ok, @legacy_versions}, false), do: true
  defp supported_versions?({:ok, @auth_versions}, enabled) when is_boolean(enabled), do: true
  defp supported_versions?(_versions, _enabled), do: false

  defp auth_contract?({:ok, @legacy_versions}) do
    query("""
    SELECT NOT EXISTS (SELECT FROM pg_catalog.pg_class
      WHERE relnamespace=pg_catalog.to_regnamespace(current_schema()) AND relname LIKE 'control_auth_%')
    """) == {:ok, [[true]]}
  end

  defp auth_contract?({:ok, @auth_versions}) do
    query(@auth_columns_sql) == {:ok, @auth_columns} and
      query(@auth_constraints_sql) == {:ok, @auth_constraints} and
      query(@auth_indexes_sql) == {:ok, [[true]]}
  end

  defp query(sql) do
    # A driver timeout starts after checkout; a stalled pool also needs a bound.
    task = Task.async(fn -> run_query(sql) end)

    case Task.yield(task, @timeout_ms) || Task.shutdown(task, :brutal_kill) do
      {:ok, result} -> result
      _ -> {:error, :dependency_unavailable}
    end
  end

  defp run_query(sql) do
    case Repo.query(sql, [], timeout: @timeout_ms, queue: false, log: false) do
      {:ok, result} -> {:ok, result.rows}
      {:error, _reason} -> {:error, :dependency_unavailable}
    end
  rescue
    _error -> {:error, :dependency_unavailable}
  catch
    :exit, _reason -> {:error, :dependency_unavailable}
  end
end
