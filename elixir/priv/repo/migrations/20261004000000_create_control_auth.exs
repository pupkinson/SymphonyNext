defmodule SymphonyControl.Repo.Migrations.CreateControlAuth do
  use Ecto.Migration

  @spec up() :: :ok
  def up do
    execute("""
    CREATE TABLE control_auth_users (
      id uuid PRIMARY KEY, active boolean NOT NULL
    )
    """)

    execute("""
    CREATE TABLE control_auth_identities (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES control_auth_users(id),
      issuer text NOT NULL CHECK (length(issuer) > 0),
      subject text NOT NULL CHECK (length(subject) > 0),
      UNIQUE (issuer, subject), UNIQUE (issuer, subject, user_id)
    )
    """)

    execute("""
    CREATE TABLE control_auth_sessions (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES control_auth_users(id),
      issuer text NOT NULL, subject text NOT NULL, sid text,
      handle_hash bytea NOT NULL UNIQUE CHECK (octet_length(handle_hash) = 32),
      tokens_ciphertext bytea NOT NULL CHECK (octet_length(tokens_ciphertext) >= 29),
      config_generation text NOT NULL CHECK (length(config_generation) > 0),
      session_generation integer NOT NULL CHECK (session_generation > 0),
      boot_epoch bytea NOT NULL CHECK (octet_length(boot_epoch) = 32),
      issued_at_ms bigint NOT NULL, monotonic_issued_ms bigint NOT NULL,
      expires_at_ms bigint NOT NULL CHECK (expires_at_ms > issued_at_ms AND expires_at_ms <= issued_at_ms + 3600000),
      credential_expires_at_ms bigint NOT NULL CHECK (expires_at_ms <= credential_expires_at_ms),
      revoked_at_ms bigint CHECK (revoked_at_ms >= issued_at_ms),
      FOREIGN KEY (issuer, subject, user_id) REFERENCES control_auth_identities(issuer, subject, user_id)
    )
    """)

    execute("""
    CREATE TABLE control_auth_pending_logins (
      id uuid PRIMARY KEY,
      state_hash bytea NOT NULL UNIQUE CHECK (octet_length(state_hash) = 32),
      browser_hash bytea NOT NULL CHECK (octet_length(browser_hash) = 32),
      flow_ciphertext bytea NOT NULL CHECK (octet_length(flow_ciphertext) >= 29),
      config_generation text NOT NULL CHECK (length(config_generation) > 0),
      boot_epoch bytea NOT NULL CHECK (octet_length(boot_epoch) = 32),
      issued_at_ms bigint NOT NULL, monotonic_issued_ms bigint NOT NULL,
      expires_at_ms bigint NOT NULL CHECK (expires_at_ms = issued_at_ms + 300000),
      consumed_at_ms bigint CHECK (consumed_at_ms >= issued_at_ms)
    )
    """)

    execute("""
    CREATE TABLE control_auth_memberships (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES control_auth_users(id),
      project_id uuid NOT NULL REFERENCES projects(id),
      roles text[] NOT NULL CHECK (cardinality(roles) > 0 AND array_position(roles, NULL) IS NULL
        AND roles <@ ARRAY['viewer','contributor','operator','approver','project_admin']::text[]),
      revision integer NOT NULL CHECK (revision > 0), revoked_at_ms bigint,
      UNIQUE (user_id, project_id)
    )
    """)

    execute("""
    CREATE TABLE control_auth_platform_grants (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES control_auth_users(id),
      permission text NOT NULL CHECK (permission = 'runtime_identity_read'),
      revision integer NOT NULL CHECK (revision > 0), revoked_at_ms bigint,
      UNIQUE (user_id, permission)
    )
    """)

    execute("""
    CREATE TABLE control_auth_logout_jtis (
      id uuid PRIMARY KEY,
      issuer text NOT NULL CHECK (length(issuer) > 0),
      jti text NOT NULL CHECK (length(jti) > 0),
      issued_at_ms bigint NOT NULL,
      retain_until_ms bigint NOT NULL CHECK (retain_until_ms >= issued_at_ms + 3600000),
      UNIQUE (issuer, jti)
    )
    """)

    :ok
  end

  @spec down() :: no_return()
  def down, do: raise("auth state requires a separately reviewed non-destructive recovery")
end
