defmodule SymphonyControl.ProjectReadHttpTest do
  use ExUnit.Case, async: false

  alias __MODULE__.{Authorizer, BrokenAuthorizer, PermissiveAuthorizer, TrustedActorFixture}
  alias SymphonyControl.{Health, Repo, Router}

  @alpha "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
  @beta "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
  @absent "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

  defmodule Authorizer do
    def authorize({:reader, id}, :project_read, id), do: :ok
    def authorize(_actor, _action, _scope), do: :deny
  end

  defmodule PermissiveAuthorizer do
    def authorize(_actor, _action, _scope), do: :ok
  end

  defmodule BrokenAuthorizer do
    def authorize(:raise, _action, _scope), do: raise("SYNTHETIC-AUTHORIZER-CANARY")
    def authorize(:throw, _action, _scope), do: throw("SYNTHETIC-AUTHORIZER-CANARY")
    def authorize(:exit, _action, _scope), do: exit("SYNTHETIC-AUTHORIZER-CANARY")
  end

  defmodule TrustedActorFixture do
    # Trusted embedding fixture only; this is not an authentication mechanism.
    def init(actor), do: actor

    def call(conn, actor) do
      conn |> Plug.Conn.assign(:current_actor, actor) |> Router.call(Router.init([]))
    end
  end

  setup_all do
    for app <- [:ecto_sql, :phoenix, :bandit, :req], do: {:ok, _} = Application.ensure_all_started(app)
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

    schema = "sn004_read_http_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

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

    start_supervised!({SymphonyControl.Application, enabled: true, repo: repo, http: [port: 0]})
    Repo.query!("CREATE SCHEMA #{schema}", [])
    migrations = [{20_260_925_000_000, SymphonyControl.Repo.Migrations.CreateProjects}]
    Ecto.Migrator.run(Repo, migrations, :up, all: true, prefix: schema, log: false)
    assert Health.readiness().ready

    for {id, key, name} <- [{@alpha, "ALPHA", "Project Alpha"}, {@beta, "BETA", "PRIVATE-BETA-CANARY"}] do
      Repo.query!(
        "INSERT INTO projects (id,key,name,lock_version,inserted_at,updated_at) " <>
          "VALUES ($1,$2,$3,5,'2026-10-04 00:00:00.000001','2026-10-04 01:00:00.000002')",
        [Ecto.UUID.dump!(id), key, name]
      )
    end

    :ok
  end

  @tag :new_route_red
  test "trusted project read over real HTTP returns only the versioned project contract" do
    port = trusted_port({:reader, @alpha})
    response = request(port, @alpha)
    assert response.status == 200
    assert response.body == alpha_response()
    assert Req.Response.get_header(response, "cache-control") == ["no-store"]
    assert %{rows: [[2, 5, 5]]} = Repo.query!("SELECT count(*),min(lock_version),max(lock_version) FROM projects", [])
  end

  test "path UUID is normalized and query parameters cannot replace its project scope" do
    port = trusted_port({:reader, @alpha})
    response = request(port, String.upcase(@alpha) <> "?id=#{@beta}&current_actor=admin")
    assert response.status == 200
    assert response.body == alpha_response()
  end

  test "project-scoped reader cannot disclose another or an unauthorized absent project" do
    for id <- [@beta, @absent] do
      response = route(id, {:reader, @alpha})
      assert_error(response, 403, "forbidden")
      refute response.resp_body =~ "PRIVATE-BETA-CANARY"
    end
  end

  test "ordinary loopback requests cannot create an actor from query, headers or body" do
    response =
      Req.request!(
        method: :get,
        url: "http://127.0.0.1:#{control_port()}/api/v1/projects/#{@alpha}?current_actor=admin&actor=admin",
        headers: [{"x-current-actor", "admin"}, {"authorization", "Bearer SYNTHETIC-CANARY"}],
        body: ~s({"current_actor":"admin","id":"#{@beta}"}),
        retry: false
      )

    assert %{status: 403, body: %{"error" => "forbidden"}} = response
    assert Req.Response.get_header(response, "cache-control") == ["no-store"]
  end

  test "missing actor stays forbidden even with a permissive server authorizer" do
    Application.put_env(:symphony_elixir, :project_authorizer, PermissiveAuthorizer)
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert_error(route(@alpha, nil), 403, "forbidden")
    assert_error(route("invalid", nil), 403, "forbidden")
  end

  test "missing, malformed and throwing authorizers fail closed without secret error details" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)

    for authorizer <- [nil, "untrusted-module", __MODULE__] do
      Application.put_env(:symphony_elixir, :project_authorizer, authorizer)
      assert_error(route(@alpha, {:reader, @alpha}), 403, "forbidden")
    end

    Application.put_env(:symphony_elixir, :project_authorizer, BrokenAuthorizer)

    for actor <- [:raise, :throw, :exit] do
      response = route(@alpha, actor)
      assert_error(response, 403, "forbidden")
      refute response.resp_body =~ "SYNTHETIC-AUTHORIZER-CANARY"
    end
  end

  test "invalid UUID is a sanitized 400 for a trusted actor" do
    assert_error(route("SYNTHETIC-INVALID-ID-CANARY", {:reader, @alpha}), 400, "invalid_input")
  end

  test "an authorized absent project is 404 without exposing its identifier" do
    assert_error(route(@absent, {:reader, @absent}), 404, "not_found")
  end

  test "stopped repository produces sanitized 503 while control remains live" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert_error(route(@alpha, {:reader, @alpha}), 503, "dependency_unavailable")
    assert Health.live?()
  end

  @tag capture_log: true
  test "real database query failure is unavailable without SQL or driver disclosure" do
    Repo.query!("DROP TABLE projects", [])
    assert_error(route(@alpha, {:reader, @alpha}), 503, "dependency_unavailable")
  end

  test "non-GET project requests cannot mutate project state" do
    for method <- [:post, :put, :patch, :delete, :head] do
      response = Req.request!(method: method, url: "http://127.0.0.1:#{control_port()}/api/v1/projects/#{@alpha}", retry: false)
      assert response.status == 405
      assert Req.Response.get_header(response, "allow") == ["GET"]
      assert Req.Response.get_header(response, "cache-control") == ["no-store"]
      if method != :head, do: assert(response.body == %{"error" => "method_not_allowed"})
    end

    assert %{rows: [["Project Alpha", 5]]} = Repo.query!("SELECT name,lock_version FROM projects WHERE key='ALPHA'", [])
  end

  test "collection, nested and mutation-style project paths remain absent" do
    for path <- ["/api/v1/projects", "/api/v1/projects/#{@alpha}/rename", "/api/v1/projects/#{@alpha}/issues"] do
      response = Req.get!("http://127.0.0.1:#{control_port()}#{path}", retry: false)
      assert %{status: 404, body: %{"error" => "not_found"}} = response
    end
  end

  test "repository and control listener restart retain persisted read-only project revision" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    {:ok, _} = Supervisor.restart_child(SymphonyControl.Application, Repo)
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Router)
    {:ok, _} = Supervisor.restart_child(SymphonyControl.Application, Router)
    assert Health.readiness().ready
    response = request(trusted_port({:reader, @alpha}), @alpha)
    assert response.status == 200
    assert response.body == alpha_response()
    assert %{status: 403, body: %{"error" => "forbidden"}} = request(control_port(), @alpha)
  end

  defp route(id, actor) do
    Plug.Test.conn(:get, "/api/v1/projects/#{id}")
    |> Plug.Conn.assign(:current_actor, actor)
    |> Router.call(Router.init([]))
  end

  defp assert_error(response, status, code) do
    assert response.status == status
    assert Jason.decode!(response.resp_body) == %{"error" => code}
    assert Plug.Conn.get_resp_header(response, "cache-control") == ["no-store"]
  end

  defp trusted_port(actor) do
    options = [plug: {TrustedActorFixture, actor}, scheme: :http, ip: {127, 0, 0, 1}, port: 0, startup_log: false]
    listener = start_supervised!({Bandit, options})
    {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener)
    port
  end

  defp control_port do
    {Router, listener, :supervisor, _} = List.keyfind(Supervisor.which_children(SymphonyControl.Application), Router, 0)
    {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener)
    port
  end

  defp request(port, id), do: Req.get!("http://127.0.0.1:#{port}/api/v1/projects/#{id}", retry: false, receive_timeout: 2_000)

  defp alpha_response do
    %{
      "schema_version" => 1,
      "project" => %{
        "id" => @alpha,
        "key" => "ALPHA",
        "name" => "Project Alpha",
        "lock_version" => 5,
        "inserted_at" => "2026-10-04T00:00:00.000001Z",
        "updated_at" => "2026-10-04T01:00:00.000002Z"
      }
    }
  end
end
