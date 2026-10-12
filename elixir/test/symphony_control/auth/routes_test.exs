defmodule SymphonyControl.Auth.RoutesTest do
  use ExUnit.Case, async: false
  alias Elixir.Config.Reader
  alias SymphonyControl.Auth.{Config, OidcFixture, Routes}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Health, Repo, Router, RuntimeConfig}

  setup do
    env_keys = ~w(SYMPHONY_CONTROL_AUTH_CONFIG SYMPHONY_CONTROL_ENABLED SYMPHONY_CONTROL_DATABASE_URL)
    app_keys = [:control_auth_config, :control_auth_status, :control_enabled, :runtime_identity, Repo]
    env = Map.new(env_keys, &{&1, System.get_env(&1)})
    app = Map.new(app_keys, &{&1, Application.fetch_env(:symphony_elixir, &1)})
    Enum.each(env_keys, &System.delete_env/1)
    Application.delete_env(:symphony_elixir, :control_auth_config)
    Application.put_env(:symphony_elixir, :control_auth_status, :absent)

    on_exit(fn ->
      Enum.each(env, fn {key, value} -> if value, do: System.put_env(key, value), else: System.delete_env(key) end)

      Enum.each(app, fn
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
      end)
    end)

    :ok
  end

  @tag repair_r5: true
  test "R5 explicit malformed manifest rejects runtime loader and clears earlier valid config" do
    provider = OidcFixture.start!()
    cfg = OidcFixture.config(provider)
    root = Agent.get(provider.state, & &1.root)
    path = Path.join(root, "operator.json")
    File.write!(path, Jason.encode!(cfg |> Map.from_struct() |> Map.delete(:tls_cacerts)))
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
    assert :ok = RuntimeConfig.configure()
    assert Application.get_env(:symphony_elixir, :control_auth_status) == :unverified
    File.write!(path, "malformed")
    assert_raise RuntimeError, "invalid_control_auth_config", fn -> RuntimeConfig.configure() end
    assert Application.get_env(:symphony_elixir, :control_auth_config) == nil
    assert Application.get_env(:symphony_elixir, :control_auth_status) == :invalid
    assert Application.get_env(:symphony_elixir, :control_enabled) == false
    assert_raise RuntimeError, "invalid_control_auth_config", fn -> Reader.read!("config/runtime.exs", env: :test) end
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path <> "/missing")
    assert_raise RuntimeError, "invalid_control_auth_config", fn -> RuntimeConfig.configure() end
    System.delete_env("SYMPHONY_CONTROL_AUTH_CONFIG")
    assert :ok = RuntimeConfig.configure()
    assert Application.get_env(:symphony_elixir, :control_auth_status) == :absent
  end

  @tag repair_r5: true
  test "R5 invalid runtime status refuses standalone listener with healthy real DB" do
    f = AuthDbFixture.start!()
    assert Repo.query!("SELECT 1", [], log: false).rows == [[1]]
    assert Health.readiness().ready
    provider = OidcFixture.start!()
    root = Agent.get(provider.state, & &1.root)
    path = Path.join(root, "invalid-startup.json")
    File.write!(path, "malformed")
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
    assert_raise RuntimeError, "invalid_control_auth_config", fn -> RuntimeConfig.configure() end
    stop_supervised!(SymphonyControl.Application)
    stop_supervised!(AuthDbFixture.SnapshotClock)
    result = start_supervised({SymphonyControl.Application, enabled: true, repo: f.repo, http: [port: 0]})
    assert elem(result, 0) == :error
    assert Process.whereis(Repo) == nil
    assert Process.whereis(SymphonyControl.Application) == nil
    assert Process.whereis(SymphonyControl.Auth.Access) == nil
    System.delete_env("SYMPHONY_CONTROL_AUTH_CONFIG")
    assert :ok = RuntimeConfig.configure()
    start_supervised!({SymphonyControl.Application, enabled: true, repo: f.repo, http: [port: 0]})
    assert Repo.query!("SELECT 1", [], log: false).rows == [[1]]
    assert Health.readiness().ready
  end

  test "R5 failed later load clears valid binding and prevents a previous real cookie from yielding Actor" do
    f = AuthHttpFixture.start!(runtime_identity_authorizer: AuthHttpFixture.Authorizer)

    Repo.query!(
      "INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)",
      [Ecto.UUID.bingenerate(), Ecto.UUID.dump!(f.user)],
      log: false
    )

    session = AuthHttpFixture.login!(f)
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 200
    root = Agent.get(f.provider.state, & &1.root)
    path = Path.join(root, "later-invalid.json")
    File.write!(path, Jason.encode!(f.config |> Map.from_struct() |> Map.delete(:tls_cacerts)))
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
    assert :ok = RuntimeConfig.configure()
    File.write!(path, "malformed")
    assert_raise RuntimeError, "invalid_control_auth_config", fn -> RuntimeConfig.configure() end
    assert Application.get_env(:symphony_elixir, :control_auth_config) == nil
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    assert AuthHttpFixture.get(f, "/health/live").status == 200
  end

  @tag repair_r7: true
  test "R7 runtime manifest and standalone reject shadowed or missing auth paths" do
    f = AuthDbFixture.start!()
    provider = OidcFixture.start!()
    cfg = %{OidcFixture.config(provider) | session_key_ref: f.config.session_key_ref}
    root = Agent.get(provider.state, & &1.root)
    path = Path.join(root, "operator.json")
    assert Repo.query!("SELECT 1", [], log: false).rows == [[1]]
    stop_supervised!(SymphonyControl.Application)
    stop_supervised!(AuthDbFixture.SnapshotClock)

    for {callback, backchannel} <- invalid_paths() do
      callback_uri = cfg.public_https_origin <> callback
      backchannel_uri = cfg.public_https_origin <> backchannel
      bad = %{cfg | callback_uri: callback_uri, backchannel_uri: backchannel_uri}
      bindings = bad |> Map.from_struct() |> Map.delete(:tls_cacerts)
      assert {:ok, _} = Config.load(bindings)
      File.write!(path, Jason.encode!(bindings))
      assert elem(RuntimeConfig.load_auth_config(path), 0) == :error
      assert_raise ArgumentError, "invalid_control_auth_options", fn -> Router.init(auth: bad) end
      options = [enabled: true, repo: f.repo, http: [port: 0], auth: [config: bad]]
      result = start_supervised({SymphonyControl.Application, options})
      assert elem(result, 0) == :error
      assert Process.whereis(Repo) == nil
    end
  end

  test "R7 incomplete trusted config and untyped Router option refuse admission" do
    assert {:error, :invalid_auth_routes} = Routes.validate(%Config{})
    assert_raise ArgumentError, "invalid_control_auth_options", fn -> Router.init(auth: :untrusted) end
  end

  test "absent and well formed unverified runtime config stay nonactivated and standalone health survives" do
    f = AuthDbFixture.start!()
    provider = OidcFixture.start!()
    cfg = OidcFixture.config(provider)
    root = Agent.get(provider.state, & &1.root)
    path = Path.join(root, "operator.json")
    File.write!(path, Jason.encode!(cfg |> Map.from_struct() |> Map.delete(:tls_cacerts)))
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
    assert :ok = RuntimeConfig.configure()
    refute Config.activation_allowed?(cfg)
    stop_supervised!(SymphonyControl.Application)
    stop_supervised!(AuthDbFixture.SnapshotClock)
    start_supervised!({SymphonyControl.Application, enabled: true, repo: f.repo, http: [port: 0]})
    {Router, listener, _, _} = List.keyfind(Supervisor.which_children(SymphonyControl.Application), Router, 0)
    {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener)
    assert Req.get!("http://127.0.0.1:#{port}/health/ready", retry: false).status == 200
    assert Req.get!("http://127.0.0.1:#{port}/auth/login", retry: false).status == 403
    assert Req.get!("http://127.0.0.1:#{port}/api/v1/control/identity", retry: false).status == 403
    wrong_method = Req.post!("http://127.0.0.1:#{port}/health/live", retry: false)
    assert wrong_method.status == 405
    assert Req.Response.get_header(wrong_method, "allow") == ["GET"]
    assert Process.whereis(SymphonyControl.Auth.Access) == nil
  end

  defp invalid_paths do
    [
      {"", "/auth/backchannel-logout"},
      {"/", "/auth/backchannel-logout"},
      {"/same", "/same"},
      {"/auth/login", "/auth/backchannel-logout"},
      {"/health/live", "/auth/backchannel-logout"},
      {"/auth/callback", "/health/ready"},
      {"/api/v1/projects/123", "/auth/backchannel-logout"},
      {"/auth/callback", "/api/v1/control/identity"},
      {"/auth/logout", "/auth/backchannel-logout"},
      {"/health/ready", "/auth/backchannel-logout"},
      {"/auth/callback", ""},
      {"/auth/callback", "/"},
      {"/auth/callback", "/health/live"},
      {"/%68ealth/live", "/auth/backchannel-logout"},
      {"/health//live", "/auth/backchannel-logout"}
    ]
  end

  test "R7 valid distinct custom paths retain exact HTTPS callback and public health methods" do
    f = AuthHttpFixture.start!(callback_path: "/oidc/return", backchannel_path: "/oidc/revoke")
    flow = AuthHttpFixture.login!(f, phase: :begin)
    location = hd(Req.Response.get_header(flow.response, "location")) |> URI.parse()
    assert URI.decode_query(location.query)["redirect_uri"] == f.config.callback_uri
    reply = AuthHttpFixture.callback(f, flow: flow)
    assert reply.status == 303
    assert not is_nil(AuthHttpFixture.cookie(reply, "__Host-symphony-control"))
    assert AuthHttpFixture.get(f, "/oidc/revoke", method: :post).status == 403
    assert AuthHttpFixture.get(f, "/auth/callback").status == 404
    assert AuthHttpFixture.get(f, "/health/live").status == 200
    wrong = AuthHttpFixture.get(f, "/health/live", method: :post)
    assert wrong.status == 405
    assert Req.Response.get_header(wrong, "allow") == ["GET"]
  end
end
