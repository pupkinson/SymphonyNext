defmodule SymphonyControl.AuthHttpFixture do
  @moduledoc false
  require ExUnit.Assertions
  alias SymphonyControl.Auth.{Access, Clock, Eligibility, OidcFixture, RateLimiter, Store}
  alias SymphonyControl.{AuthDbFixture, Repo, Router}

  defmodule LoginClock do
    use GenServer
    alias SymphonyControl.Auth.{Clock, Login}

    def start_link(opts), do: GenServer.start_link(__MODULE__, opts, name: Clock)
    @impl true
    def init(opts), do: {:ok, %{base: opts[:base], owner: opts[:owner], final: opts[:final], samples: %{}, issued: nil, advanced: nil, delivery: opts[:delivery]}}

    @impl true
    def handle_call(:now, {caller, _}, state) do
      login_sample = login_sample?(caller)
      count = Map.get(state.samples, caller, 0) + if(login_sample, do: 1, else: 0)
      final = login_sample and count == state.final
      # Controlled stable offset0.5ms: issue M799.9 -> u800/m799;
      # final M=end+one native unit -> u=E-1/m=end. The two floor
      # buckets differ by1ms, with actual native producer/unit/epoch.
      sample = projected_sample(state, final)
      native = System.monotonic_time()
      age = sample_age(final or state.advanced != nil)
      sample = Map.merge(sample, %{native_anchor: native - age, native_unit: System.convert_time_unit(1, :second, :native), native_clock: self()})
      issued = if login_sample and count == state.final - 1, do: sample, else: state.issued
      if final, do: publish_sample(state, caller, sample, issued, native)
      advanced = if final, do: sample, else: state.advanced
      {:reply, sample, %{state | samples: Map.put(state.samples, caller, count), issued: issued, advanced: advanced}}
    end

    defp sample_age(true), do: System.convert_time_unit(1, :millisecond, :native) |> div(2) |> Kernel.+(1)
    defp sample_age(false), do: System.convert_time_unit(900, :microsecond, :native)

    defp login_sample?(caller) do
      {:current_stacktrace, stack} = Process.info(caller, :current_stacktrace)
      Enum.any?(stack, fn {module, function, _, _} -> module == Login and function == :sample end)
    end

    defp projected_sample(state, true) do
      base = state.base
      expiry = if state.final == 3, do: base.utc_ms + 300_000, else: provider_expiry()
      %{base | utc_ms: expiry - 1, monotonic_ms: base.monotonic_ms + expiry - base.utc_ms}
    end

    defp projected_sample(state, false), do: state.advanced || state.base

    defp publish_sample(state, caller, sample, issued, native) do
      send(state.owner, {:lifetime_projection, sample, issued, native})
      deliver(state.delivery, state.owner, caller)
    end

    defp deliver(:held, owner, caller) do
      send(owner, {:login_sample_held, self(), caller})

      receive do
        :release_login_sample -> :ok
      after
        1000 -> :ok
      end
    end

    defp deliver(:delayed, _owner, _caller), do: Process.sleep(10)
    defp deliver(_, _owner, _caller), do: :ok

    defp provider_expiry do
      [[expiry]] = Repo.query!("SELECT expires_at_ms FROM control_auth_sessions ORDER BY expires_at_ms DESC LIMIT 1", [], log: false).rows
      expiry
    end
  end

  @spec login_clock!(map(), pos_integer(), keyword()) :: pid()
  def login_clock!(_f, final, opts \\ []) do
    base = Clock.now()
    ExUnit.Callbacks.stop_supervised!(AuthDbFixture.SnapshotClock)
    ExUnit.Callbacks.start_supervised!({LoginClock, base: base, final: final, owner: self(), delivery: opts[:delivery]})
  end

  @spec start!(keyword()) :: map()
  def start!(opts \\ []) do
    for app <- [:bandit, :req], do: {:ok, _} = Application.ensure_all_started(app)
    db = AuthDbFixture.start!()
    provider = OidcFixture.start!(opts)
    port = port!()
    origin = "https://localhost:#{port}"
    cfg = config(provider, db, origin, opts)
    Agent.update(provider.state, &%{&1 | opts: Keyword.put(&1.opts, :rp_post_logout_uri, cfg.post_logout_uri)})
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
    record(%{kind: "ingress", port: port, root: root, beam_pid: inspect(server)})

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

  defp config(provider, db, origin, opts) do
    %{
      OidcFixture.config(provider)
      | session_key_ref: db.config.session_key_ref,
        public_https_origin: origin,
        callback_uri: origin <> Keyword.get(opts, :callback_path, "/auth/callback"),
        backchannel_uri: origin <> Keyword.get(opts, :backchannel_path, "/auth/backchannel-logout"),
        post_logout_uri: origin <> Keyword.get(opts, :post_logout_path, "/")
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
      if Keyword.get(opts, :default_access, false) or Keyword.get(opts, :task4, false) do
        [config: cfg]
      else
        [config: cfg, eligibility_confirm: Keyword.get(opts, :eligibility_confirm, confirm)]
      end

    if Keyword.get(opts, :task4) do
      observer = fn config, material, deadline -> observe(provider, config, material, deadline) end
      binding = %{version: "synthetic-wire-v1", evidence: provider.observation_evidence}
      ExUnit.Callbacks.start_supervised!({Eligibility, config: cfg, observer: observer, observation_binding: binding})
    end

    if Code.ensure_loaded?(Access), do: ExUnit.Callbacks.start_supervised!({Access, access_opts})
    if Code.ensure_loaded?(RateLimiter), do: ExUnit.Callbacks.start_supervised!({RateLimiter, []})
  end

  def observe(provider, cfg, material, deadline) do
    headers = [
      {"authorization", "Bearer " <> material.tokens.access.token},
      {"x-fixture-subject", material.actor.subject},
      {"x-fixture-sid", Jason.encode!(material.sid)},
      {"x-fixture-resource", cfg.resource_id}
    ]

    response =
      Req.get!(provider.origin <> "/eligibility",
        headers: headers,
        retry: false,
        redirect: false,
        receive_timeout: max(deadline - System.monotonic_time(:millisecond), 1),
        connect_options: [timeout: max(deadline - System.monotonic_time(:millisecond), 1), transport_opts: [cacerts: [provider.ca]]]
      )

    if response.status == 200, do: {:ok, response.body}, else: {:error, :forbidden}
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

    ExUnit.Assertions.assert(
      begin.status == 303,
      if begin.status == 303 do
        "GET login must return committed-flow redirect"
      else
        reason =
          case begin.body do
            %{"error" => reason} when reason in ["invalid_request", "forbidden", "dependency_unavailable", "rate_limited", "unknown_outcome"] -> reason
            %{"error" => nil} -> "absent"
            %{"error" => _} -> "unknown"
            %{} -> "absent"
            value when value in [nil, ""] -> "absent"
            _ -> "unknown"
          end

        "GET login must return committed-flow redirect; status=#{begin.status} error=#{reason}"
      end
    )

    location = hd(Req.Response.get_header(begin, "location"))
    authorization = Req.get!(location, request_options(f))
    callback = hd(Req.Response.get_header(authorization, "location")) |> URI.parse()
    flow = %{cookie: cookie(begin, "__Host-symphony-browser"), params: URI.decode_query(callback.query), response: begin, provider_cookie: cookie(authorization, "__Host-fixture-op")}

    if Keyword.get(opts, :phase) == :begin do
      flow
    else
      response = callback(f, flow: flow)
      ExUnit.Assertions.assert(response.status == 303, "callback must confirm local session")
      %{cookie: cookie(response, "__Host-symphony-control"), response: response, provider_cookie: flow.provider_cookie}
    end
  end

  @spec callback(map(), keyword()) :: Req.Response.t()
  def callback(f, opts) do
    flow = Keyword.fetch!(opts, :flow)
    params = Map.merge(flow.params, Keyword.get(opts, :params, %{}))
    get(f, URI.parse(f.config.callback_uri).path <> "?" <> URI.encode_query(params), cookie: Keyword.get(opts, :cookie, flow.cookie))
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
    if path = System.get_env("SN005_TEST_RESOURCE_LEDGER") do
      metadata = Map.merge(data, %{vm_pid: System.pid(), vm_starttime: File.read!("/proc/#{System.pid()}/stat") |> String.split() |> Enum.at(21), owner: inspect(self())})
      File.write!(path, Jason.encode!(metadata) <> "\n", [:append])
    end
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
