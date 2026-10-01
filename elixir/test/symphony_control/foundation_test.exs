defmodule SymphonyControl.FoundationTest do
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
    %{schema: schema}
  end

  test "a clean database is live but not ready, without health creating tables" do
    assert Health.live?()
    assert Health.readiness() == %{ready: false, database: true, schema: false}
    assert %{rows: [[nil]]} = Repo.query!("SELECT to_regclass('schema_migrations')", [])
  end

  test "migration is repeatable and preserves project data", %{schema: schema} do
    assert migrate(schema) == [20_260_925_000_000]

    Repo.query!(
      """
      INSERT INTO projects (id, key, name, lock_version, inserted_at, updated_at)
      VALUES ('00000000-0000-4000-8000-000000000001', 'TEST', 'Fixture', 1, now(), now())
      """,
      []
    )

    assert migrate(schema) == []
    assert Health.readiness() == %{ready: true, database: true, schema: true}
    assert %{rows: [["Fixture"]]} = Repo.query!("SELECT name FROM projects", [])
  end

  test "missing migration version and future versions both block readiness", %{schema: schema} do
    migrate(schema)
    Repo.query!("DELETE FROM schema_migrations", [])
    refute Health.readiness().ready
    Repo.query!("INSERT INTO schema_migrations(version, inserted_at) VALUES (99999999999999, now())", [])
    refute Health.readiness().ready
  end

  test "a missing required column blocks readiness", %{schema: schema} do
    migrate(schema)
    Repo.query!("ALTER TABLE projects DROP COLUMN lock_version", [])
    assert Health.readiness() == %{ready: false, database: true, schema: false}
  end

  test "losing the repository blocks readiness without changing control liveness" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert Health.live?()
    assert Health.readiness() == %{ready: false, database: false, schema: false}
  end

  test "core stopped means not live and not ready" do
    stop_supervised!(SymphonyControl.Application)
    refute Health.live?()
    assert Health.readiness() == %{ready: false, database: false, schema: false}
  end

  test "HTTP health reflects the real schema state", %{schema: schema} do
    router = SymphonyElixirWeb.Router
    live = router.call(Plug.Test.conn(:get, "/health/live"), router.init([]))
    assert live.status == 200
    assert Jason.decode!(live.resp_body) == %{"live" => true}
    ready = router.call(Plug.Test.conn(:get, "/health/ready"), router.init([]))
    assert ready.status == 503
    migrate(schema)
    ready = router.call(Plug.Test.conn(:get, "/health/ready"), router.init([]))
    assert ready.status == 200
    assert Jason.decode!(ready.resp_body) == %{"ready" => true, "database" => true, "schema" => true}
  end

  @tag capture_log: true
  test "database loss blocks readiness and recovery restores it", %{schema: schema} do
    migrate(schema)

    {:ok, admin} =
      Postgrex.start_link(
        socket_dir: System.fetch_env!("SN004_TEST_PG_SOCKET"),
        port: 55_474,
        username: "sn004_fixture",
        database: "postgres"
      )

    try do
      Postgrex.query!(admin, "ALTER DATABASE sn004_test ALLOW_CONNECTIONS false", [])
      Postgrex.query!(admin, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'sn004_test'", [])
      assert Health.live?()
      assert Health.readiness() == %{ready: false, database: false, schema: false}
    after
      Postgrex.query!(admin, "ALTER DATABASE sn004_test ALLOW_CONNECTIONS true", [])
      GenServer.stop(admin)
    end

    assert eventually_ready?(System.monotonic_time(:millisecond) + 5_000)
  end

  test "migration enforces unique project keys and nonblank names", %{schema: schema} do
    migrate(schema)
    sql = "INSERT INTO projects(id,key,name,inserted_at,updated_at) VALUES ($1,$2,$3,now(),now())"
    Repo.query!(sql, [Ecto.UUID.bingenerate(), "UNIQUE", "Project"])
    duplicate = Repo.query(sql, [Ecto.UUID.bingenerate(), "UNIQUE", "Another"])
    assert {:error, %Postgrex.Error{postgres: %{code: :unique_violation}}} = duplicate
    blank = Repo.query(sql, [Ecto.UUID.bingenerate(), "EMPTY", " "])
    assert {:error, %Postgrex.Error{postgres: %{code: :check_violation}}} = blank
  end

  @tag capture_log: true
  test "a stalled connection pool cannot hold readiness indefinitely", %{schema: schema} do
    migrate(schema)
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)
    started = System.monotonic_time(:millisecond)

    try do
      assert Health.readiness() == %{ready: false, database: false, schema: false}
      assert System.monotonic_time(:millisecond) - started < 1_500
    after
      :sys.resume(pool)
    end

    assert eventually_ready?(System.monotonic_time(:millisecond) + 5_000)
  end

  @tag capture_log: true
  test "pool death during checkout returns unavailable instead of exiting" do
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)
    probe = Task.async(fn -> Health.readiness() end)

    try do
      assert checkout_pending?(pool, System.monotonic_time(:millisecond) + 300)
      Process.exit(pool, :kill)
      assert Task.await(probe, 2_000) == %{ready: false, database: false, schema: false}
    after
      if Process.alive?(pool), do: :sys.resume(pool)
    end
  end

  defp checkout_pending?(pool, deadline) do
    {:messages, messages} = Process.info(pool, :messages)

    if Enum.any?(messages, &match?({:db_connection, _, {:checkout, _, _, _}}, &1)) do
      true
    else
      if System.monotonic_time(:millisecond) < deadline do
        Process.sleep(1)
        checkout_pending?(pool, deadline)
      else
        false
      end
    end
  end

  defp eventually_ready?(deadline) do
    cond do
      Health.readiness().ready ->
        true

      System.monotonic_time(:millisecond) >= deadline ->
        false

      true ->
        Process.sleep(25)
        eventually_ready?(deadline)
    end
  end

  defp migrate(schema) do
    migrations = [{20_260_925_000_000, SymphonyControl.Repo.Migrations.CreateProjects}]
    Ecto.Migrator.run(Repo, migrations, :up, all: true, prefix: schema, log: false)
  end
end
