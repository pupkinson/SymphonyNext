defmodule SymphonyControl.ProjectReadHttpTest do
  use ExUnit.Case, async: false

  alias SymphonyControl.Auth.OidcFixture
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Health, Repo}
  @alpha "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
  @beta "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
  @absent "cccccccc-cccc-4ccc-8ccc-cccccccccccc"

  defmodule PermissiveAuthorizer do
    def authorize(_, _, _), do: :ok
  end

  defmodule BrokenAuthorizer do
    def authorize(_, _, _) do
      case Application.get_env(:symphony_elixir, :auth_http_authorizer_fault) do
        :raise -> raise("SYNTHETIC-AUTHORIZER-CANARY")
        :throw -> throw("SYNTHETIC-AUTHORIZER-CANARY")
        :exit -> exit("SYNTHETIC-AUTHORIZER-CANARY")
      end
    end
  end

  defmodule MissingProjectAuthorizer do
    def authorize(actor, :project_read, id) do
      if AuthHttpFixture.Authorizer.authorize(actor, :project_read, id) == :ok do
        Repo.query!("DELETE FROM control_auth_memberships WHERE project_id=$1", [Ecto.UUID.dump!(id)], log: false)
        Repo.query!("DELETE FROM projects WHERE id=$1", [Ecto.UUID.dump!(id)], log: false)
        :ok
      else
        :deny
      end
    end
  end

  setup do
    f = AuthHttpFixture.start!(project_authorizer: AuthHttpFixture.Authorizer)

    for {id, key, name} <- [{@alpha, "ALPHA", "Project Alpha"}, {@beta, "BETA", "PRIVATE-BETA-CANARY"}] do
      Repo.query!(
        "INSERT INTO projects (id,key,name,lock_version,inserted_at,updated_at) " <>
          "VALUES ($1,$2,$3,5,'2026-10-04 00:00:00.000001','2026-10-04 01:00:00.000002')",
        [Ecto.UUID.dump!(id), key, name],
        log: false
      )
    end

    AuthDbFixture.seed_membership!(f.db, f.user, @alpha, [:viewer])
    session = AuthHttpFixture.login!(f)
    Process.put(:auth_http, {f, session.cookie})
    on_exit(fn -> Application.delete_env(:symphony_elixir, :auth_http_authorizer_fault) end)
    :ok
  end

  @tag :new_route_red
  test "wire-confirmed project read over real HTTPS returns only the versioned project contract" do
    port = :fixture
    response = request(port, @alpha)
    assert response.status == 200
    assert response.body == alpha_response()
    assert Req.Response.get_header(response, "cache-control") == ["no-store"]
    assert %{rows: [[2, 5, 5]]} = Repo.query!("SELECT count(*),min(lock_version),max(lock_version) FROM projects", [])
  end

  test "path UUID is normalized and query parameters cannot replace its project scope" do
    port = :fixture
    response = request(port, String.upcase(@alpha) <> "?id=#{@beta}&current_actor=admin")
    assert response.status == 200
    assert response.body == alpha_response()
  end

  test "project-scoped reader cannot disclose another or an unauthorized absent project" do
    for id <- [@beta, @absent] do
      response = route(id, {:reader, @alpha})
      assert_error(response, 403, "forbidden")
      refute Jason.encode!(response.body) =~ "PRIVATE-BETA-CANARY"
    end
  end

  test "ordinary loopback requests cannot create an actor from query, headers or body" do
    {f, _} = Process.get(:auth_http)

    response =
      AuthHttpFixture.get(f, "/api/v1/projects/#{@alpha}?current_actor=admin&actor=admin",
        headers: [{"x-current-actor", "admin"}, {"authorization", "Bearer SYNTHETIC-CANARY"}],
        body: ~s({"current_actor":"admin","id":"#{@beta}"})
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

  test "wire-confirmed session does not retain a removed current local project grant" do
    {f, _} = Process.get(:auth_http)
    assert request(:fixture, @alpha).status == 200
    Repo.query!("DELETE FROM control_auth_memberships WHERE project_id=$1", [Ecto.UUID.dump!(@alpha)], log: false)
    assert_error(request(:fixture, @alpha), 403, "forbidden")
    assert OidcFixture.calls(f.provider, :eligibility) == 2
  end

  test "missing, malformed and throwing authorizers fail closed without secret error details" do
    for authorizer <- [nil, "untrusted-module", __MODULE__] do
      Application.put_env(:symphony_elixir, :project_authorizer, authorizer)
      assert_error(route(@alpha, {:reader, @alpha}), 403, "forbidden")
    end

    Application.put_env(:symphony_elixir, :project_authorizer, BrokenAuthorizer)

    for fault <- [:raise, :throw, :exit] do
      Application.put_env(:symphony_elixir, :auth_http_authorizer_fault, fault)
      response = route(@alpha, {:reader, @alpha})
      assert_error(response, 403, "forbidden")
      refute Jason.encode!(response.body) =~ "SYNTHETIC-AUTHORIZER-CANARY"
    end
  end

  test "invalid UUID is a sanitized 400 for a trusted actor" do
    assert_error(route("SYNTHETIC-INVALID-ID-CANARY", {:reader, @alpha}), 400, "invalid_input")
  end

  test "an authorized absent project is 404 without exposing its identifier" do
    {f, _} = Process.get(:auth_http)
    Repo.query!("INSERT INTO projects(id,key,name,inserted_at,updated_at) VALUES($1,'ABSENT','Absent',now(),now())", [Ecto.UUID.dump!(@absent)], log: false)
    AuthDbFixture.seed_membership!(f.db, f.user, @absent, [:viewer])
    Application.put_env(:symphony_elixir, :project_authorizer, MissingProjectAuthorizer)
    assert_error(route(@absent, {:reader, @absent}), 404, "not_found")
  end

  test "stopped repository produces sanitized 503 while control remains live" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    assert_error(route(@alpha, {:reader, @alpha}), 503, "dependency_unavailable")
    assert Health.live?()
  end

  @tag capture_log: true
  test "real database query failure is unavailable without SQL or driver disclosure" do
    Repo.query!("DROP TABLE projects CASCADE", [])
    assert_error(route(@alpha, {:reader, @alpha}), 503, "dependency_unavailable")
  end

  test "non-GET project requests cannot mutate project state" do
    for method <- [:post, :put, :patch, :delete, :head] do
      {f, _} = Process.get(:auth_http)
      response = AuthHttpFixture.get(f, "/api/v1/projects/#{@alpha}", method: method)
      assert response.status == 405
      assert Req.Response.get_header(response, "allow") == ["GET"]
      assert Req.Response.get_header(response, "cache-control") == ["no-store"]
      if method != :head, do: assert(response.body == %{"error" => "method_not_allowed"})
    end

    assert %{rows: [["Project Alpha", 5]]} = Repo.query!("SELECT name,lock_version FROM projects WHERE key='ALPHA'", [])
  end

  test "collection, nested and mutation-style project paths remain absent" do
    for path <- ["/api/v1/projects", "/api/v1/projects/#{@alpha}/rename", "/api/v1/projects/#{@alpha}/issues"] do
      {f, _} = Process.get(:auth_http)
      response = AuthHttpFixture.get(f, path)
      assert %{status: 404, body: %{"error" => "not_found"}} = response
    end
  end

  test "repository and control listener restart retain persisted read-only project revision" do
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    {:ok, _} = Supervisor.restart_child(SymphonyControl.Application, Repo)
    {f, _} = Process.get(:auth_http)
    AuthHttpFixture.restart_http!(f)
    assert Health.readiness().ready
    response = request(:fixture, @alpha)
    assert response.status == 200
    assert response.body == alpha_response()
    assert %{status: 403, body: %{"error" => "forbidden"}} = request(:unauthenticated, @alpha)
  end

  defp route(id, actor) do
    {f, cookie} = Process.get(:auth_http)
    AuthHttpFixture.get(f, "/api/v1/projects/#{id}", cookie: if(actor, do: cookie))
  end

  defp assert_error(response, status, code) do
    assert response.status == status
    assert response.body == %{"error" => code}
    assert Req.Response.get_header(response, "cache-control") == ["no-store"]
  end

  defp request(mode, id) do
    {f, cookie} = Process.get(:auth_http)
    AuthHttpFixture.get(f, "/api/v1/projects/#{id}", cookie: if(mode == :fixture, do: cookie))
  end

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
