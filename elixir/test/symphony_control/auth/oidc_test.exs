defmodule SymphonyControl.Auth.OidcTest do
  use ExUnit.Case, async: false
  import ExUnit.CaptureLog
  alias SymphonyControl.Auth.{Oidc, OidcFixture}
  @expectations %{nonce: String.duplicate("n", 43), verifier: String.duplicate("v", 43)}

  defp deadline(ms \\ 5_000), do: System.monotonic_time(:millisecond) + ms

  defp exchange(f, cfg \\ nil, ms \\ 5_000) do
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    Oidc.exchange(cfg || OidcFixture.config(f), code, @expectations, deadline(ms))
  end

  defp queued_exchange(f, expires) do
    cfg = OidcFixture.config(f)
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    caller = Task.async(fn -> Oidc.exchange(cfg, code, @expectations, expires) end)
    assert_receive {:jwks_waiting, provider}, 1_000
    :erlang.suspend_process(caller.pid)
    on_exit(fn -> if Process.alive?(caller.pid), do: :erlang.resume_process(caller.pid) end)
    {:links, links} = Process.info(caller.pid, :links)
    worker = Enum.find(links, &(&1 != self()))
    assert is_pid(worker)
    monitor = Process.monitor(worker)
    send(provider, :release_jwks)
    assert_receive {:DOWN, ^monitor, :process, ^worker, :normal}, 1_000
    {:messages, messages} = Process.info(caller.pid, :messages)

    identity =
      Enum.find_value(messages, fn
        {ref, {:ok, %{credential_expires_at_ms: expiry} = identity}} when is_reference(ref) and is_integer(expiry) ->
          identity

        _ ->
          nil
      end)

    assert is_map(identity)
    {caller, worker, identity}
  end

  test "HTTPS fixture is ready independently of missing product adapter" do
    f = OidcFixture.start!()
    assert {:ok, %{status: 200, body: %{"issuer" => issuer}}} = Req.get(f.origin <> "/discovery", connect_options: [transport_opts: [cacerts: [f.ca]]], retry: false)
    assert issuer == f.origin <> "/issuer"
    assert OidcFixture.calls(f, :discovery) == 1
  end

  test "authorization uses configured endpoints exact redirect scopes and S256" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    input = Map.put(@expectations, :state, String.duplicate("s", 43))
    assert {:ok, url} = Oidc.authorization_url(cfg, input, deadline())
    uri = URI.parse(url)
    params = URI.decode_query(uri.query)
    assert uri.path == "/authorize"
    assert params["redirect_uri"] == cfg.callback_uri
    assert params["response_type"] == "code"
    assert params["scope"] == "openid profile email"
    assert params["code_challenge_method"] == "S256"
    assert params["code_challenge"] == Base.url_encode64(:crypto.hash(:sha256, @expectations.verifier), padding: false)
    refute url =~ @expectations.verifier
    refute url =~ "synthetic-client-secret-canary"
  end

  test "exchange accepts exact signed issuer subject and S256 expectations without granting claims" do
    f = OidcFixture.start!()
    assert {:ok, identity} = exchange(f)
    assert identity.issuer == f.origin <> "/issuer"
    assert identity.subject == "human-1"
    assert identity.sid == "session-1"
    assert identity.credential_expires_at_ms > System.system_time(:millisecond)
    refute Map.has_key?(identity, :email)
    refute Map.has_key?(identity, :roles)
    assert OidcFixture.calls(f, :token) == 1
  end

  for fault <- [
        :wrong_issuer,
        :wrong_audience,
        :wrong_azp,
        :bad_signature,
        :alg_none,
        :disallowed_alg,
        :expired,
        :future_iat,
        :wrong_nonce,
        :empty_sub,
        :missing_sub,
        :jku_other_host,
        :encrypted_unsigned,
        :oversized_jwt
      ] do
    test "#{fault} never returns verified identity" do
      f = OidcFixture.start!(fault: unquote(fault))
      log = capture_log(fn -> assert {:error, :forbidden} == exchange(f) end)
      OidcFixture.record_log(f, log)
      assert :ok == OidcFixture.assert_no_secret_echo(f)
      refute log =~ "synthetic-client-secret-canary"
      refute log =~ "synthetic-access-canary"
      assert OidcFixture.calls(f, :token) == 1
    end
  end

  test "unknown kid refresh happens once without resending code" do
    for fault <- [:unknown_kid, :never_known_kid] do
      f = OidcFixture.start!(fault: fault)
      result = exchange(f)
      if fault == :unknown_kid, do: assert(match?({:ok, _}, result)), else: assert(result == {:error, :forbidden})
      assert OidcFixture.calls(f, :jwks) == 2
      assert OidcFixture.calls(f, :token) == 1
    end
  end

  test "DPoP nonce challenge permits at most one real token POST" do
    f = OidcFixture.start!(fault: :dpop_nonce)
    assert {:error, :unknown_outcome} == exchange(f)
    assert OidcFixture.calls(f, :token) == 1
  end

  test "lost token response is not retried" do
    f = OidcFixture.start!(fault: :lost_response)
    assert {:error, :unknown_outcome} == exchange(f, nil, 500)
    assert OidcFixture.calls(f, :token) == 1
  end

  test "foreign discovery endpoint issuer redirect and oversized response never reach token endpoint" do
    for fault <- [:foreign_endpoint, :wrong_discovery_issuer, :redirect, :oversized] do
      f = OidcFixture.start!(fault: fault)
      assert {:error, _} = exchange(f)
      assert OidcFixture.calls(f, :token) == 0
      assert OidcFixture.calls(f, :other) == 0
    end
  end

  test "plain PKCE is refused rather than downgraded" do
    f = OidcFixture.start!(pkce: :plain)
    assert {:error, :forbidden} == exchange(f)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "untrusted certificate is refused" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    assert {:error, :dependency_unavailable} == exchange(f, Map.put(cfg, :tls_cacerts, nil))
    assert OidcFixture.calls(f, :token) == 0
  end

  test "trusted CA with wrong SAN is independently refused before HTTP" do
    f = OidcFixture.start!(wrong_san: true)
    assert {:error, :dependency_unavailable} == exchange(f)
    assert OidcFixture.calls(f, :discovery) == 0
    assert OidcFixture.calls(f, :token) == 0
  end

  test "HTTP202 cannot disclose token material through stop or exception telemetry" do
    f = OidcFixture.start!(token_status: 202)
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    owner = self()
    handler = make_ref()
    events = [[:oidcc, :request_token, :stop], [:oidcc, :request_token, :exception]]
    callback = fn event, measurements, metadata, _ -> send(owner, {:token_event, event, measurements, metadata}) end
    :ok = :telemetry.attach_many(handler, events, callback, nil)
    on_exit(fn -> :telemetry.detach(handler) end)
    log = capture_log(fn -> assert {:error, _} = Oidc.exchange(OidcFixture.config(f), code, @expectations, deadline()) end)
    assert_receive {:token_event, [:oidcc, :request_token, :stop], _, metadata}
    telemetry = inspect(metadata, limit: :infinity)
    token = Agent.get(f.state, & &1.last_token)

    for payload <- [token, "synthetic-access-canary", "synthetic-client-secret-canary", code] do
      refute telemetry =~ payload
      refute log =~ payload
    end

    refute_receive {:token_event, [:oidcc, :request_token, :exception], _, _}
    assert OidcFixture.calls(f, :token) == 1
  end

  test "non UTF8 response header cannot expose real credentials through exception telemetry" do
    f = OidcFixture.start!(fault: :non_utf8_header)
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    owner = self()
    handler = make_ref()
    events = [[:oidcc, :request_token, :stop], [:oidcc, :request_token, :exception]]

    callback = fn event, _, metadata, _ -> send(owner, {:header_event, event, metadata}) end
    :ok = :telemetry.attach_many(handler, events, callback, nil)
    on_exit(fn -> :telemetry.detach(handler) end)
    log = capture_log(fn -> assert {:error, _} = Oidc.exchange(OidcFixture.config(f), code, @expectations, deadline()) end)
    assert_receive {:header_event, event, metadata}
    telemetry = inspect(metadata, limit: :infinity, printable_limit: :infinity)
    token = Agent.get(f.state, & &1.last_token)

    for canary <- [token, "synthetic-access-canary", "synthetic-client-secret-canary", code] do
      refute telemetry =~ canary
      refute log =~ canary
    end

    assert event == [:oidcc, :request_token, :stop]
    refute_receive {:header_event, [:oidcc, :request_token, :exception], _}
    assert OidcFixture.calls(f, :token) == 1
  end

  test "completed worker result queued until after deadline is refused and worker is gone" do
    f = OidcFixture.start!(hold_jwks: self())
    cfg = OidcFixture.config(f)
    input = Map.put(@expectations, :state, String.duplicate("s", 43))
    expires = deadline(1_000)
    caller = Task.async(fn -> Oidc.authorization_url(cfg, input, expires) end)
    assert_receive {:jwks_waiting, provider}, 700
    :erlang.suspend_process(caller.pid)
    on_exit(fn -> if Process.alive?(caller.pid), do: :erlang.resume_process(caller.pid) end)
    {:links, links} = Process.info(caller.pid, :links)
    worker = Enum.find(links, &(&1 != self()))
    monitor = Process.monitor(worker)
    send(provider, :release_jwks)
    assert_receive {:DOWN, ^monitor, :process, ^worker, :normal}, 700
    Process.sleep(max(expires - System.monotonic_time(:millisecond), 0) + 20)
    :erlang.resume_process(caller.pid)
    assert Task.await(caller) == {:error, :dependency_unavailable}
    refute Process.alive?(worker)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "successful exchange queued past credential expiry is refused before network deadline" do
    f = OidcFixture.start!(hold_jwks: self(), expires_in: 1)

    log =
      capture_log(fn ->
        expires = deadline()
        {caller, worker, identity} = queued_exchange(f, expires)
        Process.sleep(max(identity.credential_expires_at_ms - System.system_time(:millisecond), 0) + 30)
        assert identity.credential_expires_at_ms <= System.system_time(:millisecond)
        assert System.monotonic_time(:millisecond) < expires
        :erlang.resume_process(caller.pid)
        assert Task.await(caller) == {:error, :forbidden}
        assert OidcFixture.calls(f, :token) == 1
        refute Process.alive?(worker)
      end)

    OidcFixture.record_log(f, log)
    assert :ok == OidcFixture.assert_no_secret_echo(f)
  end

  test "successful exchange queued within credential lifetime remains accepted" do
    f = OidcFixture.start!(hold_jwks: self(), expires_in: 120)

    log =
      capture_log(fn ->
        expires = deadline()
        {caller, worker, identity} = queued_exchange(f, expires)
        assert identity.credential_expires_at_ms > System.system_time(:millisecond)
        assert System.monotonic_time(:millisecond) < expires
        :erlang.resume_process(caller.pid)
        assert {:ok, accepted} = Task.await(caller)
        assert accepted.subject == "human-1"
        assert accepted.credential_expires_at_ms > System.system_time(:millisecond)
        assert OidcFixture.calls(f, :token) == 1
        refute Process.alive?(worker)
      end)

    OidcFixture.record_log(f, log)
    assert :ok == OidcFixture.assert_no_secret_echo(f)
  end

  test "UTF8 Content-Type parameter preserves byte representation without credential telemetry" do
    f = OidcFixture.start!(fault: :utf8_content_type)
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    owner = self()
    handler = make_ref()
    events = [[:oidcc, :request_token, :stop], [:oidcc, :request_token, :exception]]
    callback = fn event, _, metadata, _ -> send(owner, {:utf8_event, event, metadata}) end
    :ok = :telemetry.attach_many(handler, events, callback, nil)
    on_exit(fn -> :telemetry.detach(handler) end)

    log =
      capture_log(fn ->
        result = Oidc.exchange(OidcFixture.config(f), code, @expectations, deadline())
        send(owner, {:utf8_exchange_result, result})
      end)

    assert_receive {:utf8_event, event, metadata}
    token = Agent.get(f.state, & &1.last_token)
    canaries = [token, "synthetic-access-canary", "synthetic-client-secret-canary", code]
    assert_no_canaries(metadata, canaries)
    assert_no_canaries(log, canaries)
    assert event == [:oidcc, :request_token, :stop]
    refute_receive {:utf8_event, [:oidcc, :request_token, :exception], _}
    assert_receive {:utf8_exchange_result, {:ok, %{subject: "human-1"}}}
    assert OidcFixture.calls(f, :token) == 1
  end

  defp assert_no_canaries(value, canaries) when is_binary(value) do
    for canary <- canaries,
        encoded <- [
          canary,
          Base.encode64(canary),
          Base.url_encode64(canary, padding: false),
          URI.encode_www_form(canary),
          Base.encode64("control-client:" <> canary)
        ],
        do: refute(value =~ encoded)

    case Jason.decode(value) do
      {:ok, decoded} when decoded != value -> assert_no_canaries(decoded, canaries)
      _ -> :ok
    end
  end

  defp assert_no_canaries(value, canaries) when is_list(value) do
    if Enum.all?(value, &is_integer/1) do
      case :unicode.characters_to_binary(value) do
        binary when is_binary(binary) -> assert_no_canaries(binary, canaries)
        {_, prefix, _} -> assert_no_canaries(prefix, canaries)
      end
    end

    Enum.each(value, &assert_no_canaries(&1, canaries))
  end

  defp assert_no_canaries(value, canaries) when is_tuple(value),
    do: value |> Tuple.to_list() |> assert_no_canaries(canaries)

  defp assert_no_canaries(value, canaries) when is_map(value),
    do: value |> Map.to_list() |> assert_no_canaries(canaries)

  defp assert_no_canaries(_, _), do: :ok

  test "structural scanner detects nested charlist and JSON-escaped canaries" do
    canary = "synthetic-scanner-canary"
    encoded = String.replace(Jason.encode!(%{"nested" => canary}), "synthetic", "\\u0073ynthetic")

    for value <- [
          %{reason: {:error, [String.to_charlist(canary)]}},
          %{stacktrace: [{__MODULE__, :synthetic, [encoded], []}]},
          %{nested: [{:basic, Base.encode64("control-client:" <> canary)}]}
        ] do
      assert_raise ExUnit.AssertionError, fn -> assert_no_canaries(value, [canary]) end
    end
  end

  for {variant, expected} <- [
        missing: :refused,
        empty: :refused,
        wrong: :refused,
        malformed: :refused,
        utf8_parameter: :accepted,
        json_suffix: :accepted
      ] do
    test "wire Content-Type #{variant} has typed #{expected} result and no disclosure" do
      assert_wire_exchange({:content_type, unquote(variant)}, unquote(expected))
    end
  end

  for field <- ~w(expires_in access_token refresh_token scope), variant <- [:string, :list, :map, :null] do
    expected =
      if (field in ~w(access_token refresh_token scope) and variant == :string) or
           (field == "scope" and variant == :list), do: :accepted, else: :refused

    test "wire #{field} #{variant} has typed #{expected} result and no disclosure" do
      assert_wire_exchange({:field, unquote(field), unquote(variant)}, unquote(expected))
    end
  end

  for variant <- [:string, :list, :map, :null, :empty, :missing] do
    test "wire id_token #{variant} refuses identity and does not disclose credentials" do
      assert_wire_exchange({:field, "id_token", unquote(variant)}, :refused)
    end
  end

  for variant <- [:string, :list, :map, :null] do
    test "wire token_type #{variant} remains accepted by existing contract without disclosure" do
      assert_wire_exchange({:field, "token_type", unquote(variant)}, :accepted)
    end
  end

  test "wire numeric string expiry remains accepted with signed token and refresh token" do
    assert_wire_exchange({:field, "expires_in", :numeric_string}, :accepted)
  end

  for {variant, expected} <- [
        malformed: :refused,
        escaped_canaries: :accepted,
        escaped_id_key: :accepted,
        large_integer: :accepted,
        float_overflow: :refused,
        lone_surrogate: :refused,
        duplicate_extension: :accepted,
        invalid_id_last: :accepted,
        valid_id_last: :refused
      ] do
    test "wire JSON #{variant} has typed #{expected} result and no disclosure" do
      assert_wire_exchange({:json, unquote(variant)}, unquote(expected))
    end
  end

  defp assert_wire_exchange(fault, expected) do
    f = OidcFixture.start!(wire_fault: fault)
    code = OidcFixture.issue_code(f, Map.to_list(@expectations))
    cfg = OidcFixture.config(f)
    owner = self()
    handler = make_ref()
    events = for phase <- [:start, :stop, :exception], do: [:oidcc, :request_token, phase]
    callback = fn event, measurements, metadata, _ -> send(owner, {handler, event, measurements, metadata}) end
    :ok = :telemetry.attach_many(handler, events, callback, nil)

    try do
      log = capture_log(fn -> send(owner, {handler, :result, Oidc.exchange(cfg, code, @expectations, deadline())}) end)
      assert_receive {^handler, :result, result}
      collected = collect_wire_events(handler)
      assert Enum.count(collected, &(elem(&1, 0) == [:oidcc, :request_token, :start])) == 1
      assert Enum.count(collected, &(elem(&1, 0) in [[:oidcc, :request_token, :stop], [:oidcc, :request_token, :exception]])) == 1
      %{wire_canaries: canaries, wire_body: body} = Agent.get(f.state, & &1)
      assert length(canaries) == 5
      assert OidcFixture.calls(f, :token) == 1
      assert_no_canaries(collected, canaries)
      assert_no_canaries(log, canaries)
      OidcFixture.record_log(f, log)
      assert :ok == OidcFixture.assert_no_secret_echo(f)
      assert_wire_result(result, expected)
      assert_decoder_controls(fault, body)
    after
      :telemetry.detach(handler)
    end
  end

  defp collect_wire_events(handler) do
    receive do
      {^handler, event, measurements, metadata} -> [{event, measurements, metadata} | collect_wire_events(handler)]
    after
      0 -> []
    end
  end

  defp assert_wire_result(result, :refused), do: assert(result == {:error, :forbidden})
  defp assert_wire_result(result, :accepted), do: assert(match?({:ok, %{subject: "human-1"}}, result))

  defp assert_decoder_controls({:json, variant}, body) do
    expected = variant not in [:malformed, :float_overflow, :lone_surrogate]
    assert match?({:ok, _}, Jason.decode(body)) == expected

    otp =
      try do
        :json.decode(body)
        :accepted
      rescue
        _ -> :refused
      end

    assert otp == :accepted == expected

    if variant in [:invalid_id_last, :valid_id_last] do
      {:ok, jason} = Jason.decode(body)
      assert :json.decode(body)["id_token"] == jason["id_token"]
      first = body |> String.split("\"id_token\":") |> Enum.at(1)
      assert String.starts_with?(first, Jason.encode!(jason["id_token"]))
    end
  end

  defp assert_decoder_controls(_, _), do: :ok

  test "timeout kills held protocol worker and discards its later completion" do
    f = OidcFixture.start!(hold_jwks: self())
    cfg = OidcFixture.config(f)
    input = Map.put(@expectations, :state, String.duplicate("s", 43))
    caller = Task.async(fn -> Oidc.authorization_url(cfg, input, deadline(700)) end)
    assert_receive {:jwks_waiting, provider}, 500
    {:links, links} = Process.info(caller.pid, :links)
    worker = Enum.find(links, &(&1 != self()))
    monitor = Process.monitor(worker)
    assert Task.await(caller) == {:error, :dependency_unavailable}
    assert_receive {:DOWN, ^monitor, :process, ^worker, :killed}
    send(provider, :release_jwks)
    refute Process.alive?(worker)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "invalid outgoing header is refused before any token request is sent" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    transport = %{config: cfg, deadline: deadline(), posts: :atomics.new(1, [])}
    request = {cfg.token_url, [{~c"x-invalid", ~c"canary\r\n"}], ~c"application/json", "{}"}
    assert {:error, :unknown_outcome} == Oidc.request(:post, request, [], [], transport)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "access lifetime elapsed during successful JWKS refresh is refused" do
    f = OidcFixture.start!(fault: :unknown_kid, expires_in: 1, refresh_delay_ms: 1_200)
    assert {:error, :forbidden} == exchange(f)
    assert OidcFixture.calls(f, :jwks) == 2
    assert OidcFixture.calls(f, :token) == 1
  end

  for seconds <- [0, -1] do
    test "unusable access lifetime #{seconds} refuses otherwise valid identity" do
      f = OidcFixture.start!(expires_in: unquote(seconds))
      assert {:error, :forbidden} == exchange(f)
      assert OidcFixture.calls(f, :token) == 1
    end
  end

  for fault <- [:additional_audience, :multi_audience_no_azp] do
    test "#{fault} is outside this client's audience policy" do
      f = OidcFixture.start!(fault: unquote(fault))
      assert {:error, :forbidden} == exchange(f)
      assert OidcFixture.calls(f, :token) == 1
    end
  end

  test "single approved audience does not require optional azp" do
    f = OidcFixture.start!(fault: :single_audience_no_azp)
    assert {:ok, %{subject: "human-1"}} = exchange(f)
    assert OidcFixture.calls(f, :token) == 1
  end

  test "one absolute deadline includes discovery keys and token without renewal" do
    f = OidcFixture.start!(delay_ms: 200)
    start = System.monotonic_time(:millisecond)
    assert {:error, :unknown_outcome} == exchange(f, nil, 650)
    elapsed = System.monotonic_time(:millisecond) - start
    assert elapsed < 850
    assert OidcFixture.calls(f, :token) == 1
  end

  test "staged connection dispatch and TLS handshake cannot produce a late POST" do
    f = OidcFixture.start!()
    cfg = OidcFixture.delayed_token_endpoint(f, 600, 700)
    started = System.monotonic_time(:millisecond)
    assert {:error, _} = exchange(f, cfg, 1_500)
    assert System.monotonic_time(:millisecond) - started < 1_700
    assert OidcFixture.calls(f, :tls_accept) == 1
    assert OidcFixture.calls(f, :tls_handshake) == 1
    Process.sleep(1_000)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "missing access lifetime uses signed ID expiry without extending it" do
    f = OidcFixture.start!(omit_expiry: true)
    assert {:ok, identity} = exchange(f)
    assert identity.credential_expires_at_ms <= System.system_time(:millisecond) + 120_000
    assert identity.credential_expires_at_ms > System.system_time(:millisecond)
  end

  test "malformed discovery documents and throttling fail closed before POST" do
    for fault <- [:invalid_json, :json_array, :rate_limited] do
      f = OidcFixture.start!(fault: fault)
      expected = if fault == :rate_limited, do: :rate_limited, else: :dependency_unavailable
      assert {:error, ^expected} = exchange(f)
      assert OidcFixture.calls(f, :token) == 0
    end
  end

  test "malformed provider keys are sanitized before token submission" do
    f = OidcFixture.start!(fault: :malformed_jwks)
    log = capture_log(fn -> assert {:error, :forbidden} == exchange(f) end)
    refute log =~ "synthetic-client-secret-canary"
    assert OidcFixture.calls(f, :token) == 0
  end

  test "invalid bounded input and expired deadline make no network calls" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    assert {:error, :invalid_request} == Oidc.exchange(cfg, String.duplicate("c", 4097), @expectations, deadline())
    assert {:error, :invalid_request} == Oidc.exchange(cfg, "code", %{}, deadline())
    assert {:error, :dependency_unavailable} == Oidc.exchange(cfg, "code", @expectations, deadline(-1))
    assert OidcFixture.calls(f, :discovery) == 0
  end

  test "transport refuses arbitrary destinations and a second POST before connecting" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    transport = %{config: cfg, deadline: deadline(), posts: :atomics.new(1, [])}
    assert {:error, :forbidden} == Oidc.request(:get, {"https://foreign.example/", []}, [], [], transport)
    assert {:error, :forbidden} == Oidc.request(:delete, {cfg.token_url, []}, [], [], transport)
    :atomics.put(transport.posts, 1, 1)
    assert {:error, :unknown_outcome} == Oidc.request(:post, {cfg.token_url, [], ~c"application/x-www-form-urlencoded", "code=consumed"}, [], [], transport)
    assert OidcFixture.calls(f, :token) == 0
  end

  test "missing or oversized secret references fail before exchanging a code" do
    for contents <- [nil, "", String.duplicate("s", 16_385)] do
      f = OidcFixture.start!()
      if contents == nil, do: File.rm!(f.secret_ref), else: File.write!(f.secret_ref, contents)
      assert {:error, :dependency_unavailable} == exchange(f)
      assert OidcFixture.calls(f, :token) == 0
    end
  end

  test "malformed expectation values are refused before transport" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    assert {:error, :invalid_request} == Oidc.exchange(cfg, "code", nil, deadline())
    assert {:error, :invalid_request} == Oidc.authorization_url(cfg, @expectations, deadline())
    assert OidcFixture.calls(f, :discovery) == 0
  end
end
