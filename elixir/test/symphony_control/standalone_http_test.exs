defmodule SymphonyControl.StandaloneHttpTest do
  use ExUnit.Case, async: false

  alias __MODULE__.OperatorAuthorizer
  alias SymphonyControl.Auth.{Access, Clock, Config, OidcFixture, RateLimiter}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Health, Repo}

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

  @tag :continuation_readiness
  test "standalone startup waits for an actual initial connection before returning" do
    f = AuthDbFixture.start!()
    stop_supervised!(SymphonyControl.Application)
    owner = self()
    ref = make_ref()

    callback = fn _connection ->
      send(owner, {:connection_held, ref, self()})

      receive do
        {:release_connection, ^ref} -> :ok
      after
        1000 -> :ok
      end
    end

    starter =
      Task.async(fn ->
        {:ok, supervisor} = SymphonyControl.Application.start_link(enabled: true, repo: Keyword.put(f.repo, :after_connect, callback), http: [port: 0])
        send(owner, {:standalone_started, ref, supervisor})

        receive do
          {:stop_owned_startup, ^ref} -> Supervisor.stop(supervisor)
        after
          2000 -> Supervisor.stop(supervisor)
        end
      end)

    held =
      for _ <- 1..4 do
        assert_receive {:connection_held, ^ref, connection}, 1000
        connection
      end

    try do
      refute_receive {:standalone_started, ^ref, _supervisor}, 50
      Enum.each(held, &send(&1, {:release_connection, ref}))
      assert_receive {:standalone_started, ^ref, supervisor}, 1000
      assert Process.alive?(supervisor)
      assert Health.readiness() == %{ready: true, database: true, schema: true}
    after
      Enum.each(held, &send(&1, {:release_connection, ref}))
      send(starter.pid, {:stop_owned_startup, ref})
      Task.await(starter, 2000)
    end
  end

  test "default standalone startup remains Repo-only" do
    start_control(http: nil)
    assert Health.live?()
    assert [{Repo, _, :supervisor, _}] = Supervisor.which_children(SymphonyControl.Application)
    current = Process.whereis(SymphonyControl.Application)
    assert {:error, {:already_started, ^current}} = SymphonyControl.Application.start_link(enabled: true)
    assert Process.whereis(SymphonyControl.Application) == current
  end

  test "initial missing connection remains bounded live and unready" do
    f = AuthDbFixture.start!()
    stop_supervised!(SymphonyControl.Application)
    options = Keyword.put(f.repo, :socket_dir, f.repo[:socket_dir] <> "-owned-missing")
    started = System.monotonic_time(:millisecond)
    start_supervised!({SymphonyControl.Application, enabled: true, repo: options, http: [port: 0]})
    assert System.monotonic_time(:millisecond) - started < 1000
    assert Health.live?()
    assert Health.readiness() == %{ready: false, database: false, schema: false}
    assert request(port(), "/auth/login").status == 403
    identity_started = System.monotonic_time(:millisecond)

    try do
      assert request(port(), "/api/v1/control/identity").status == 403
    rescue
      error in Req.TransportError ->
        reason = if error.reason in [:closed, :timeout, :econnrefused, :econnreset, :enetunreach, :nxdomain], do: error.reason, else: :UNKNOWN
        elapsed = System.monotonic_time(:millisecond) - identity_started
        IO.puts("T1_MISSING_DB error_class=Req.TransportError reason=#{reason} elapsed_ms=#{elapsed} status=NOT_OBTAINED client_stage=request_call listener_stage=NOT_OBSERVED")
        reraise error, __STACKTRACE__
    end
  end

  test "missing canonical Repo during the initial probe cannot crash the startup owner" do
    f = AuthDbFixture.start!()
    stop_supervised!(SymphonyControl.Application)
    options = Keyword.put(f.repo, :name, :owned_noncanonical_repo)
    start_supervised!({SymphonyControl.Application, enabled: true, repo: options, http: [port: 0]})
    assert is_pid(Process.whereis(:owned_noncanonical_repo))
    assert Process.whereis(Repo) == nil
    assert Health.live?()
    assert Health.readiness() == %{ready: false, database: false, schema: false}
    assert request(port(), "/auth/login").status == 403
    assert request(port(), "/api/v1/control/identity").status == 403
  end

  test "only explicit server auth opts start auth workers after Repo; env config cannot activate" do
    provider = OidcFixture.start!()
    cfg = OidcFixture.config(provider)
    previous = Application.fetch_env(:symphony_elixir, :control_auth_config)

    on_exit(fn ->
      case previous do
        {:ok, value} -> Application.put_env(:symphony_elixir, :control_auth_config, value)
        :error -> Application.delete_env(:symphony_elixir, :control_auth_config)
      end
    end)

    Application.put_env(:symphony_elixir, :control_auth_config, cfg)
    start_control()
    assert length(Supervisor.which_children(SymphonyControl.Application)) == 2
    assert request(port(), "/auth/login").status == 403
    stop_supervised!(SymphonyControl.Application)

    confirm = fn _, _, _, deadline ->
      result =
        Req.get!(provider.origin <> "/eligibility",
          retry: false,
          receive_timeout: max(deadline - System.monotonic_time(:millisecond), 1),
          connect_options: [transport_opts: [cacerts: [provider.ca]]]
        )

      if result.status == 200, do: {:error, :forbidden}, else: {:error, :dependency_unavailable}
    end

    start_control(auth: [config: cfg, eligibility_confirm: confirm])
    assert length(Supervisor.which_children(SymphonyControl.Application)) == 7
    assert is_pid(Process.whereis(SymphonyControl.Auth.Eligibility))
    assert is_pid(Process.whereis(Clock))
    assert is_pid(Process.whereis(Access))
    assert is_pid(Process.whereis(RateLimiter))
    assert request(port(), "/auth/login").status == 403
  end

  test "invalid auth opts reject before Repo or listener creation" do
    invalid = [
      true,
      "callback",
      %{},
      [config: %Config{}],
      [config: nil],
      [config: nil, eligibility_confirm: "module"],
      [eligibility_confirm: fn _, _, _, _ -> :ok end]
    ]

    for auth <- invalid do
      result = SymphonyControl.Application.start_link(enabled: true, http: [port: 0], auth: auth)
      assert result == {:error, :invalid_auth_options}
      assert Process.whereis(Repo) == nil
    end
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

  test "identity disclosure requires cookie, wire confirmation and current local platform grant" do
    f = AuthHttpFixture.start!(runtime_identity_authorizer: AuthHttpFixture.Authorizer)
    Application.put_env(:symphony_elixir, :runtime_identity, commit_sha: String.duplicate("a", 40))
    session = AuthHttpFixture.login!(f)
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 403
    Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), Ecto.UUID.dump!(f.user)], log: false)
    response = AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie)
    assert response.status == 200
    assert response.body == %{"schema_version" => 1, "commit_sha" => String.duplicate("a", 40), "image_digest" => "UNKNOWN", "config_sha256" => "UNKNOWN"}
    assert OidcFixture.calls(f.provider, :eligibility) == 2
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

  @tag :n1_lifecycle
  test "production supervisor binding lifetime preserves raw missing nil and explicit defaults" do
    alias SymphonyControl.Auth.{Authorizer, AuthorizerBindings, RequestContext}
    keys = [:project_authorizer, :runtime_identity_authorizer]
    saved = for key <- keys, do: {key, Application.fetch_env(:symphony_elixir, key)}

    on_exit(fn ->
      Enum.each(saved, fn
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
      end)
    end)

    provider = OidcFixture.start!()
    cfg = OidcFixture.config(provider)

    for base <- [:error, {:ok, nil}, {:ok, OperatorAuthorizer}] do
      Enum.each(keys, fn key ->
        case base do
          :error -> Application.delete_env(:symphony_elixir, key)
          {:ok, value} -> Application.put_env(:symphony_elixir, key, value)
        end
      end)

      start_control(auth: [config: cfg])
      binding = :sys.get_state(AuthorizerBindings)
      assert binding.owner == Process.whereis(SymphonyControl.Application)

      Enum.each(keys, fn key ->
        assert Application.fetch_env(:symphony_elixir, key) == base
        assert AuthorizerBindings.resolve(key) == {:ok, Authorizer}
      end)

      for _ <- 1..2 do
        old = Process.whereis(Access)
        Process.exit(old, :kill)
        AuthDbFixture.await!(fn -> is_pid(Process.whereis(Access)) and Process.whereis(Access) != old end)
        assert Access.configuration(RequestContext.deadline()) == {:ok, cfg}
        current = :sys.get_state(AuthorizerBindings)
        assert current.owner == binding.owner
        assert current.generation == binding.generation

        Enum.each(keys, fn key ->
          assert Application.fetch_env(:symphony_elixir, key) == base
          assert AuthorizerBindings.resolve(key) == {:ok, Authorizer}
        end)

        assert request(port(), "/api/v1/control/identity").status == 403
      end

      stop_supervised!(SymphonyControl.Application)

      Enum.each(keys, fn key ->
        assert Application.fetch_env(:symphony_elixir, key) == base

        assert AuthorizerBindings.resolve(key) ==
                 {:ok,
                  case(base,
                    do: (
                      :error -> nil
                      {:ok, value} -> value
                    )
                  )}
      end)
    end
  end

  @tag :n2
  test "N2 owning supervisor graceful Access retirement and restart fence the inactive reply" do
    alias SymphonyControl.Auth.{Authorizer, AuthorizerBindings, RequestContext}
    alias SymphonyControl.RuntimeIdentity
    provider = OidcFixture.start!()
    cfg = OidcFixture.config(provider)
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, OperatorAuthorizer)
    start_control(auth: [config: cfg])
    helper = Process.whereis(AuthorizerBindings)
    active = :sys.get_state(helper)
    assert active.owner == Process.whereis(SymphonyControl.Application)
    assert active.writer == Process.whereis(Access)
    assert :ok = Supervisor.terminate_child(SymphonyControl.Application, Access)
    inactive = :sys.get_state(helper)
    assert inactive.phase == :inactive
    refute inactive.revision == active.revision
    assert {:ok, _} = RuntimeIdentity.read(:operator)
    :ok = :sys.suspend(helper)
    started = System.monotonic_time(:millisecond)

    caller =
      Task.async(fn ->
        Process.put({Authorizer, :deadline}, RequestContext.deadline())
        RuntimeIdentity.read(:operator)
      end)

    AuthDbFixture.await!(
      fn ->
        {:messages, messages} = Process.info(helper, :messages)
        Enum.any?(messages, &match?({:"$gen_call", _, {:resolve, _}}, &1))
      end,
      100
    )

    :erlang.suspend_process(caller.pid)
    :ok = :sys.resume(helper)

    try do
      AuthDbFixture.await!(
        fn ->
          {:messages, messages} = Process.info(caller.pid, :messages)
          Enum.any?(messages, &match?({_, {:ok, :base, _}}, &1))
        end,
        100
      )

      assert {:ok, access} = Supervisor.restart_child(SymphonyControl.Application, Access)
      assert Access.configuration(RequestContext.deadline()) == {:ok, cfg}
      current = :sys.get_state(helper)
      assert Process.whereis(AuthorizerBindings) == helper
      assert current.incarnation == active.incarnation
      assert current.writer == access
      refute current.generation == active.generation
      refute current.revision == inactive.revision
      :erlang.resume_process(caller.pid)
      assert Task.await(caller, 1000) == {:error, :forbidden}
      assert System.monotonic_time(:millisecond) - started < 250
      assert AuthorizerBindings.resolve(:runtime_identity_authorizer) == {:ok, Authorizer}
      assert RuntimeIdentity.read(:operator) == {:error, :forbidden}
      assert Application.fetch_env(:symphony_elixir, :runtime_identity_authorizer) == {:ok, OperatorAuthorizer}
    after
      :sys.resume(helper)
    end
  end

  defp start_control(opts \\ []) do
    schema = "sn004_http_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

    options = [enabled: true, repo: repo_opts(schema), http: Keyword.get(opts, :http, port: 0)]
    options = if Keyword.has_key?(opts, :auth), do: Keyword.put(options, :auth, opts[:auth]), else: options
    supervisor = start_supervised!({SymphonyControl.Application, options})

    if http = Keyword.get(options, :http) do
      {:ok, {_, port}} = ThousandIsland.listener_info(listener())
      AuthHttpFixture.record(%{kind: "legacy_http", port: port, beam_pid: inspect(supervisor), options: Map.new(http)})
    end

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
