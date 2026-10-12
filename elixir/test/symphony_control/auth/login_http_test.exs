defmodule SymphonyControl.Auth.LoginHttpTest do
  use ExUnit.Case, async: false
  alias __MODULE__.TransportFailure
  alias SymphonyControl.Auth.{Access, Clock, Login, OidcFixture, Store}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Repo}

  defmodule TransportFailure do
    alias Plug.Adapters.Test.Conn
    def read_req_body(_, _), do: exit(:synthetic_transport_failure)
    def send_resp(payload, status, headers, body), do: Conn.send_resp(payload, status, headers, body)
  end

  test "unreachable provider differs from accepted code with lost response and never retries" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    stop_supervised!(f.provider.server_id)
    response = AuthHttpFixture.callback(f, flow: flow)
    assert response.status == 503
    assert is_nil(AuthHttpFixture.cookie(response, "__Host-symphony-control"))
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
    assert Agent.get(f.provider.state, &Map.get(&1, :accepted_codes, 0)) == 0
    assert Agent.get(f.provider.state, &map_size(&1.codes)) == 1
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]
  end

  test "unknown session COMMIT yields no cookie and confirmed flow consumption is retained" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    Repo.query!("CREATE FUNCTION delay_commit() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN PERFORM pg_sleep(2); RETURN NEW; END'", [], log: false)
    Repo.query!("CREATE CONSTRAINT TRIGGER session_commit_delay AFTER INSERT ON control_auth_sessions DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION delay_commit()", [], log: false)
    started = System.monotonic_time(:millisecond)
    reply = AuthHttpFixture.callback(f, flow: flow)
    assert System.monotonic_time(:millisecond) - started < 2000
    assert reply.status == 503
    assert is_nil(AuthHttpFixture.cookie(reply, "__Host-symphony-control"))
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert OidcFixture.calls(f.provider, :token) == 1
    Repo.query!("DROP TRIGGER session_commit_delay ON control_auth_sessions", [], timeout: 3000, log: false)
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]
    assert AuthHttpFixture.counts(f).sessions == 0
  end

  test "unconfirmed pending insertion cannot issue redirect or browser binding" do
    f = AuthHttpFixture.start!()
    Repo.query!("CREATE FUNCTION delay_commit() RETURNS trigger LANGUAGE plpgsql AS 'BEGIN PERFORM pg_sleep(2); RETURN NEW; END'", [], log: false)
    Repo.query!("CREATE CONSTRAINT TRIGGER flow_commit_delay AFTER INSERT ON control_auth_pending_logins DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION delay_commit()", [], log: false)
    started = System.monotonic_time(:millisecond)
    response = AuthHttpFixture.get(f, "/auth/login")
    assert System.monotonic_time(:millisecond) - started < 1100
    assert response.status == 503
    assert Req.Response.get_header(response, "location") == []
    assert is_nil(AuthHttpFixture.cookie(response, "__Host-symphony-browser"))
    Repo.query!("DROP TRIGGER flow_commit_delay ON control_auth_pending_logins", [], timeout: 3000, log: false)
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows == [[0]]
  end

  defmodule CandidateAuthorizer do
    def authorize(%SymphonyControl.Auth.Actor{}, :runtime_identity_read), do: :ok
    def authorize(_, _), do: :deny
  end

  defmodule PermissiveAuthorizer do
    def authorize(_, _), do: :ok
  end

  test "missing actor cannot disclose identity even through a permissive domain seam" do
    f = AuthHttpFixture.start!(runtime_identity_authorizer: PermissiveAuthorizer)
    assert AuthHttpFixture.get(f, "/api/v1/control/identity?current_actor=admin").status == 403
  end

  @tag capture_log: true
  test "invalid server config preserves public health and denies auth and protected reads" do
    f = AuthHttpFixture.start!(router_config: %SymphonyControl.Auth.Config{})
    assert AuthHttpFixture.get(f, "/health/live").status == 200
    assert AuthHttpFixture.get(f, "/auth/login").status == 403
    assert AuthHttpFixture.get(f, "/api/v1/control/identity").status == 403
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "a real committed handle queued beyond credential expiry is never released" do
    f = AuthHttpFixture.start!(expires_in: 1)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    owner = self()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :hold_jwks, owner)})
    browser = flow.cookie |> String.split("=", parts: 2) |> List.last()
    caller = Task.async(fn -> Login.finish(f.config, flow.params["code"], flow.params["state"], browser, nil, Clock.now()) end)
    assert_receive {:jwks_waiting, provider}, 2000
    :erlang.suspend_process(caller.pid)
    on_exit(fn -> if Process.alive?(caller.pid), do: :erlang.resume_process(caller.pid) end)
    {:links, links} = Process.info(caller.pid, :links)
    worker = Enum.find(links, &(&1 != self()))
    monitor = Process.monitor(worker)
    send(provider, :release_jwks)
    assert_receive {:DOWN, ^monitor, :process, ^worker, :normal}, 2000
    [[expiry]] = Repo.query!("SELECT expires_at_ms FROM control_auth_sessions", [], log: false).rows
    Process.sleep(max(expiry - System.system_time(:millisecond), 0) + 2)
    :erlang.resume_process(caller.pid)
    assert {:error, :forbidden} = Task.await(caller, 6000)
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]
  end

  test "untrusted clocks invalid config and malformed browser cannot insert a pending flow" do
    f = AuthHttpFixture.start!()
    clock = Clock.now()

    for invalid <- [
          %{clock | sample_valid: false},
          %{clock | native_unit: 1},
          %{clock | native_clock: self()},
          %{clock | native_anchor: System.monotonic_time() + 1_000_000_000},
          %{clock | epoch: "other"},
          %{}
        ] do
      assert {:error, :forbidden} = Login.begin(f.config, nil, invalid)
    end

    assert {:error, :forbidden} = Login.begin(nil, nil, clock)
    assert {:error, :forbidden} = Login.begin(%{f.config | callback_uri: nil}, nil, clock)
    assert {:error, :invalid_request} = Login.begin(f.config, "malformed", clock)
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows == [[0]]
  end

  test "second browser login rotates the committed handle and keeps tokens private" do
    f = AuthHttpFixture.start!()
    first = AuthHttpFixture.login!(f)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    response = AuthHttpFixture.callback(f, flow: flow, cookie: flow.cookie <> "; " <> first.cookie)
    assert response.status == 303
    second = AuthHttpFixture.cookie(response, "__Host-symphony-control")
    refute second == first.cookie
    old_handle = first.cookie |> String.split("=", parts: 2) |> List.last()
    handle = second |> String.split("=", parts: 2) |> List.last()
    assert {:error, :forbidden} = Store.local_actor(f.config, old_handle, Clock.now())
    assert {:ok, _} = Store.local_actor(f.config, handle, Clock.now())
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
    [[encrypted]] = Repo.query!("SELECT tokens_ciphertext FROM control_auth_sessions WHERE revoked_at_ms IS NULL", [], log: false).rows
    refute :binary.match(encrypted, "synthetic-access-canary") != :nomatch
    assert AuthHttpFixture.counts(f) == %{exchanges: 2, sessions: 2}
    assert Agent.get(f.provider.state, & &1.accepted_codes) == 2
  end

  for fault <- [:wrong_nonce, :wrong_issuer, :wrong_audience, :bad_signature, :expired] do
    test "library verification rejects #{fault} after one real exchange without cookie or echo" do
      f = AuthHttpFixture.start!(fault: unquote(fault))
      flow = AuthHttpFixture.login!(f, phase: :begin)

      log =
        ExUnit.CaptureLog.capture_log(fn ->
          reply = AuthHttpFixture.callback(f, flow: flow)
          assert reply.status == 403
          assert is_nil(AuthHttpFixture.cookie(reply, "__Host-symphony-control"))
          refute Jason.encode!(reply.body) =~ flow.params["code"]
          refute Jason.encode!(reply.body) =~ "synthetic-access-canary"
        end)

      refute log =~ flow.params["code"]
      refute log =~ "synthetic-client-secret-canary"
      refute log =~ "synthetic-access-canary"
      token = Agent.get(f.provider.state, & &1.last_token)
      refute log =~ token
      assert AuthHttpFixture.callback(f, flow: flow).status == 403
      assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 0}
    end
  end

  test "signed email and admin claims do not register an unknown local identity" do
    f = AuthHttpFixture.start!()
    Repo.query!("DELETE FROM control_auth_identities", [], log: false)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 0}
    assert Repo.query!("SELECT count(*) FROM control_auth_identities", [], log: false).rows == [[0]]
  end

  test "state config and expired flow checks precede exchange and preserve valid state" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    assert AuthHttpFixture.callback(f, flow: flow, params: %{"state" => String.duplicate("s", 43)}).status == 403
    cfg = %{f.config | generation: "other-generation"}
    browser = flow.cookie |> String.split("=", parts: 2) |> List.last()
    assert {:error, :forbidden} = Login.finish(cfg, flow.params["code"], flow.params["state"], browser, nil, Clock.now())
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NULL", [], log: false).rows == [[1]]
    advance_clock(f, 300_000)
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "shared five second deadline bounds a multi-stage provider without issuing session" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :delay_ms, 1800)})
    started = System.monotonic_time(:millisecond)
    response = AuthHttpFixture.callback(f, flow: flow)
    elapsed = System.monotonic_time(:millisecond) - started
    assert elapsed >= 4500 and elapsed < 5500
    assert response.status == 503
    assert is_nil(AuthHttpFixture.cookie(response, "__Host-symphony-control"))
    assert AuthHttpFixture.counts(f).sessions == 0
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.delete(&1.opts, :delay_ms)})
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert AuthHttpFixture.counts(f).exchanges <= 1
  end

  test "bounded login and callback counters refuse before expensive calls and cleanup preserves flow TTL" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    for _ <- 1..5, do: assert(AuthHttpFixture.get(f, "/auth/login", cookie: flow.cookie).status == 303)
    limited = AuthHttpFixture.get(f, "/auth/login", cookie: flow.cookie)
    assert limited.status == 429
    assert Req.Response.get_header(limited, "cache-control") == ["no-store"]

    for _ <- 1..54 do
      cookie = "__Host-symphony-browser=" <> Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
      assert AuthHttpFixture.get(f, "/auth/login", cookie: cookie).status == 303
    end

    for _ <- 1..1001 do
      cookie = "__Host-symphony-browser=" <> Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
      assert AuthHttpFixture.get(f, "/auth/login", cookie: cookie).status == 429
    end

    assert map_size(:sys.get_state(SymphonyControl.Auth.RateLimiter)) <= 62
    for _ <- 1..120, do: assert(AuthHttpFixture.get(f, "/auth/callback").status == 400)
    assert AuthHttpFixture.get(f, "/auth/backchannel-logout", method: :post).status == 429
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
    :sys.replace_state(SymphonyControl.Auth.RateLimiter, fn counters -> Map.new(counters, fn {key, {_, n}} -> {key, {System.monotonic_time(:millisecond) - 1, n}} end) end)
    advance_clock(f, 300_000)
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert map_size(:sys.get_state(SymphonyControl.Auth.RateLimiter)) == 1
    assert Repo.query!("SELECT bool_and(expires_at_ms = issued_at_ms + 300000) FROM control_auth_pending_logins", [], log: false).rows == [[true]]
  end

  test "missing limiter and insecure ingress refuse; bounded code and state never reach exchange" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)

    for params <- [%{"code" => ""}, %{"code" => String.duplicate("x", 4097)}, %{"state" => String.duplicate("x", 257)}] do
      assert AuthHttpFixture.callback(f, flow: flow, params: params).status == 400
    end

    conn = Plug.Test.conn(:get, "/auth/login") |> SymphonyControl.Router.call(SymphonyControl.Router.init(auth: f.config))
    assert conn.status == 403
    stop_supervised!(SymphonyControl.Auth.RateLimiter)
    assert AuthHttpFixture.get(f, "/auth/login").status == 503
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "default Access denies even a valid session and clears a forged server assignment" do
    f = AuthHttpFixture.start!(default_access: true, runtime_identity_authorizer: CandidateAuthorizer)
    session = AuthHttpFixture.login!(f)
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 0
    conn = Plug.Test.conn(:get, "/api/v1/control/identity") |> Plug.Conn.assign(:current_actor, :operator) |> SymphonyControl.Router.call(SymphonyControl.Router.init(auth: f.config))
    assert conn.status == 403
    assert conn.assigns.current_actor == nil
  end

  for failure <- [:raise, :throw, :exit, :unknown, :denied] do
    test "wire callback #{failure} fails closed with no actor or secret details" do
      f =
        AuthHttpFixture.start!(
          runtime_identity_authorizer: CandidateAuthorizer,
          after_wire: fn _, _, _, _, _ ->
            case unquote(failure) do
              :raise -> raise("SYNTHETIC-ELIGIBILITY-CANARY")
              :throw -> throw("SYNTHETIC-ELIGIBILITY-CANARY")
              :exit -> exit("SYNTHETIC-ELIGIBILITY-CANARY")
              :unknown -> {:ok, :permitted}
              :denied -> {:error, :forbidden}
            end
          end
        )

      session = AuthHttpFixture.login!(f)
      response = AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie)
      assert response.status == 403
      refute Jason.encode!(response.body) =~ "SYNTHETIC-ELIGIBILITY-CANARY"
      assert OidcFixture.calls(f.provider, :eligibility) == 1
    end
  end

  test "expiry after a wire confirmation cannot turn a queued candidate into an actor" do
    owner = self()

    f =
      AuthHttpFixture.start!(
        after_wire: fn _, _, _, _, result ->
          send(owner, {:wire_confirmed, self()})

          receive do
            :continue -> result
          end
        end
      )

    session = AuthHttpFixture.login!(f)
    handle = session.cookie |> String.split("=", parts: 2) |> List.last()
    caller = Task.async(fn -> Access.authenticate(f.config, handle, Clock.now()) end)
    assert_receive {:wire_confirmed, worker}, 2000
    :erlang.suspend_process(caller.pid)
    on_exit(fn -> if Process.alive?(caller.pid), do: :erlang.resume_process(caller.pid) end)
    monitor = Process.monitor(worker)
    send(worker, :continue)
    assert_receive {:DOWN, ^monitor, :process, ^worker, :normal}, 2000
    advance_clock(f, 120_001)
    :erlang.resume_process(caller.pid)
    assert {:error, :forbidden} = Task.await(caller, 6000)
    assert OidcFixture.calls(f.provider, :eligibility) == 1
  end

  test "owned TLS ingress is ready before product login assertions" do
    f = AuthHttpFixture.start!()
    assert AuthHttpFixture.get(f, "/health/live").status == 200
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "concurrent real callbacks consume once before one exchange and session" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    responses = 1..2 |> Enum.map(fn _ -> Task.async(fn -> AuthHttpFixture.callback(f, flow: flow) end) end) |> Enum.map(&Task.await(&1, 7000))
    assert Enum.count(responses, &(&1.status == 303)) == 1
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]
  end

  test "foreign browser cannot consume legitimate flow" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    cookie = "__Host-symphony-browser=" <> Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
    assert AuthHttpFixture.callback(f, flow: flow, cookie: cookie).status == 403
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
    assert AuthHttpFixture.callback(f, flow: flow).status == 303
  end

  @tag capture_log: true
  test "provider accepts code then disconnects; consumed code is never exchanged again" do
    f = AuthHttpFixture.start!(fault: :disconnect_after_accept)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    first = AuthHttpFixture.callback(f, flow: flow)
    assert first.status == 503
    assert is_nil(AuthHttpFixture.cookie(first, "__Host-symphony-control"))
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 0}
    assert Agent.get(f.provider.state, &map_size(&1.codes)) == 0
    assert Agent.get(f.provider.state, & &1.accepted_codes) == 1
  end

  test "TLS login uses exact redirect S256 scopes secure cookies and fixed final location" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin, headers: [{"host", "external.invalid"}, {"x-forwarded-host", "evil.invalid"}])
    location = hd(Req.Response.get_header(flow.response, "location")) |> URI.parse()
    params = URI.decode_query(location.query)
    assert params["redirect_uri"] == f.config.callback_uri
    assert params["code_challenge_method"] == "S256"
    assert params["scope"] == "openid profile email"
    assert byte_size(params["state"]) >= 43
    assert byte_size(params["nonce"]) >= 43
    response = AuthHttpFixture.callback(f, flow: flow)
    assert response.status == 303
    assert Req.Response.get_header(response, "location") == ["/"]

    for reply <- [flow.response, response], header <- Req.Response.get_header(reply, "set-cookie") do
      assert String.contains?(header, "secure")
      assert String.contains?(header, "HttpOnly")
      assert String.contains?(header, "SameSite=Lax")
      assert String.contains?(header, "path=/")
      refute String.contains?(String.downcase(header), "domain=")
    end

    assert OidcFixture.calls(f.provider, :token) == 1
    handle = AuthHttpFixture.cookie(response, "__Host-symphony-control") |> String.split("=", parts: 2) |> List.last()
    assert byte_size(Base.url_decode64!(handle, padding: false)) >= 32
    assert {:ok, _} = Store.local_actor(f.config, handle, Clock.now())
  end

  test "methods, unknown paths, malformed callbacks and body bound refuse without exchange" do
    f = AuthHttpFixture.start!()

    for {path, method, allow} <- [{"/auth/login", :post, "GET"}, {"/auth/callback", :post, "GET"}, {"/auth/logout", :get, "POST"}, {"/auth/backchannel-logout", :get, "POST"}] do
      response = AuthHttpFixture.get(f, path, method: method)
      assert response.status == 405
      assert Req.Response.get_header(response, "allow") == [allow]
    end

    assert AuthHttpFixture.get(f, "/auth/unknown").status == 404

    for path <- ["/auth/callback", "/auth/callback?code=x&state=x", "/auth/logout", "/auth/backchannel-logout"] do
      method = if path in ["/auth/logout", "/auth/backchannel-logout"], do: :post, else: :get
      response = AuthHttpFixture.get(f, path, method: method)
      assert response.status in [400, 403]
      assert Req.Response.get_header(response, "cache-control") == ["no-store"]
    end

    assert AuthHttpFixture.get(f, "/auth/callback", body: String.duplicate("x", 32_769)).status == 400
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "transport adapter loss and missing Clock refuse auth without publishing secrets or handles" do
    f = AuthHttpFixture.start!()
    conn = Plug.Test.conn(:post, "/auth/logout")
    {_, payload} = conn.adapter
    conn = %{conn | scheme: :https, adapter: {TransportFailure, payload}, private: %{control_auth: f.config}}

    for handler <- [:login, :callback, :logout, :backchannel_logout] do
      reply = apply(SymphonyControl.Auth.Controller, handler, [conn, %{}])
      assert reply.status == 503
      assert Jason.decode!(reply.resp_body) == %{"error" => "dependency_unavailable"}
      assert Plug.Conn.get_resp_header(reply, "set-cookie") == []
    end

    clock = Clock.now()
    stop_supervised!(AuthDbFixture.SnapshotClock)
    assert AuthHttpFixture.get(f, "/auth/login").status == 503
    assert AuthHttpFixture.get(f, "/auth/callback").status == 503
    assert AuthHttpFixture.get(f, "/api/v1/control/identity").status == 403
    assert {:error, :dependency_unavailable} = Login.begin(f.config, nil, clock)
    assert {:error, :forbidden} = Access.authenticate(nil, "unknown", clock)
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  test "wire-confirmed candidate loses Repo before caller acceptance and becomes fixed unavailable" do
    owner = self()

    f =
      AuthHttpFixture.start!(
        after_wire: fn _, _, _, _, result ->
          send(owner, {:candidate_wire_ready, self()})

          receive do
            :continue -> result
          end
        end
      )

    session = AuthHttpFixture.login!(f)
    request = Task.async(fn -> AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie) end)
    assert_receive {:candidate_wire_ready, worker}, 2000
    :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
    send(worker, :continue)
    reply = Task.await(request, 6000)
    assert reply.status == 503
    assert reply.body == %{"error" => "dependency_unavailable"}
    assert OidcFixture.calls(f.provider, :eligibility) == 1
  end

  test "wire-confirmed candidate loses Clock before acceptance and stays forbidden" do
    owner = self()

    f =
      AuthHttpFixture.start!(
        after_wire: fn _, _, _, _, result ->
          send(owner, {:candidate_wire_ready, self()})

          receive do
            :continue -> result
          end
        end
      )

    session = AuthHttpFixture.login!(f)
    request = Task.async(fn -> AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie) end)
    assert_receive {:candidate_wire_ready, worker}, 2000
    stop_supervised!(AuthDbFixture.SnapshotClock)
    send(worker, :continue)
    assert Task.await(request, 6000).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 1
  end

  test "slow wire confirmation uses the original bounded budget and kills its own worker" do
    owner = self()

    f =
      AuthHttpFixture.start!(
        after_wire: fn _, _, _, _, result ->
          send(owner, {:slow_wire, self()})

          receive do
            :never -> result
          after
            5000 -> result
          end
        end
      )

    session = AuthHttpFixture.login!(f)
    started = System.monotonic_time(:millisecond)
    request = Task.async(fn -> AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie) end)
    assert_receive {:slow_wire, worker}, 2000
    monitor = Process.monitor(worker)
    reply = Task.await(request, 6000)
    assert reply.status == 503
    assert System.monotonic_time(:millisecond) - started < 4500
    assert_receive {:DOWN, ^monitor, :process, ^worker, :killed}, 1000
    assert OidcFixture.calls(f.provider, :eligibility) == 1
  end

  defp advance_clock(f, ms) do
    clock = Clock.now()
    AuthDbFixture.set_clock!(f.db, %{clock | utc_ms: clock.utc_ms + ms, monotonic_ms: clock.monotonic_ms + ms})
  end
end
