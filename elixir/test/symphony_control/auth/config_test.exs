defmodule SymphonyControl.Auth.ConfigTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Clock, Config, OidcFixture}

  test "operator bindings are exact and activation defaults closed" do
    f = OidcFixture.start!()
    assert {:ok, cfg} = Config.load(OidcFixture.bindings(f))
    assert cfg.issuer != cfg.discovery_url
    refute Config.activation_allowed?(cfg)
    refute Map.has_key?(cfg, :client_secret)
  end

  test "malformed unknown insecure and credential-valued input is rejected" do
    f = OidcFixture.start!()
    good = OidcFixture.bindings(f)

    bad = [
      nil,
      %{},
      Map.put(good, :issuer, "http://localhost"),
      Map.put(good, :token_url, "https://u:p@foreign.example/token"),
      Map.put(good, :allowed_algorithms, ["none"]),
      Map.put(good, :client_auth_method, "none"),
      Map.put(good, :callback_uri, "https://other.example/callback"),
      Map.put(good, :client_secret, "must-not-load"),
      Map.put(good, :tls_cacerts, []),
      Map.put(good, :host, "foreign.example")
    ]

    for input <- bad, do: assert({:error, :invalid_config} == Config.load(input))
  end

  test "clock reports stable boot epoch and a new epoch on restart" do
    {:ok, pid} = Clock.start_link([])
    first = Clock.now()
    second = Clock.now()
    assert byte_size(first.epoch) >= 32
    assert first.epoch == second.epoch
    assert first.monotonic_ms <= second.monotonic_ms
    assert is_integer(first.utc_ms)
    GenServer.stop(pid)
    {:ok, pid2} = Clock.start_link([])
    refute first.epoch == Clock.now().epoch
    GenServer.stop(pid2)
  end

  test "invalid URI encoding and ports return a sanitized config error" do
    f = OidcFixture.start!()

    for url <- ["https://localhost:invalid/token", <<255>>] do
      assert {:error, :invalid_config} == Config.load(Map.put(OidcFixture.bindings(f), :token_url, url))
    end
  end
end
