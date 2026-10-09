defmodule SymphonyControl.AuthDbFixture do
  @moduledoc false
  alias SymphonyControl.Auth.Config
  alias SymphonyControl.Repo
  alias SymphonyControl.Repo.Migrations.{CreateControlAuth, CreateProjects}

  def start!(opts \\ []) do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    schema = "sn005_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

    repo = [
      socket_dir: System.fetch_env!("SN005_TEST_PG_SOCKET"),
      port: String.to_integer(System.fetch_env!("SN005_TEST_PG_PORT")),
      username: System.fetch_env!("SN005_TEST_PG_USER"),
      database: System.fetch_env!("SN005_TEST_PG_DB"),
      pool_size: 4,
      parameters: [search_path: schema],
      log: false
    ]

    ExUnit.Callbacks.start_supervised!({SymphonyControl.Application, enabled: true, repo: repo})
    Repo.query!("CREATE SCHEMA #{schema}", [], log: false)
    key = Path.join(System.fetch_env!("SN005_TEST_KEY_ROOT"), schema)
    File.write!(key, :crypto.strong_rand_bytes(32))
    File.chmod!(key, 0o600)
    ExUnit.Callbacks.on_exit(fn -> File.rm(key) end)
    cfg = %Config{issuer: "https://fixture.example.invalid/issuer", generation: "generation-1", session_key_ref: key}
    initial_clock = %{utc_ms: 1_800_000_000_000, monotonic_ms: 1000, epoch: :crypto.strong_rand_bytes(32)}
    {:ok, agent} = Agent.start_link(fn -> initial_clock end)
    f = %{config: cfg, schema: schema, repo: repo, clock_agent: agent}
    if Keyword.get(opts, :migrate, true), do: migrate!(f)
    f
  end

  def migrate!(f) do
    paths = Application.app_dir(:symphony_elixir, "priv/repo/migrations")
    modules = [{20_260_925_000_000, CreateProjects}, {20_261_004_000_000, CreateControlAuth}]

    for {_version, module} <- modules do
      file = migration_file(module)
      Code.require_file(Path.join(paths, file))
    end

    Ecto.Migrator.run(Repo, modules, :up, all: true, prefix: f.schema, log: false)
  end

  def migrate_legacy!(f) do
    paths = Application.app_dir(:symphony_elixir, "priv/repo/migrations")
    Code.require_file(Path.join(paths, migration_file(CreateProjects)))
    Ecto.Migrator.run(Repo, [{20_260_925_000_000, CreateProjects}], :up, all: true, prefix: f.schema, log: false)
  end

  defp migration_file(CreateProjects), do: "20260925000000_create_projects.exs"
  defp migration_file(CreateControlAuth), do: "20261004000000_create_control_auth.exs"

  def clock(f), do: Agent.get(f.clock_agent, & &1)
  def advance!(f, ms), do: Agent.update(f.clock_agent, &%{&1 | utc_ms: &1.utc_ms + ms, monotonic_ms: &1.monotonic_ms + ms})

  def restart_control!(f) do
    ExUnit.Callbacks.stop_supervised!(SymphonyControl.Application)
    ExUnit.Callbacks.start_supervised!({SymphonyControl.Application, enabled: true, repo: f.repo})
    Repo.query!("SELECT 1", [], timeout: 1_000, log: false)
    Agent.update(f.clock_agent, &%{&1 | epoch: :crypto.strong_rand_bytes(32), monotonic_ms: 0})
  end

  def seed_user!(f, opts \\ []) do
    id = Ecto.UUID.generate()
    Repo.query!("INSERT INTO control_auth_users(id,active) VALUES($1,$2)", [uuid(id), Keyword.get(opts, :active, true)], log: false)

    Repo.query!(
      "INSERT INTO control_auth_identities(id,user_id,issuer,subject) VALUES($1,$2,$3,$4)",
      [Ecto.UUID.bingenerate(), uuid(id), Keyword.get(opts, :issuer, f.config.issuer), Keyword.get(opts, :subject, "known")],
      log: false
    )

    id
  end

  def seed_project! do
    id = Ecto.UUID.generate()

    Repo.query!(
      "INSERT INTO projects(id,key,name,inserted_at,updated_at) VALUES($1,$2,'Fixture',now(),now())",
      [uuid(id), id],
      log: false
    )

    id
  end

  def seed_membership!(_f, user, project, roles) do
    Repo.query!(
      "INSERT INTO control_auth_memberships(id,user_id,project_id,roles,revision) VALUES($1,$2,$3,$4,1)",
      [Ecto.UUID.bingenerate(), uuid(user), uuid(project), Enum.map(roles, &Atom.to_string/1)],
      log: false
    )

    :ok
  end

  def identity(f, opts \\ []) do
    Map.merge(
      %{issuer: f.config.issuer, subject: "known", sid: "sid-1", credential_expires_at_ms: clock(f).utc_ms + 3_600_000, tokens: %{"access_token" => "synthetic-token"}},
      Map.new(opts)
    )
  end

  def flow(f, opts \\ []) do
    state = Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
    Map.merge(%{state: state, nonce: "synthetic-nonce", verifier: "synthetic-verifier", issued_ms: clock(f).utc_ms}, Map.new(opts))
  end

  def uuid(id), do: Ecto.UUID.dump!(id)
end
