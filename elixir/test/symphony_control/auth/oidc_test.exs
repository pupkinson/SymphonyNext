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

  test "untrusted certificate and hostname are refused" do
    f = OidcFixture.start!()
    cfg = OidcFixture.config(f)
    assert {:error, :dependency_unavailable} == exchange(f, Map.put(cfg, :tls_cacerts, nil))
    assert OidcFixture.calls(f, :token) == 0
  end

  test "one absolute deadline includes discovery keys and token without renewal" do
    f = OidcFixture.start!(delay_ms: 200)
    start = System.monotonic_time(:millisecond)
    assert {:error, :unknown_outcome} == exchange(f, nil, 650)
    elapsed = System.monotonic_time(:millisecond) - start
    assert elapsed < 850
    assert OidcFixture.calls(f, :token) == 1
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
