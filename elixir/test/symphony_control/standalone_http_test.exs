defmodule SymphonyControl.StandaloneHttpTest do
  use ExUnit.Case, async: false

  alias __MODULE__.OperatorAuthorizer
  alias SymphonyControl.{Health, Repo}

  setup_all do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    {:ok, _} = Application.ensure_all_started(:phoenix)
    {:ok, _} = Application.ensure_all_started(:bandit)
    {:ok, _} = Application.ensure_all_started(:req)
    Code.require_file(Application.app_dir(:symphony_elixir, "priv/repo/migrations/20260925000000_create_projects.exs"))
    :ok
  end

  setup do
    keys = [:runtime_identity_authorizer, :runtime_identity]
    original = Enum.map(keys, &{&1, Application.fetch_env(:symphony_elixir, &1)})
    Enum.each(keys, &Application.delete_env(:symphony_elixir, &1))

    on_exit(fn ->
      Enum.each(original, fn
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
      end)
    end)

    :ok
  end

  test "explicit HTTP startup serves control health on loopback without agent children" do
    agent_names = [SymphonyElixir.AgentRuntimeSupervisor, SymphonyElixir.Orchestrator, SymphonyElixirWeb.Endpoint]
    agents_before = Enum.map(agent_names, &Process.whereis/1)
    start_control()

    children = Supervisor.which_children(SymphonyControl.Application)
    assert List.keymember?(children, SymphonyControl.Router, 0)
    assert Enum.map(agent_names, &Process.whereis/1) == agents_before
    assert length(children) == 2

    assert {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener())
    assert port > 0
    assert %{status: 200, body: %{"live" => true}} = request(port, "/health/live")

    assert %{status: 503, body: %{"ready" => false, "database" => true, "schema" => false}} =
             request(port, "/health/ready")

    assert %{rows: [[nil]]} = Repo.query!("SELECT to_regclass('schema_migrations')", [])
  end

  test "default standalone startup remains Repo-only" do
    start_control(http: nil)
    assert Health.live?()
    assert [{Repo, _, :supervisor, _}] = Supervisor.which_children(SymphonyControl.Application)
  end

  test "disabled control ignores HTTP and starts no repository" do
    assert SymphonyControl.Application.start_link(enabled: false, http: [port: 0]) == :ignore
    assert Process.whereis(SymphonyControl.Application) == nil
    assert Process.whereis(Repo) == nil
  end

  test "malformed HTTP options fail before starting the repository" do
    for http <- [
          [],
          false,
          %{port: 0},
          [port: -1],
          [port: 65_536],
          [port: "0"],
          [port: 0.0],
          [port: nil],
          [port: 0, port: 1],
          [port: 0, ip: {0, 0, 0, 0}],
          [port: 0, plug: SymphonyElixirWeb.Router]
        ] do
      result = SymphonyControl.Application.start_link(enabled: true, http: http)
      if match?({:ok, _}, result), do: Supervisor.stop(elem(result, 1))
      assert result == {:error, :invalid_control_http_options}

      assert Process.whereis(SymphonyControl.Application) == nil
      assert Process.whereis(Repo) == nil
    end
  end

  test "the maximum valid TCP port is accepted and remains loopback-only" do
    start_control(http: [port: 65_535])
    assert {:ok, {{127, 0, 0, 1}, 65_535}} = ThousandIsland.listener_info(listener())
    assert %{status: 200, body: %{"live" => true}} = request(65_535, "/health/live")
  end

  test "HTTP readiness becomes healthy only after explicit migration" do
    schema = start_control()
    migrate(schema)

    assert %{status: 200, body: %{"ready" => true, "database" => true, "schema" => true}} =
             request(port(), "/health/ready")
  end

  test "a partial schema stays live but fails HTTP readiness" do
    schema = start_control()
    migrate(schema)
    Repo.query!("ALTER TABLE projects DROP COLUMN lock_version", [])

    assert %{status: 503, body: %{"ready" => false, "database" => true, "schema" => false}} =
             request(port(), "/health/ready")

    assert %{status: 200, body: %{"live" => true}} = request(port(), "/health/live")
  end

  @tag capture_log: true
  test "HTTP stays live across database loss and readiness recovers" do
    schema = start_control()
    migrate(schema)
    assert request(port(), "/health/ready").status == 200
    {:ok, admin} = Postgrex.start_link(repo_opts("public") |> Keyword.put(:database, "postgres"))

    try do
      Postgrex.query!(admin, "ALTER DATABASE sn004_test ALLOW_CONNECTIONS false", [])
      Postgrex.query!(admin, "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'sn004_test'", [])

      assert %{status: 503, body: %{"ready" => false, "database" => false, "schema" => false}} =
               request(port(), "/health/ready")

      assert %{status: 200, body: %{"live" => true}} = request(port(), "/health/live")
    after
      Postgrex.query!(admin, "ALTER DATABASE sn004_test ALLOW_CONNECTIONS true", [])
      GenServer.stop(admin)
    end

    assert eventually_ready?(System.monotonic_time(:millisecond) + 5_000)
    assert request(port(), "/health/ready").status == 200
  end

  test "identity cannot be authorized through client query parameters or headers" do
    start_control()
    Application.put_env(:symphony_elixir, :runtime_identity, commit_sha: String.duplicate("a", 40))
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, OperatorAuthorizer)
    assert OperatorAuthorizer.authorize(:operator, :runtime_identity_read) == :ok

    response =
      Req.get!("http://127.0.0.1:#{port()}/api/v1/control/identity?current_actor=operator&actor=operator",
        headers: [{"x-current-actor", "operator"}, {"authorization", "Bearer synthetic-canary"}],
        retry: false
      )

    assert %{status: 403, body: %{"error" => "forbidden"}} = response
  end

  test "identity disclosure requires a trusted server-side actor assignment" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, OperatorAuthorizer)
    Application.put_env(:symphony_elixir, :runtime_identity, commit_sha: String.duplicate("a", 40))

    response =
      Plug.Test.conn(:get, "/api/v1/control/identity")
      |> Plug.Conn.assign(:current_actor, :operator)
      |> SymphonyControl.Router.call(SymphonyControl.Router.init([]))

    assert response.status == 200

    assert Jason.decode!(response.resp_body) == %{
             "schema_version" => 1,
             "commit_sha" => String.duplicate("a", 40),
             "image_digest" => "UNKNOWN",
             "config_sha256" => "UNKNOWN"
           }
  end

  test "identity remains forbidden when no server authorizer is installed" do
    start_control()
    assert %{status: 403, body: %{"error" => "forbidden"}} = request(port(), "/api/v1/control/identity")
  end

  test "standalone HTTP exposes no dashboard, agent state or mutation routes" do
    start_control()

    for path <- ["/", "/api/v1/state", "/api/v1/refresh", "/api/v1/projects", "/unknown"] do
      assert %{status: 404, body: %{"error" => "not_found"}} = request(port(), path)
    end

    assert %{status: 404, body: %{"error" => "not_found"}} =
             Req.post!("http://127.0.0.1:#{port()}/api/v1/refresh", retry: false)
  end

  test "known control routes reject non-GET methods" do
    start_control()

    for path <- ["/health/live", "/health/ready", "/api/v1/control/identity"], method <- [:post, :delete] do
      response = Req.request!(method: method, url: "http://127.0.0.1:#{port()}#{path}", retry: false)
      assert %{status: 405, body: %{"error" => "method_not_allowed"}} = response
      assert Req.Response.get_header(response, "allow") == ["GET"]
    end
  end

  test "listener restart and control shutdown preserve the lifecycle boundary" do
    schema = start_control()
    migrate(schema)
    original = listener()
    :ok = Supervisor.terminate_child(SymphonyControl.Application, SymphonyControl.Router)
    {:ok, restarted} = Supervisor.restart_child(SymphonyControl.Application, SymphonyControl.Router)
    assert restarted != original
    refute Process.alive?(original)
    assert request(port(), "/health/ready").status == 200
    bound_port = port()
    stop_supervised!(SymphonyControl.Application)
    refute Process.alive?(restarted)
    assert Process.whereis(Repo) == nil
    assert {:error, :econnrefused} = :gen_tcp.connect({127, 0, 0, 1}, bound_port, [], 500)
  end

  defp start_control(opts \\ []) do
    schema = "sn004_http_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

    options = [enabled: true, repo: repo_opts(schema), http: Keyword.get(opts, :http, port: 0)]
    start_supervised!({SymphonyControl.Application, options})
    Repo.query!("CREATE SCHEMA #{schema}", [])
    schema
  end

  defp repo_opts(schema) do
    [
      socket_dir: System.fetch_env!("SN004_TEST_PG_SOCKET"),
      port: 55_474,
      username: "sn004_fixture",
      database: "sn004_test",
      pool_size: 2,
      timeout: 1_000,
      parameters: [search_path: schema],
      log: false
    ]
  end

  defp listener do
    {SymphonyControl.Router, pid, :supervisor, _} =
      List.keyfind(Supervisor.which_children(SymphonyControl.Application), SymphonyControl.Router, 0)

    pid
  end

  defp request(port, path) do
    Req.get!("http://127.0.0.1:#{port}#{path}", retry: false, receive_timeout: 2_000)
  end

  defp port do
    {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener())
    port
  end

  defp migrate(schema) do
    migrations = [{20_260_925_000_000, SymphonyControl.Repo.Migrations.CreateProjects}]
    Ecto.Migrator.run(Repo, migrations, :up, all: true, prefix: schema, log: false)
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

  defmodule OperatorAuthorizer do
    def authorize(:operator, :runtime_identity_read), do: :ok
    def authorize(_actor, _action), do: {:error, :forbidden}
  end
end
