defmodule SymphonyControl.SchemaContractTest do
  use ExUnit.Case, async: false

  alias SymphonyControl.{Health, Repo}

  setup_all do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    Code.require_file(Application.app_dir(:symphony_elixir, "priv/repo/migrations/20260925000000_create_projects.exs"))
    :ok
  end

  setup do
    schema = "sn004_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

    repo = [
      socket_dir: System.fetch_env!("SN004_TEST_PG_SOCKET"),
      port: 55_474,
      username: "sn004_fixture",
      database: "sn004_test",
      pool_size: 2,
      timeout: 1_000,
      parameters: [search_path: schema],
      log: false
    ]

    start_supervised!({SymphonyControl.Application, enabled: true, repo: repo})
    Repo.query!("CREATE SCHEMA #{schema}", [])

    assert Ecto.Migrator.run(Repo, [{20_260_925_000_000, SymphonyControl.Repo.Migrations.CreateProjects}], :up,
             all: true,
             prefix: schema,
             log: false
           ) == [20_260_925_000_000]

    assert Health.readiness() == %{ready: true, database: true, schema: true}
    :ok
  end

  for {name, statements} <- [
        {"missing unique key index", ["DROP INDEX projects_key_index"]},
        {"nonunique replacement index", ["DROP INDEX projects_key_index", "CREATE INDEX projects_key_index ON projects (key)"]},
        {"partial unique key index", ["DROP INDEX projects_key_index", "CREATE UNIQUE INDEX projects_key_index ON projects (key) WHERE key <> 'EXCLUDED'"]},
        {"unique index on the wrong column", ["DROP INDEX projects_key_index", "CREATE UNIQUE INDEX projects_key_index ON projects (name)"]},
        {"missing UUID primary key", ["ALTER TABLE projects DROP CONSTRAINT projects_pkey"]},
        {"different key type", ["ALTER TABLE projects ALTER COLUMN key TYPE varchar(255)"]},
        {"nullable key", ["ALTER TABLE projects ALTER COLUMN key DROP NOT NULL"]},
        {"nullable timestamp", ["ALTER TABLE projects ALTER COLUMN inserted_at DROP NOT NULL"]},
        {"different timestamp precision", ["ALTER TABLE projects ALTER COLUMN updated_at TYPE timestamp(0)"]},
        {"different revision default", ["ALTER TABLE projects ALTER COLUMN lock_version SET DEFAULT 0"]},
        {"missing nonblank check", ["ALTER TABLE projects DROP CONSTRAINT projects_key_not_blank"]},
        {"weakened nonblank check", ["ALTER TABLE projects DROP CONSTRAINT projects_name_not_blank", "ALTER TABLE projects ADD CONSTRAINT projects_name_not_blank CHECK (true)"]},
        {"unvalidated revision check",
         ["ALTER TABLE projects DROP CONSTRAINT projects_lock_version_positive", "ALTER TABLE projects ADD CONSTRAINT projects_lock_version_positive CHECK (lock_version > 0) NOT VALID"]}
      ] do
    test "schema drift blocks readiness: #{name}" do
      for sql <- unquote(statements), do: Repo.query!(sql, [])

      assert Health.live?()
      assert Health.readiness() == %{ready: false, database: true, schema: false}

      router = SymphonyElixirWeb.Router
      response = router.call(Plug.Test.conn(:get, "/health/ready"), router.init([]))
      assert response.status == 503
      assert Jason.decode!(response.resp_body) == %{"ready" => false, "database" => true, "schema" => false}
    end
  end
end
