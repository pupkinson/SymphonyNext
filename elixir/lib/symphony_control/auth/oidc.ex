defmodule SymphonyControl.Auth.Oidc do
  @moduledoc "Oidcc protocol adapter with exact destinations and one bounded code submission."
  @behaviour :oidcc_http_adapter
  alias SymphonyControl.Auth.Config
  @max_response 1_048_576
  @reasons [:invalid_request, :forbidden, :dependency_unavailable, :unknown_outcome, :rate_limited]
  @type verified_identity :: %{
          issuer: binary(),
          subject: binary(),
          sid: binary() | nil,
          credential_expires_at_ms: integer(),
          tokens: map()
        }

  @spec authorization_url(Config.t(), map(), integer()) :: {:ok, String.t()} | {:error, Config.reason()}
  def authorization_url(%Config{} = cfg, input, deadline) do
    bounded(deadline, :get, fn deadline ->
      with :ok <- validate_input(input, true),
           {:ok, context, transport} <- context(cfg, deadline),
           {:ok, url} <- Oidcc.Authorization.create_redirect_url(context, Map.merge(options(cfg, input, transport), %{state: input.state, scopes: ["openid", "profile", "email"]})) do
        {:ok, IO.iodata_to_binary(url)}
      end
    end)
  end

  @spec exchange(Config.t(), binary(), map(), integer()) :: {:ok, verified_identity()} | {:error, Config.reason()}
  def exchange(%Config{} = cfg, code, input, deadline) do
    bounded(deadline, :post, fn deadline ->
      with true <- is_binary(code) and byte_size(code) in 1..4096,
           :ok <- validate_input(input, false),
           {:ok, context, transport} <- context(cfg, deadline),
           opts = exchange_options(cfg, input, transport),
           {:ok, token, _refresh} <- Oidcc.Token.retrieve_with_refresh(code, context, opts),
           {:ok, identity} <- identity(cfg, token, transport) do
        {:ok, identity}
      else
        false -> {:error, :invalid_request}
        error -> error
      end
    end)
  end

  defp bounded(deadline, method, fun) do
    deadline = min(deadline, now() + 5_000)

    if deadline <= now() do
      transport_error(:get)
    else
      task = Task.async(fn -> run_guarded(fun, deadline) end)

      case Task.yield(task, max(deadline - now(), 0)) do
        {:ok, result} ->
          accept_result(result, deadline, method)

        nil ->
          Task.shutdown(task, :brutal_kill)
          transport_error(method)
      end
    end
  end

  defp accept_result(result, deadline, method),
    do: if(now() < deadline, do: result, else: transport_error(method))

  defp run_guarded(fun, deadline), do: guarded(fn -> fun.(deadline) end)

  defp exchange_options(cfg, input, transport) do
    options(cfg, input, transport)
    |> Map.put(:trusted_audiences, [])
    |> Map.put(:refresh_jwks, fn _old, _kid -> refresh_keys(cfg, transport) end)
  end

  defp validate_input(input, state?) when is_map(input) do
    valid =
      is_binary(input[:nonce]) and byte_size(input[:nonce]) in 32..256 and
        is_binary(input[:verifier]) and byte_size(input[:verifier]) in 43..128 and String.match?(input[:verifier], ~r/\A[A-Za-z0-9._~-]+\z/) and
        (not state? or (is_binary(input[:state]) and byte_size(input[:state]) in 32..256))

    if valid, do: :ok, else: {:error, :invalid_request}
  end

  defp validate_input(_, _), do: {:error, :invalid_request}

  defp guarded(fun) do
    case fun.() do
      {:ok, value} -> {:ok, value}
      {:error, reason} when reason in @reasons -> {:error, reason}
      _ -> {:error, :forbidden}
    end
  catch
    _, _ -> {:error, :forbidden}
  end

  defp context(cfg, deadline) do
    transport = %{config: cfg, deadline: deadline, posts: :atomics.new(1, []), received_at: :atomics.new(1, [])}

    with {:ok, document} <- get_json(cfg.discovery_url, transport),
         :ok <- validate_document(cfg, document),
         {:ok, provider} <- Oidcc.ProviderConfiguration.decode_configuration(safe_document(cfg, document)),
         {:ok, keys} <- get_json(cfg.jwks_url, transport),
         {:ok, secret} <- read_secret(cfg.client_secret_ref) do
      {:ok, Oidcc.ClientContext.from_manual(provider, JOSE.JWK.from_map(keys), cfg.client_id, secret), transport}
    else
      error -> error
    end
  end

  defp validate_document(cfg, doc) do
    bindings = [{"issuer", cfg.issuer}, {"authorization_endpoint", cfg.authorization_url}, {"token_endpoint", cfg.token_url}, {"jwks_uri", cfg.jwks_url}, {"end_session_endpoint", cfg.end_session_url}]

    valid =
      Enum.all?(bindings, fn {field, value} -> doc[field] == value end) and
        "S256" in Map.get(doc, "code_challenge_methods_supported", []) and
        cfg.client_auth_method in Map.get(doc, "token_endpoint_auth_methods_supported", []) and
        Enum.all?(cfg.allowed_algorithms, &(&1 in Map.get(doc, "id_token_signing_alg_values_supported", [])))

    if valid, do: :ok, else: {:error, :forbidden}
  end

  defp safe_document(cfg, doc) do
    doc
    |> Map.take(~w(issuer authorization_endpoint token_endpoint jwks_uri end_session_endpoint response_types_supported subject_types_supported scopes_supported))
    |> Map.merge(%{
      "id_token_signing_alg_values_supported" => cfg.allowed_algorithms,
      "token_endpoint_auth_methods_supported" => [cfg.client_auth_method],
      "grant_types_supported" => ["authorization_code"],
      "code_challenge_methods_supported" => ["S256"]
    })
  end

  defp read_secret(path) do
    case File.open(path, [:read, :binary]) do
      {:ok, file} ->
        try do
          case IO.binread(file, 16_385) do
            value when is_binary(value) and byte_size(value) in 1..16_384 -> {:ok, value}
            _ -> {:error, :dependency_unavailable}
          end
        after
          File.close(file)
        end

      _ ->
        {:error, :dependency_unavailable}
    end
  end

  defp options(cfg, input, transport),
    do: %{redirect_uri: cfg.callback_uri, nonce: input.nonce, pkce_verifier: input.verifier, require_pkce: true, request_opts: %{http_adapter: {__MODULE__, transport}}}

  defp refresh_keys(cfg, transport) do
    with {:ok, keys} <- get_json(cfg.jwks_url, transport), do: {:ok, JOSE.JWK.to_record(JOSE.JWK.from_map(keys))}
  end

  defp identity(cfg, %Oidcc.Token{id: %Oidcc.Token.Id{claims: claims}} = token, transport) do
    current_ms = System.system_time(:millisecond)
    current = div(current_ms, 1_000)

    access_expiry =
      case token.access do
        %Oidcc.Token.Access{expires: seconds} when is_integer(seconds) -> :atomics.get(transport.received_at, 1) + seconds * 1_000
        _ -> claims["exp"] * 1_000
      end

    expiry = min(claims["exp"] * 1_000, access_expiry)

    valid =
      valid_identity_claims?(claims, current) and
        claims["aud"] in [cfg.client_id, [cfg.client_id]] and
        expiry > current_ms and now() < transport.deadline

    if valid do
      {:ok, %{issuer: cfg.issuer, subject: claims["sub"], sid: claims["sid"], credential_expires_at_ms: expiry, tokens: %{id: token.id.token, access: token.access}}}
    else
      {:error, :forbidden}
    end
  end

  defp valid_identity_claims?(claims, current) do
    is_binary(claims["sub"]) and byte_size(claims["sub"]) > 0 and
      is_integer(claims["exp"]) and claims["exp"] > current and
      is_integer(claims["iat"]) and claims["iat"] <= current + 30 and
      (is_nil(claims["sid"]) or is_binary(claims["sid"]))
  end

  defp get_json(url, transport) do
    with {:ok, {{_, 200, _}, _, body}} <- request(:get, {url, []}, [], [], transport),
         {:ok, document} when is_map(document) <- Jason.decode(body) do
      {:ok, document}
    else
      {:error, reason} when reason in @reasons -> {:error, reason}
      _ -> {:error, :dependency_unavailable}
    end
  end

  @impl true
  def request(method, request, _http_opts, _request_opts, transport) do
    guarded(fn -> dispatch(method, request, transport) end)
  end

  defp dispatch(method, request, transport) do
    url = request |> elem(0) |> to_string()
    cfg = transport.config
    allowed = allowed_request?(method, url, cfg)

    cond do
      not allowed -> {:error, :forbidden}
      remaining(transport) <= 0 -> transport_error(method)
      method == :post and :atomics.add_get(transport.posts, 1, 1) != 1 -> {:error, :unknown_outcome}
      true -> perform(method, request, transport)
    end
  end

  defp allowed_request?(:get, url, cfg), do: url in [cfg.discovery_url, cfg.jwks_url]
  defp allowed_request?(:post, url, cfg), do: url == cfg.token_url
  defp allowed_request?(_, _, _), do: false

  defp perform(method, request, transport) do
    uri = request |> elem(0) |> to_string() |> URI.parse()
    tls = [timeout: remaining(transport), verify: :verify_peer]
    tls = if transport.config.tls_cacerts, do: Keyword.put(tls, :cacerts, transport.config.tls_cacerts), else: tls

    case Mint.HTTP1.connect(:https, uri.host, uri.port, mode: :passive, transport_opts: tls) do
      {:ok, conn} ->
        try do
          {headers, body} = request_parts(request)

          verb = method |> Atom.to_string() |> String.upcase()

          with true <- remaining(transport) > 0,
               :ok <-
                 :ssl.setopts(Mint.HTTP1.get_socket(conn),
                   send_timeout: remaining(transport),
                   send_timeout_close: true
                 ),
               true <- remaining(transport) > 0,
               {:ok, conn, ref} <- Mint.HTTP1.request(conn, verb, uri.path || "/", headers, body) do
            response = %{status: nil, headers: [], body: [], bytes: 0}
            receive_response(conn, ref, transport, method, response)
          else
            _ ->
              transport_error(method)
          end
        after
          Mint.HTTP1.close(conn)
        end

      _ ->
        transport_error(method)
    end
  end

  defp request_parts({_, headers}), do: {Enum.map(headers, fn {k, v} -> {to_string(k), IO.iodata_to_binary(v)} end), nil}

  defp request_parts({_, headers, content_type, body}) do
    {converted, _} = request_parts({nil, headers})
    {[{"content-type", to_string(content_type)} | converted], IO.iodata_to_binary(body)}
  end

  defp receive_response(conn, ref, transport, method, response) do
    socket = Mint.HTTP1.get_socket(conn)

    with true <- remaining(transport) > 0,
         {:ok, bytes} <- :ssl.recv(socket, 0, max(remaining(transport), 1)),
         true <- response.bytes + byte_size(bytes) <= @max_response,
         {:ok, conn, events} <- Mint.HTTP1.stream(conn, {:ssl, socket, bytes}) do
      response =
        Enum.reduce(events, %{response | bytes: response.bytes + byte_size(bytes)}, fn
          {:status, ^ref, status}, acc -> %{acc | status: status}
          {:headers, ^ref, headers}, acc -> %{acc | headers: acc.headers ++ headers}
          {:data, ^ref, body}, acc -> %{acc | body: [body | acc.body]}
          _, acc -> acc
        end)

      if {:done, ref} in events do
        finish(response, method, transport)
      else
        receive_response(conn, ref, transport, method, response)
      end
    else
      _ -> transport_error(method)
    end
  end

  defp finish(%{status: status} = response, method, transport) when status in 200..299 do
    received_at = System.system_time(:millisecond)
    body = response.body |> Enum.reverse() |> IO.iodata_to_binary()

    cond do
      method == :post and status not in [200, 201] ->
        transport_error(method)

      method == :post and not signed_token?(body, transport.config.allowed_algorithms) ->
        {:error, :forbidden}

      true ->
        headers = Enum.map(response.headers, fn {k, v} -> {String.to_charlist(k), String.to_charlist(v)} end)
        if method == :post, do: :atomics.put(transport.received_at, 1, received_at)
        {:ok, {{~c"HTTP/1.1", status, ~c""}, headers, body}}
    end
  end

  defp finish(%{status: 429}, _, _), do: {:error, :rate_limited}
  defp finish(_, method, _), do: transport_error(method)

  defp signed_token?(body, algorithms) do
    with {:ok, %{"id_token" => token}} when is_binary(token) and byte_size(token) <= 16_384 <- Jason.decode(body),
         [header, _, _] <- String.split(token, "."),
         {:ok, decoded} <- Base.url_decode64(header, padding: false),
         {:ok, %{"alg" => alg} = fields} <- Jason.decode(decoded) do
      alg in algorithms and Enum.all?(~w(jku x5u jwk x5c), &(not Map.has_key?(fields, &1)))
    else
      _ -> false
    end
  end

  defp transport_error(:post), do: {:error, :unknown_outcome}
  defp transport_error(_), do: {:error, :dependency_unavailable}
  defp now, do: System.monotonic_time(:millisecond)
  defp remaining(transport), do: transport.deadline - now()
end
