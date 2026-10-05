defmodule SymphonyControl.Auth.OidcFixture do
  @moduledoc false
  import Plug.Conn
  require ExUnit.Assertions
  alias SymphonyControl.Auth.Config

  def start!(opts \\ []) do
    suffix = Base.url_encode64(:crypto.strong_rand_bytes(12), padding: false)
    root = Path.join(System.tmp_dir!(), "sn005-https-#{System.pid()}-#{suffix}")
    File.mkdir_p!(root)
    cert = Path.join(root, "cert.pem")
    key = Path.join(root, "key.pem")
    ca_cert = Path.join(root, "ca.pem")
    ca_key = Path.join(root, "ca-key.pem")
    csr = Path.join(root, "server.csr")
    extensions = Path.join(root, "extensions")
    san = if Keyword.get(opts, :wrong_san), do: "DNS:foreign.example", else: "DNS:localhost,IP:127.0.0.1"
    File.write!(extensions, "subjectAltName=#{san}\nbasicConstraints=CA:FALSE\nextendedKeyUsage=serverAuth\n")

    {_, 0} =
      System.cmd(
        "openssl",
        [
          "req",
          "-x509",
          "-newkey",
          "ec",
          "-pkeyopt",
          "ec_paramgen_curve:P-256",
          "-nodes",
          "-keyout",
          ca_key,
          "-out",
          ca_cert,
          "-days",
          "1",
          "-subj",
          "/CN=SN005 disposable CA",
          "-addext",
          "basicConstraints=critical,CA:TRUE"
        ],
        stderr_to_stdout: true
      )

    {_, 0} = System.cmd("openssl", ["req", "-new", "-newkey", "ec", "-pkeyopt", "ec_paramgen_curve:P-256", "-nodes", "-keyout", key, "-out", csr, "-subj", "/CN=localhost"], stderr_to_stdout: true)
    {_, 0} = System.cmd("openssl", ["x509", "-req", "-in", csr, "-CA", ca_cert, "-CAkey", ca_key, "-CAcreateserial", "-out", cert, "-days", "1", "-extfile", extensions], stderr_to_stdout: true)
    secret = Path.join(root, "client-secret")
    File.write!(secret, "synthetic-client-secret-canary")
    File.chmod!(secret, 0o600)
    signing = JOSE.JWK.generate_key({:rsa, 2048})
    initial = %{opts: opts, root: root, signing: signing, counts: %{}, codes: %{}}
    state = ExUnit.Callbacks.start_supervised!({Agent, fn -> initial end}, id: make_ref())

    server_opts = [
      plug: {__MODULE__, state},
      scheme: :https,
      ip: {127, 0, 0, 1},
      port: 0,
      certfile: cert,
      keyfile: key,
      startup_log: false
    ]

    server = ExUnit.Callbacks.start_supervised!({Bandit, server_opts}, id: make_ref())
    {:ok, {_, port}} = ThousandIsland.listener_info(server)
    origin = "https://localhost:#{port}"
    Agent.update(state, &Map.put(&1, :origin, origin))
    [pem] = :public_key.pem_decode(File.read!(ca_cert))
    {:Certificate, ca, _} = pem

    ExUnit.Callbacks.on_exit(fn ->
      File.rm_rf!(root)
    end)

    %{state: state, server: server, origin: origin, secret_ref: secret, ca: ca}
  end

  def config(fixture) do
    {:ok, config} = Config.load(bindings(fixture))
    Map.put(config, :tls_cacerts, [fixture.ca])
  end

  def bindings(f) do
    %{
      generation: "fixture-v1",
      issuer: f.origin <> "/issuer",
      discovery_url: f.origin <> "/discovery",
      jwks_url: f.origin <> "/jwks",
      authorization_url: f.origin <> "/authorize",
      token_url: f.origin <> "/token",
      end_session_url: f.origin <> "/logout",
      client_id: "control-client",
      client_auth_method: "client_secret_basic",
      allowed_algorithms: ["RS256"],
      public_https_origin: "https://control.example",
      callback_uri: "https://control.example/auth/callback",
      post_logout_uri: "https://control.example/",
      backchannel_uri: "https://control.example/auth/backchannel-logout",
      application_id: "own-app",
      provider_id: "own-provider",
      resource_id: "own-control",
      client_secret_ref: f.secret_ref,
      session_key_ref: f.secret_ref,
      eligible_mechanism: nil,
      live_evidence: nil
    }
  end

  def issue_code(f, opts \\ []) do
    code = Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
    Agent.update(f.state, &put_in(&1, [:codes, code], Map.new(opts)))
    code
  end

  def calls(f, endpoint), do: Agent.get(f.state, &Map.get(&1.counts, endpoint, 0))

  def delayed_token_endpoint(f, connection_delay, handshake_delay) do
    root = Agent.get(f.state, & &1.root)

    opts = [
      ip: {127, 0, 0, 1},
      active: false,
      backlog: 0,
      certfile: Path.join(root, "cert.pem"),
      keyfile: Path.join(root, "key.pem"),
      sni_fun: fn _ ->
        Agent.update(f.state, &update_in(&1, [:counts, :tls_handshake], fn count -> (count || 0) + 1 end))
        Process.sleep(handshake_delay)
        []
      end
    ]

    {:ok, listener} = :ssl.listen(0, opts)
    {:ok, {_, port}} = :ssl.sockname(listener)
    {:ok, filler} = :gen_tcp.connect({127, 0, 0, 1}, port, [:binary, active: false], 1_000)
    url = "https://localhost:#{port}/token"
    Agent.update(f.state, &Map.put(&1, :token_url, url))
    ExUnit.Callbacks.on_exit(fn -> :ssl.close(listener) end)

    ExUnit.Callbacks.start_supervised!(
      {Task,
       fn ->
         Process.sleep(connection_delay)
         {:ok, queued} = :ssl.transport_accept(listener, 2_000)
         :ssl.close(queued)
         :gen_tcp.close(filler)
         {:ok, socket} = :ssl.transport_accept(listener, 2_000)
         Agent.update(f.state, &update_in(&1, [:counts, :tls_accept], fn count -> (count || 0) + 1 end))

         try do
           with {:ok, socket} <- :ssl.handshake(socket, 2_000),
                {:ok, request} <- :ssl.recv(socket, 0, 1_000),
                true <- String.starts_with?(request, "POST ") do
             Agent.update(f.state, &update_in(&1, [:counts, :token], fn count -> (count || 0) + 1 end))
           end
         after
           :ssl.close(socket)
         end
       end},
      id: make_ref()
    )

    Map.put(config(f), :token_url, url)
  end

  def record_log(f, log), do: Agent.update(f.state, &Map.put(&1, :captured_log, log))

  def assert_no_secret_echo(f) do
    log = Agent.get(f.state, &Map.fetch!(&1, :captured_log))
    ExUnit.Assertions.refute(log =~ "synthetic-client-secret-canary")
    ExUnit.Assertions.refute(log =~ "synthetic-access-canary")
    :ok
  end

  def init(state), do: state

  def call(conn, state) do
    endpoint =
      case conn.request_path do
        "/discovery" -> :discovery
        "/jwks" -> :jwks
        "/token" -> :token
        _ -> :other
      end

    data =
      Agent.get_and_update(state, fn data ->
        {data, update_in(data, [:counts, endpoint], &((&1 || 0) + 1))}
      end)

    Process.sleep(Keyword.get(data.opts, :delay_ms, 0))
    respond(conn, endpoint, state, data)
  end

  defp respond(conn, :discovery, _state, data) do
    document = %{
      "issuer" => data.origin <> "/issuer",
      "authorization_endpoint" => data.origin <> "/authorize",
      "token_endpoint" => Map.get(data, :token_url, data.origin <> "/token"),
      "jwks_uri" => data.origin <> "/jwks",
      "end_session_endpoint" => data.origin <> "/logout",
      "response_types_supported" => ["code"],
      "subject_types_supported" => ["public"],
      "id_token_signing_alg_values_supported" => ["RS256", "RS512", "none"],
      "scopes_supported" => ["openid", "profile", "email"],
      "grant_types_supported" => ["authorization_code"],
      "token_endpoint_auth_methods_supported" => ["client_secret_basic", "client_secret_post"],
      "code_challenge_methods_supported" => if(Keyword.get(data.opts, :pkce) == :plain, do: ["plain"], else: ["S256"])
    }

    discovery_response(conn, data, document)
  end

  defp respond(conn, :jwks, _state, data) do
    wait_for_keys(data)
    {_, public} = data.signing |> JOSE.JWK.to_public() |> JOSE.JWK.to_map()
    kid = if Keyword.get(data.opts, :fault) == :unknown_kid and Map.get(data.counts, :jwks, 0) == 0, do: "old", else: "current"

    if Keyword.get(data.opts, :fault) == :malformed_jwks do
      json(conn, 200, %{"keys" => [%{"kty" => "RSA", "n" => "?", "e" => "AQAB"}]})
    else
      json(conn, 200, %{"keys" => [Map.put(public, "kid", kid)]})
    end
  end

  defp respond(conn, :token, state, data) do
    {:ok, body, conn} = read_body(conn)
    params = URI.decode_query(body)

    expectations =
      Agent.get_and_update(state, fn current ->
        {Map.get(current.codes, params["code"]), %{current | codes: Map.delete(current.codes, params["code"])}}
      end)

    auth = "Basic " <> Base.encode64("control-client:synthetic-client-secret-canary")

    cond do
      get_req_header(conn, "authorization") != [auth] ->
        json(conn, 401, %{"error" => "invalid_client"})

      not is_map(expectations) ->
        json(conn, 400, %{"error" => "invalid_grant"})

      params["grant_type"] != "authorization_code" or params["redirect_uri"] != "https://control.example/auth/callback" or params["code_verifier"] != expectations.verifier ->
        json(conn, 400, %{"error" => "invalid_grant"})

      true ->
        token_response(conn, state, data, expectations, params)
    end
  end

  defp respond(conn, _, _, _), do: send_resp(conn, 404, "")

  defp discovery_response(conn, data, document) do
    case Keyword.get(data.opts, :fault) do
      :foreign_endpoint -> json(conn, 200, Map.put(document, "token_endpoint", "https://foreign.example/token"))
      :wrong_discovery_issuer -> json(conn, 200, Map.put(document, "issuer", data.origin <> "/other"))
      :redirect -> conn |> put_resp_header("location", data.origin <> "/other") |> send_resp(302, "")
      :oversized -> json(conn, 200, Map.put(document, "padding", String.duplicate("x", 1_048_577)))
      :invalid_json -> send_resp(conn, 200, "{")
      :json_array -> json(conn, 200, [])
      :rate_limited -> json(conn, 429, %{"error" => "slow_down"})
      _ -> json(conn, 200, document)
    end
  end

  defp wait_for_keys(data) do
    if owner = Keyword.get(data.opts, :hold_jwks) do
      send(owner, {:jwks_waiting, self()})

      receive do
        :release_jwks -> :ok
      after
        5_000 -> raise "fixture JWKS release missing"
      end
    end

    if Map.get(data.counts, :jwks, 0) > 0 do
      Process.sleep(Keyword.get(data.opts, :refresh_delay_ms, 0))
    end
  end

  defp token_response(conn, state, data, expectations, params) do
    case Keyword.get(data.opts, :fault) do
      :dpop_nonce ->
        conn |> put_resp_header("dpop-nonce", "synthetic-nonce") |> json(400, %{"error" => "use_dpop_nonce"})

      :lost_response ->
        Process.sleep(1_000)
        json(conn, 200, %{})

      _ ->
        payload = %{
          "id_token" => token(data, expectations),
          "access_token" => "synthetic-access-canary",
          "token_type" => "Bearer",
          "expires_in" => Keyword.get(data.opts, :expires_in, 120),
          "scope" => "openid profile email"
        }

        payload = if Keyword.get(data.opts, :omit_expiry), do: Map.delete(payload, "expires_in"), else: payload
        Agent.update(state, &Map.put(&1, :last_token, payload["id_token"]))
        conn = canary_header(conn, data, payload, params)

        if Keyword.get(data.opts, :fault) == :utf8_content_type do
          canaries = Enum.join([payload["id_token"], payload["access_token"], params["code"], "synthetic-client-secret-canary"], " ")

          conn
          |> put_resp_header("content-type", "application/json; x-canary=\"#{canaries} Ā\"")
          |> send_resp(200, Jason.encode!(payload))
        else
          json(conn, Keyword.get(data.opts, :token_status, 200), payload)
        end
    end
  end

  defp canary_header(conn, data, payload, params) do
    if Keyword.get(data.opts, :fault) == :non_utf8_header do
      canaries = Enum.join([payload["id_token"], payload["access_token"], params["code"], "synthetic-client-secret-canary"], " ")
      put_resp_header(conn, "x-canary", canaries <> <<255>>)
    else
      conn
    end
  end

  defp token(data, expectations) do
    now = System.system_time(:second)

    claims = %{
      "iss" => data.origin <> "/issuer",
      "sub" => "human-1",
      "aud" => "control-client",
      "azp" => "control-client",
      "nonce" => expectations.nonce,
      "iat" => now,
      "exp" => now + 120,
      "sid" => "session-1",
      "email" => "untrusted@example.test",
      "roles" => ["admin"]
    }

    fault = Keyword.get(data.opts, :fault)

    claims = fault_claims(claims, fault, now)
    encode_token(data, claims, fault)
  end

  defp fault_claims(claims, fault, now) do
    changes = %{
      wrong_issuer: {"iss", "https://foreign.example"},
      wrong_audience: {"aud", "other-client"},
      wrong_azp: {"azp", "other-client"},
      expired: {"exp", now},
      future_iat: {"iat", now + 31},
      wrong_nonce: {"nonce", "other-nonce"},
      empty_sub: {"sub", ""}
    }

    case Map.get(changes, fault) do
      {field, value} -> Map.put(claims, field, value)
      nil when fault == :missing_sub -> Map.delete(claims, "sub")
      nil when fault == :additional_audience -> Map.put(claims, "aud", ["control-client", "other-client"])
      nil when fault == :multi_audience_no_azp -> claims |> Map.put("aud", ["control-client", "other-client"]) |> Map.delete("azp")
      nil when fault == :single_audience_no_azp -> Map.delete(claims, "azp")
      nil when fault == :malformed_jwks -> claims
      _ -> claims
    end
  end

  defp encode_token(data, claims, fault) do
    cond do
      fault == :encrypted_unsigned ->
        key = JOSE.JWK.from_oct(:crypto.hash(:sha256, "synthetic-client-secret-canary"))
        {_, compact} = JOSE.JWE.block_encrypt(key, Jason.encode!(claims), %{"alg" => "dir", "enc" => "A256GCM"}) |> JOSE.JWE.compact()
        compact

      fault == :alg_none ->
        header = Base.url_encode64(Jason.encode!(%{"alg" => "none"}), padding: false)
        payload = Base.url_encode64(Jason.encode!(claims), padding: false)
        header <> "." <> payload <> "."

      true ->
        alg = if fault == :disallowed_alg, do: "RS512", else: "RS256"
        kid = if fault == :never_known_kid, do: "absent", else: "current"
        header = %{"alg" => alg, "kid" => kid}
        header = if fault == :jku_other_host, do: Map.put(header, "jku", "https://foreign.example/jwks"), else: header
        signing = if fault == :bad_signature, do: JOSE.JWK.generate_key({:rsa, 2048}), else: data.signing
        {_, compact} = JOSE.JWT.sign(signing, header, claims) |> JOSE.JWS.compact()
        if fault == :oversized_jwt, do: compact <> String.duplicate("x", 16_385), else: compact
    end
  end

  defp json(conn, status, data), do: conn |> put_resp_content_type("application/json") |> send_resp(status, Jason.encode!(data))
end
