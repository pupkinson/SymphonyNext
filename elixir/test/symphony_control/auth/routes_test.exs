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

  for post_logout_path <- ["/", "/signed-out", "/account/session-ended"] do
    @tag repair_n1: true
    test "N1 exact Config post-logout binding passes Routes: #{post_logout_path}" do
      {cfg, _manifest} = post_logout_config!(unquote(post_logout_path))
      assert :ok = Routes.validate(cfg)
      refute Config.activation_allowed?(cfg)
    end

    @tag repair_n1: true
    test "N1 runtime loaders preserve unverified post-logout binding: #{post_logout_path}" do
      {cfg, manifest} = post_logout_config!(unquote(post_logout_path))
      assert {:ok, loaded} = RuntimeConfig.load_auth_config(manifest)
      assert loaded.post_logout_uri == cfg.post_logout_uri
      System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", manifest)
      assert :ok = RuntimeConfig.configure()
      assert Application.fetch_env!(:symphony_elixir, :control_auth_status) == :unverified
      runtime_cfg = Application.fetch_env!(:symphony_elixir, :control_auth_config)
      assert runtime_cfg.post_logout_uri == cfg.post_logout_uri
      refute Config.activation_allowed?(runtime_cfg)
      refute Application.get_env(:symphony_elixir, :control_enabled)
      runtime = Reader.read!("config/runtime.exs", env: :test) |> Keyword.fetch!(:symphony_elixir)
      assert runtime[:control_auth_status] == :unverified
      assert runtime[:control_auth_config].post_logout_uri == cfg.post_logout_uri
    end

    @tag repair_n1: true
    test "N1 healthy standalone stays ready and denied with unverified binding: #{post_logout_path}" do
      f = AuthDbFixture.start!()
      {cfg, _manifest} = post_logout_config!(unquote(post_logout_path))
      Application.put_env(:symphony_elixir, :control_auth_config, cfg)
      Application.put_env(:symphony_elixir, :control_auth_status, :unverified)
      stop_fixture_control!()
      assert {:ok, _} = start_supervised({SymphonyControl.Application, enabled: true, repo: f.repo, http: [port: 0]})
      assert Repo.query!("SELECT 1", [], log: false).rows == [[1]]
      assert Health.readiness() == %{ready: true, database: true, schema: true}
      assert_standalone_denied!()
      assert Process.whereis(SymphonyControl.Auth.Access) == nil
      assert Application.fetch_env!(:symphony_elixir, :control_auth_config).post_logout_uri == cfg.post_logout_uri
    end
  end

  for post_logout_path <- ["/signed-out", "/account/session-ended"] do
    @tag repair_n1: true
    test "N1 explicit supervisor and Router admit exact non-root binding: #{post_logout_path}" do
      f = AuthDbFixture.start!()
      {cfg, _manifest} = post_logout_config!(unquote(post_logout_path))
      cfg = %{cfg | session_key_ref: f.config.session_key_ref}
      assert Router.init(auth: cfg)[:auth] == cfg
      stop_fixture_control!()
      options = [enabled: true, repo: f.repo, http: [port: 0], auth: [config: cfg]]
      assert {:ok, _} = start_supervised({SymphonyControl.Application, options})
      assert is_pid(Process.whereis(SymphonyControl.Auth.Access))
      assert Health.readiness() == %{ready: true, database: true, schema: true}
      assert_standalone_denied!()
      refute Config.activation_allowed?(cfg)
    end

    @tag repair_n1: true
    test "N1 owned HTTPS login retains fixed root return and cookie authority: #{post_logout_path}" do
      f = AuthHttpFixture.start!(post_logout_path: unquote(post_logout_path), runtime_identity_authorizer: AuthHttpFixture.Authorizer)
      expected = f.origin <> unquote(post_logout_path)
      assert {:ok, loaded} = Config.load(bindings(f.config))
      assert loaded.post_logout_uri == expected
      assert :ok = Routes.validate(loaded)

      Repo.query!(
        "INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)",
        [Ecto.UUID.bingenerate(), Ecto.UUID.dump!(f.user)],
        log: false
      )

      flow = AuthHttpFixture.login!(f, phase: :begin)
      response = AuthHttpFixture.callback(f, flow: flow)
      session = %{cookie: AuthHttpFixture.cookie(response, "__Host-symphony-control"), response: response}
      assert session.response.status == 303
      assert Req.Response.get_header(session.response, "location") == ["/"]
      assert is_binary(session.cookie)
      assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
      assert AuthHttpFixture.callback(f, flow: flow).status == 403
      assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
      [header] = Req.Response.get_header(session.response, "set-cookie")
      for attribute <- ["; secure", "; HttpOnly", "; SameSite=Lax", "; path=/"], do: assert(String.contains?(header, attribute))
      refute String.contains?(String.downcase(header), "domain=")
      assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 200
      assert OidcFixture.calls(f.provider, :eligibility) == 1
      second_flow = AuthHttpFixture.login!(f, phase: :begin)
      rotated_response = AuthHttpFixture.callback(f, flow: second_flow, cookie: second_flow.cookie <> "; " <> session.cookie)
      rotated_cookie = AuthHttpFixture.cookie(rotated_response, "__Host-symphony-control")
      assert rotated_response.status == 303
      assert Req.Response.get_header(rotated_response, "location") == ["/"]
      assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 403
      assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: rotated_cookie).status == 200
      assert AuthHttpFixture.counts(f) == %{exchanges: 2, sessions: 2}
      assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
      assert AuthHttpFixture.get(f, unquote(post_logout_path)).status == 404
      assert AuthHttpFixture.get(f, "/auth/logout", method: :post, cookie: session.cookie).status == 403
      assert f.config.post_logout_uri == expected
    end
  end

  @tag repair_n1: true
  test "N1 non-root config keeps default HTTPS eligibility and logout denied" do
    f = AuthHttpFixture.start!(post_logout_path: "/signed-out", default_access: true)
    session = AuthHttpFixture.login!(f)
    assert Req.Response.get_header(session.response, "location") == ["/"]
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 0
    assert AuthHttpFixture.get(f, "/auth/logout", method: :post, cookie: session.cookie).status == 403
    refute Config.activation_allowed?(f.config)
  end

  @tag repair_n1: true
  test "N1 frozen Config still rejects malformed post-logout bindings at public admission boundaries" do
    f = AuthDbFixture.start!()
    {cfg, manifest} = post_logout_config!("/signed-out")
    stop_fixture_control!()

    for value <- invalid_post_logout_uris(cfg.public_https_origin) do
      bad = %{cfg | post_logout_uri: value}
      assert {:error, :invalid_config} = Config.load(bindings(bad))
      File.write!(manifest, Jason.encode!(bindings(bad)))
      assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(manifest)
      System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", manifest)
      assert_raise RuntimeError, "invalid_control_auth_config", fn -> RuntimeConfig.configure() end
      assert_raise RuntimeError, "invalid_control_auth_config", fn -> Reader.read!("config/runtime.exs", env: :test) end
      Application.put_env(:symphony_elixir, :control_auth_status, :absent)
      assert_raise ArgumentError, "invalid_control_auth_options", fn -> Router.init(auth: bad) end
      options = [enabled: true, repo: f.repo, http: [port: 0], auth: [config: bad]]
      assert {:error, _} = start_supervised({SymphonyControl.Application, options})
      assert Process.whereis(Repo) == nil
    end
  end

  defp bindings(cfg), do: cfg |> Map.from_struct() |> Map.delete(:tls_cacerts)

  defp post_logout_config!(path) do
    provider = OidcFixture.start!()
    original = OidcFixture.config(provider)
    exact = original.public_https_origin <> path
    assert {:ok, cfg} = Config.load(bindings(%{original | post_logout_uri: exact}))
    assert cfg.post_logout_uri == exact
    root = Agent.get(provider.state, & &1.root)
    manifest = Path.join(root, "n1-operator.json")
    File.write!(manifest, Jason.encode!(bindings(cfg)))
    {cfg, manifest}
  end

  defp stop_fixture_control! do
    stop_supervised!(SymphonyControl.Application)
    stop_supervised!(AuthDbFixture.SnapshotClock)
  end

  defp assert_standalone_denied! do
    {Router, listener, _, _} = List.keyfind(Supervisor.which_children(SymphonyControl.Application), Router, 0)
    {:ok, {{127, 0, 0, 1}, port}} = ThousandIsland.listener_info(listener)
    origin = "http://127.0.0.1:#{port}"
    assert Req.get!(origin <> "/health/ready", retry: false).body == %{"ready" => true, "database" => true, "schema" => true}
    assert Req.get!(origin <> "/health/live", retry: false).body == %{"live" => true}

    for path <- ["/auth/login", "/api/v1/control/identity", "/api/v1/projects/00000000-0000-4000-8000-000000000001"] do
      assert Req.get!(origin <> path, retry: false).status == 403
    end

    wrong = Req.post!(origin <> "/health/live", retry: false)
    assert wrong.status == 405
    assert Req.Response.get_header(wrong, "allow") == ["GET"]
  end

  defp invalid_post_logout_uris(origin) do
    [
      nil,
      "not a URI",
      "https://",
      "https://foreign.example/signed-out",
      String.replace(origin, "https://", "http://") <> "/signed-out",
      String.replace(origin, "https://", "https://user@") <> "/signed-out",
      origin <> "/signed-out?next=/",
      origin <> "/signed-out#end"
    ]
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
