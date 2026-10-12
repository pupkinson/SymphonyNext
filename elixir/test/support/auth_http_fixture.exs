defmodule SymphonyControl.AuthHttpFixture do
  @moduledoc false
  require ExUnit.Assertions
  alias SymphonyControl.Auth.{Access, Clock, OidcFixture, RateLimiter, Store}
  alias SymphonyControl.{AuthDbFixture, Repo, Router}

  @spec start!(keyword()) :: map()
  def start!(opts \\ []) do
    for app <- [:bandit, :req], do: {:ok, _} = Application.ensure_all_started(app)
    db = AuthDbFixture.start!()
    provider = OidcFixture.start!(opts)
    port = port!()
    origin = "https://localhost:#{port}"
    cfg = config(provider, db, origin)
    db = %{db | config: cfg}
    install_authorizers(cfg, opts)
    clock = AuthDbFixture.clock(db)
    utc = System.system_time(:millisecond)
    mono = System.monotonic_time(:millisecond)
    AuthDbFixture.set_clock!(db, %{clock | utc_ms: utc, monotonic_ms: mono})
    AuthDbFixture.ticking_clock!(db)
    user = AuthDbFixture.seed_user!(db, subject: "human-1")
    start_auth(cfg, provider, opts)
    {server, id, server_opts, root} = start_http(cfg, provider, port, opts)
    record(%{kind: "ingress", port: port, root: root})

    %{
      db: db,
      config: cfg,
      provider: provider,
      origin: origin,
      server: server,
      server_id: id,
      server_opts: server_opts,
      user: user
    }
  end

  defp port! do
    {:ok, socket} = :gen_tcp.listen(0, ip: {127, 0, 0, 1})
    {:ok, {_, port}} = :inet.sockname(socket)
    :gen_tcp.close(socket)
    port
  end

  defp config(provider, db, origin) do
    %{
      OidcFixture.config(provider)
      | session_key_ref: db.config.session_key_ref,
        public_https_origin: origin,
        callback_uri: origin <> "/auth/callback",
        backchannel_uri: origin <> "/auth/backchannel-logout",
        post_logout_uri: origin <> "/"
    }
  end

  defp install_authorizers(cfg, opts) do
    for {key, value} <- [
          {:auth_http_fixture_config, cfg},
          {:project_authorizer, opts[:project_authorizer]},
          {:runtime_identity_authorizer, opts[:runtime_identity_authorizer]}
        ] do
      previous = Application.fetch_env(:symphony_elixir, key)
      Application.put_env(:symphony_elixir, key, value)
      ExUnit.Callbacks.on_exit(fn -> restore(key, previous) end)
    end
  end

  defp restore(key, {:ok, old}), do: Application.put_env(:symphony_elixir, key, old)
  defp restore(key, :error), do: Application.delete_env(:symphony_elixir, key)

  defp start_auth(cfg, provider, opts) do
    confirm = fn config, actor, clock, deadline -> wire_confirm(provider, config, actor, clock, deadline, opts) end

    access_opts =
      if Keyword.get(opts, :default_access) do
        [config: cfg]
      else
        [config: cfg, eligibility_confirm: Keyword.get(opts, :eligibility_confirm, confirm)]
      end

    if Code.ensure_loaded?(Access), do: ExUnit.Callbacks.start_supervised!({Access, access_opts})
    if Code.ensure_loaded?(RateLimiter), do: ExUnit.Callbacks.start_supervised!({RateLimiter, []})
  end

  defp wire_confirm(provider, cfg, actor, clock, deadline, opts) do
    options = [
      retry: false,
      receive_timeout: max(deadline - System.monotonic_time(:millisecond), 1),
      connect_options: [transport_opts: [cacerts: [provider.ca]]]
    ]

    response = Req.get!(provider.origin <> "/eligibility", options)
    result = if response.status == 200 and response.body == %{"eligible" => true}, do: :ok, else: {:error, :forbidden}
    if after_wire = Keyword.get(opts, :after_wire), do: after_wire.(cfg, actor, clock, deadline, result), else: result
  end

  defp start_http(cfg, provider, port, opts) do
    root = Agent.get(provider.state, & &1.root)
    id = make_ref()

    server_opts = [
      plug: {Router, [auth: Keyword.get(opts, :router_config, cfg)]},
      scheme: :https,
      ip: {127, 0, 0, 1},
      port: port,
      certfile: Path.join(root, "cert.pem"),
      keyfile: Path.join(root, "key.pem"),
      startup_log: false
    ]

    server = ExUnit.Callbacks.start_supervised!({Bandit, server_opts}, id: id)
    {server, id, server_opts, root}
  end

  @spec login!(map(), keyword()) :: map()
  def login!(f, opts \\ []) do
    begin = get(f, "/auth/login", opts)
    ExUnit.Assertions.assert(begin.status == 303, "GET login must return committed-flow redirect")
    location = hd(Req.Response.get_header(begin, "location"))
    authorization = Req.get!(location, request_options(f))
    callback = hd(Req.Response.get_header(authorization, "location")) |> URI.parse()
    flow = %{cookie: cookie(begin, "__Host-symphony-browser"), params: URI.decode_query(callback.query), response: begin}

    if Keyword.get(opts, :phase) == :begin do
      flow
    else
      response = callback(f, flow: flow)
      ExUnit.Assertions.assert(response.status == 303, "callback must confirm local session")
      %{cookie: cookie(response, "__Host-symphony-control"), response: response}
    end
  end

  @spec callback(map(), keyword()) :: Req.Response.t()
  def callback(f, opts) do
    flow = Keyword.fetch!(opts, :flow)
    params = Map.merge(flow.params, Keyword.get(opts, :params, %{}))
    get(f, "/auth/callback?" <> URI.encode_query(params), cookie: Keyword.get(opts, :cookie, flow.cookie))
  end

  @spec get(map(), binary(), keyword()) :: Req.Response.t()
  def get(f, path, opts \\ []) do
    headers = Keyword.get(opts, :headers, [])
    headers = if opts[:cookie], do: [{"cookie", opts[:cookie]} | headers], else: headers
    Req.request!([url: f.origin <> path, method: Keyword.get(opts, :method, :get), headers: headers, body: opts[:body]] ++ request_options(f))
  end

  @spec counts(map()) :: %{exchanges: integer(), sessions: integer()}
  def counts(f) do
    [[sessions]] = Repo.query!("SELECT count(*) FROM control_auth_sessions", [], log: false).rows
    %{exchanges: OidcFixture.calls(f.provider, :token), sessions: sessions}
  end

  @spec cookie(Req.Response.t(), binary()) :: binary() | nil
  def cookie(response, name) do
    response
    |> Req.Response.get_header("set-cookie")
    |> Enum.find_value(fn value ->
      if String.starts_with?(value, name <> "="), do: hd(String.split(value, ";"))
    end)
  end

  @spec request_options(map()) :: keyword()
  def request_options(f), do: [retry: false, redirect: false, receive_timeout: 6000, connect_options: [transport_opts: [cacerts: [f.provider.ca]]]]

  @spec restart_http!(map()) :: pid()
  def restart_http!(f) do
    ExUnit.Callbacks.stop_supervised!(f.server_id)
    ExUnit.Callbacks.start_supervised!({Bandit, f.server_opts}, id: f.server_id)
  end

  @spec record(map()) :: :ok | nil
  def record(data) do
    if path = System.get_env("SN005_TEST_RESOURCE_LEDGER"), do: File.write!(path, Jason.encode!(data) <> "\n", [:append])
  end

  defmodule Authorizer do
    def authorize(actor, action, scope), do: permit(actor, action, scope)
    def authorize(actor, :runtime_identity_read), do: permit(actor, :runtime_identity_read, :platform)

    defp permit(actor, action, scope) do
      cfg = Application.fetch_env!(:symphony_elixir, :auth_http_fixture_config)

      case Store.permissions(cfg, actor, scope, Clock.now()) do
        {:ok, permissions} -> if MapSet.member?(permissions, action), do: :ok, else: :deny
        _ -> :deny
      end
    end
  end
end
