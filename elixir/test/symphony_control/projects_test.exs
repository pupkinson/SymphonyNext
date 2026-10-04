defmodule SymphonyControl.ProjectsTest do
  use ExUnit.Case, async: false

  alias SymphonyControl.{Health, Projects, Repo}

  defmodule Authorizer do
    def authorize(:admin, _action, _scope), do: :ok
    def authorize({:reader, id}, :project_read, id), do: :ok
    def authorize(_actor, _action, _scope), do: :deny
  end

  defmodule BrokenAuthorizer do
    def authorize(:raise, _action, _scope), do: raise("synthetic authorizer secret")
    def authorize(:throw, _action, _scope), do: throw("synthetic authorizer secret")
    def authorize(:exit, _action, _scope), do: exit("synthetic authorizer secret")
    def authorize(_actor, _action, _scope), do: true
  end

  setup_all do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    Code.require_file(Application.app_dir(:symphony_elixir, "priv/repo/migrations/20260925000000_create_projects.exs"))
    :ok
  end

  setup do
    previous = Application.fetch_env(:symphony_elixir, :project_authorizer)
    Application.put_env(:symphony_elixir, :project_authorizer, Authorizer)

    on_exit(fn ->
      case previous do
        {:ok, value} -> Application.put_env(:symphony_elixir, :project_authorizer, value)
        :error -> Application.delete_env(:symphony_elixir, :project_authorizer)
      end
    end)

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

    assert Health.readiness().ready
    # A missing API is an expected new-feature RED after a healthy real fixture.
    assert Code.ensure_loaded?(Projects), "Projects domain API has not been implemented"
    :ok
  end

  test "creation persists server identity, initial revision and timestamps across repository restart" do
    assert {:ok, project} = Projects.create_project(:admin, %{key: "ALPHA", name: "Project Alpha"})
    assert is_struct(project, SymphonyControl.Project)
    assert {:ok, _} = Ecto.UUID.cast(project.id)
    assert project.key == "ALPHA"
    assert project.name == "Project Alpha"
    assert project.lock_version == 1
    assert %DateTime{} = project.inserted_at
    assert %DateTime{} = project.updated_at
    assert %{rows: [["ALPHA", "Project Alpha", 1]]} = Repo.query!("SELECT key,name,lock_version FROM projects", [])

    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert {:ok, _} = Supervisor.restart_child(SymphonyControl.Application, Repo)
    assert eventually_ready?(System.monotonic_time(:millisecond) + 5_000)
    assert {:ok, ^project} = Projects.get_project(:admin, project.id)
  end

  test "missing or malformed server authorizer denies all operations before database access" do
    for value <- [nil, "client-selected-module", __MODULE__] do
      Application.put_env(:symphony_elixir, :project_authorizer, value)
      assert_error(Projects.create_project(:admin, %{key: "DENIED", name: "Denied"}), :forbidden)
      assert_error(Projects.get_project(:admin, "00000000-0000-4000-8000-000000000001"), :forbidden)
      assert_error(Projects.rename_project(:admin, "00000000-0000-4000-8000-000000000001", 1, "Denied"), :forbidden)
    end

    Application.delete_env(:symphony_elixir, :project_authorizer)
    assert_error(Projects.create_project(:admin, %{}), :forbidden)
    assert %{rows: [[0]]} = Repo.query!("SELECT count(*) FROM projects", [])
  end

  test "throwing and non-OK authorizers fail closed without exposing their errors" do
    Application.put_env(:symphony_elixir, :project_authorizer, BrokenAuthorizer)

    for actor <- [:raise, :throw, :exit, :other] do
      error = assert_error(Projects.create_project(actor, %{key: "DENIED", name: "Denied"}), :forbidden)
      refute inspect(error) =~ "synthetic authorizer secret"
    end

    assert %{rows: [[0]]} = Repo.query!("SELECT count(*) FROM projects", [])
  end

  test "a project reader cannot access another project or rename its own project" do
    {:ok, alpha} = Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"})
    {:ok, beta} = Projects.create_project(:admin, %{key: "BETA", name: "Beta"})
    actor = {:reader, alpha.id}
    assert {:ok, ^alpha} = Projects.get_project(actor, alpha.id)
    assert_error(Projects.get_project(actor, beta.id), :forbidden)
    assert_error(Projects.rename_project(actor, alpha.id, 1, "Changed"), :forbidden)
    assert_error(Projects.create_project(actor, %{key: "GAMMA", name: "Gamma"}), :forbidden)
    assert {:ok, ^alpha} = Projects.get_project(:admin, alpha.id)
    assert {:ok, ^beta} = Projects.get_project(:admin, beta.id)
  end

  for {attrs, fields} <- [
        {nil, [:attributes]},
        {%{"key" => "ALPHA", "name" => "Alpha"}, [:attributes]},
        {%{key: "ALPHA", name: "Alpha", id: "caller-owned"}, [:attributes]},
        {%{key: "ALPHA", name: "Alpha", lock_version: 100}, [:attributes]},
        {%{}, [:key, :name]},
        {%{key: "", name: "Alpha"}, [:key]},
        {%{key: " \t\n", name: "Alpha"}, [:key]},
        {%{key: 12, name: "Alpha"}, [:key]},
        {%{key: <<255>>, name: "Alpha"}, [:key]},
        {%{key: "ALPHA", name: <<0>>}, [:name]},
        {%{key: "ALPHA", name: nil}, [:name]},
        {%{key: "ALPHA", name: " \t\n"}, [:name]}
      ] do
    test "invalid creation has no effect: #{inspect(attrs)}" do
      assert_error(Projects.create_project(:admin, unquote(Macro.escape(attrs))), :invalid_input, unquote(fields))
      assert %{rows: [[0]]} = Repo.query!("SELECT count(*) FROM projects", [])
    end
  end

  test "duplicate key is a typed conflict without raw submitted values" do
    {:ok, first} = Projects.create_project(:admin, %{key: "SYNTHETIC-CANARY", name: "First"})
    error = assert_error(Projects.create_project(:admin, %{key: "SYNTHETIC-CANARY", name: "Second"}), :conflict, [:key])
    refute inspect(error) =~ "SYNTHETIC-CANARY"
    assert {:ok, ^first} = Projects.get_project(:admin, first.id)
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM projects", [])
  end

  test "concurrent creation of one key has exactly one database winner" do
    results = concurrently(fn -> Projects.create_project(:admin, %{key: "UNIQUE", name: "Concurrent"}) end)
    assert length(Enum.filter(results, &match?({:ok, _}, &1))) == 1
    assert [{:error, error}] = Enum.filter(results, &match?({:error, _}, &1))
    assert error.code == :conflict
    assert error.fields == [:key]
    assert %{rows: [[1]]} = Repo.query!("SELECT count(*) FROM projects", [])
  end

  test "malformed and missing IDs have distinct typed results" do
    for id <- [nil, 7, "not-a-uuid", <<255>>] do
      assert_error(Projects.get_project(:admin, id), :invalid_input, [:id])
      assert_error(Projects.rename_project(:admin, id, 1, "Changed"), :invalid_input, [:id])
    end

    id = "00000000-0000-4000-8000-000000000001"
    assert_error(Projects.get_project(:admin, id), :not_found)
    assert_error(Projects.rename_project(:admin, id, 1, "Changed"), :not_found)
  end

  test "rename changes only name and advances revision while preserving another project" do
    {:ok, alpha} = Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"})
    {:ok, beta} = Projects.create_project(:admin, %{key: "BETA", name: "Beta"})
    assert {:ok, renamed} = Projects.rename_project(:admin, alpha.id, 1, "Renamed")
    assert renamed.id == alpha.id
    assert renamed.key == "ALPHA"
    assert renamed.name == "Renamed"
    assert renamed.lock_version == 2
    assert renamed.inserted_at == alpha.inserted_at
    assert DateTime.compare(renamed.updated_at, alpha.updated_at) in [:eq, :gt]
    assert {:ok, ^renamed} = Projects.get_project(:admin, alpha.id)
    assert {:ok, ^beta} = Projects.get_project(:admin, beta.id)
  end

  test "invalid rename input and stale version leave the persisted project unchanged" do
    {:ok, project} = Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"})

    for version <- [nil, 0, -1, "1", 1.0] do
      assert_error(Projects.rename_project(:admin, project.id, version, "Changed"), :invalid_input, [:lock_version])
    end

    for name <- [nil, 12, " \t\n", <<255>>] do
      assert_error(Projects.rename_project(:admin, project.id, 1, name), :invalid_input, [:name])
    end

    assert_error(Projects.rename_project(:admin, project.id, 9, "Changed"), :conflict, [:lock_version])
    assert {:ok, ^project} = Projects.get_project(:admin, project.id)
  end

  test "concurrent renames with one expected version cannot overwrite each other" do
    {:ok, project} = Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"})
    results = concurrently(fn -> Projects.rename_project(:admin, project.id, 1, "Changed") end)
    assert length(Enum.filter(results, &match?({:ok, _}, &1))) == 1
    assert [{:error, error}] = Enum.filter(results, &match?({:error, _}, &1))
    assert error.code == :conflict
    assert error.fields == [:lock_version]
    assert {:ok, %{name: "Changed", lock_version: 2}} = Projects.get_project(:admin, project.id)
  end

  test "revision exhaustion cannot wrap an old revision back into validity" do
    {:ok, project} = Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"})
    Repo.query!("UPDATE projects SET lock_version=2147483647", [])
    assert_error(Projects.rename_project(:admin, project.id, 2_147_483_647, "Changed"), :conflict, [:lock_version])
    assert {:ok, %{name: "Alpha", lock_version: 2_147_483_647}} = Projects.get_project(:admin, project.id)
  end

  test "a stopped repository is unavailable and never produces a successful mutation" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert_error(Projects.get_project(:admin, "00000000-0000-4000-8000-000000000001"), :dependency_unavailable)
    assert_error(Projects.create_project(:admin, %{key: "ALPHA", name: "Alpha"}), :dependency_unavailable)
    assert_error(Projects.rename_project(:admin, "00000000-0000-4000-8000-000000000001", 1, "Changed"), :dependency_unavailable)
  end

  @tag capture_log: true
  test "a lost schema produces sanitized read failure and an unknown write outcome" do
    Repo.query!("DROP TABLE projects", [])
    assert_error(Projects.get_project(:admin, "00000000-0000-4000-8000-000000000001"), :dependency_unavailable)
    error = assert_error(Projects.create_project(:admin, %{key: "SYNTHETIC-CANARY", name: "Alpha"}), :unknown_outcome)
    assert {:ok, _} = Ecto.UUID.cast(error.reference_id)
    refute inspect(error) =~ "SYNTHETIC-CANARY"
    refute inspect(error) =~ "Postgrex"
  end

  @tag capture_log: true
  test "stalled checkout is bounded and a write timeout exposes a safe reconciliation ID" do
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)

    try do
      started = System.monotonic_time(:millisecond)
      assert_error(Projects.get_project(:admin, "00000000-0000-4000-8000-000000000001"), :dependency_unavailable)
      assert System.monotonic_time(:millisecond) - started < 1_500
      started = System.monotonic_time(:millisecond)
      error = assert_error(Projects.create_project(:admin, %{key: "UNKNOWN", name: "Unknown"}), :unknown_outcome)
      assert {:ok, _} = Ecto.UUID.cast(error.reference_id)
      assert System.monotonic_time(:millisecond) - started < 1_500
    after
      :sys.resume(pool)
    end

    assert %{rows: [[0]]} = Repo.query!("SELECT count(*) FROM projects", [])
  end

  @tag capture_log: true
  test "pool death during a read does not terminate the caller" do
    pool = Ecto.Adapter.lookup_meta(Repo).pid
    :ok = :sys.suspend(pool)
    probe = Task.async(fn -> Projects.get_project(:admin, "00000000-0000-4000-8000-000000000001") end)

    try do
      assert checkout_pending?(pool, System.monotonic_time(:millisecond) + 300)
      Process.exit(pool, :kill)
      assert_error(Task.await(probe, 2_000), :dependency_unavailable)
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

  defp assert_error(result, code, fields \\ []) do
    assert {:error, error} = result
    assert is_struct(error, SymphonyControl.Error)
    assert error.code == code
    assert error.fields == fields
    assert Map.keys(Map.from_struct(error)) |> Enum.sort() == [:code, :fields, :reference_id]
    error
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

  defp concurrently(operation) do
    tasks =
      for _ <- 1..2,
          do:
            Task.async(fn ->
              receive do
                :start -> operation.()
              end
            end)

    Enum.each(tasks, &send(&1.pid, :start))
    Enum.map(tasks, &Task.await(&1, 5_000))
  end
end
