defmodule SymphonyControl.Auth.LogoutHttpTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, Clock, Logout, Oidc, OidcFixture, RequestContext, Store}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Repo}

  defp fixture(opts \\ []) do
    f = AuthHttpFixture.start!([task4: true] ++ opts)
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
    login = AuthHttpFixture.login!(f)
    {f, login, "/api/v1/projects/" <> project}
  end

  defp local(f, login, opts \\ []) do
    token = AuthHttpFixture.cookie(login.response, "__Host-symphony-csrf")
    value = if token, do: token |> String.split("=", parts: 2) |> List.last(), else: ""
    headers = Keyword.get(opts, :headers, [{"origin", f.origin}, {"x-csrf-token", value}])
    AuthHttpFixture.get(f, "/auth/logout", method: :post, cookie: login.cookie, headers: headers)
  end

  defp backchannel(f, jwt, opts \\ []) do
    body = Keyword.get(opts, :body, URI.encode_query(%{"logout_token" => jwt}))
    headers = Keyword.get(opts, :headers, [{"content-type", "application/x-www-form-urlencoded"}])
    AuthHttpFixture.get(f, URI.parse(f.config.backchannel_uri).path, method: :post, body: body, headers: headers)
  end

  test "legitimate CSRF issuance permits confirmed local logout and exact token-free RP redirect" do
    {f, login, path} = fixture(post_logout_path: "/signed-out")
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    refute is_nil(AuthHttpFixture.cookie(login.response, "__Host-symphony-csrf"))
    response = local(f, login)
    assert response.status == 303
    [location] = Req.Response.get_header(response, "location")
    uri = URI.parse(location)
    assert %{uri | query: nil} |> URI.to_string() == f.config.end_session_url
    assert URI.decode_query(uri.query) == %{"client_id" => f.config.client_id, "post_logout_redirect_uri" => f.config.post_logout_uri}
    refute location =~ "id_token"
    refute location =~ "synthetic-access"
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
    assert Enum.any?(Req.Response.get_header(response, "set-cookie"), &(&1 =~ "__Host-symphony-control=" and &1 =~ "max-age=0"))
  end

  test "missing bad duplicate CSRF foreign Origin and GET never revoke" do
    {f, login, _path} = fixture()

    for headers <- [
          [],
          [{"origin", f.origin}],
          [{"origin", f.origin}, {"x-csrf-token", "wrong"}],
          [{"origin", "https://foreign.invalid"}, {"x-csrf-token", "wrong"}],
          [{"origin", f.origin}, {"origin", f.origin}, {"x-csrf-token", "wrong"}]
        ] do
      assert local(f, login, headers: headers).status == 403
    end

    assert AuthHttpFixture.get(f, "/auth/logout", cookie: login.cookie).status == 405
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[0]]
    assert local(f, login).status == 303
  end

  test "IdP outage cannot prevent local revoke or restore the old cookie" do
    {f, login, path} = fixture()
    stop_supervised!(f.provider.server_id)
    assert local(f, login).status == 303
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
  end

  test "signed backchannel commits its exact session effect and replay record once" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    jwt = OidcFixture.logout_token(f.provider)
    assert backchannel(f, jwt).status == 200
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert backchannel(f, jwt).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[1]]
    assert Repo.query!("SELECT retain_until_ms-issued_at_ms >= 3600000 FROM control_auth_logout_jtis", [], log: false).rows == [[true]]
  end

  test "foreign and malformed signed claims and algorithms do not mutate any session" do
    {f, _login, _path} = fixture()
    now = System.system_time(:second)

    for {claims, opts} <- [
          {%{"iss" => "https://foreign.invalid/issuer"}, []},
          {%{"aud" => "foreign"}, []},
          {%{"aud" => ["control-client", "foreign"]}, []},
          {%{"iat" => now - 301}, []},
          {%{"iat" => now + 600}, []},
          {%{"iat" => "bad"}, []},
          {%{"exp" => now}, []},
          {%{"nbf" => now + 600}, []},
          {%{"jti" => ""}, []},
          {%{"nonce" => nil}, []},
          {%{"events" => %{}}, []},
          {%{"events" => %{"http://schemas.openid.net/event/backchannel-logout" => true}}, []},
          {%{"sid" => "", "sub" => nil}, []},
          {%{}, [drop: ["sid", "sub"]]},
          {%{}, [drop: ["exp"]]},
          {%{}, [fault: :bad_signature]},
          {%{}, [fault: :alg_none]},
          {%{}, [fault: :disallowed_alg]},
          {%{}, [fault: :jku_other_host]}
        ] do
      assert backchannel(f, OidcFixture.logout_token(f.provider, claims, opts)).status in [400, 403],
             "claim fields #{inspect(Map.keys(claims))}, fault #{inspect(opts)}, elapsed seconds #{System.system_time(:second) - now}"
    end

    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[0]]
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[0]]
    assert backchannel(f, OidcFixture.logout_token(f.provider)).status == 200
  end

  test "signed body is required and duplicate token cannot select arbitrary authority" do
    {f, _login, _path} = fixture()
    jwt = OidcFixture.logout_token(f.provider)

    for body <- [
          "",
          URI.encode_query(%{"unrelated" => jwt}),
          URI.encode_query(%{"logout_token" => jwt}) <> "&logout_token=" <> URI.encode_www_form(jwt),
          URI.encode_query(%{"logout_token" => jwt}) <> "&%6Cogout_token=x",
          URI.encode_query(%{"logout_token" => String.duplicate("x", 16_385)})
        ] do
      assert backchannel(f, jwt, body: body).status in [400, 403]
    end

    assert backchannel(f, jwt, body: "", headers: [{"authorization", "Bearer " <> jwt}]).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[0]]
  end

  test "CSRF from a replaced session cannot revoke its successor" do
    {f, first, _path} = fixture()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    second_response = AuthHttpFixture.callback(f, flow: flow, cookie: flow.cookie <> "; " <> first.cookie)
    second = %{cookie: AuthHttpFixture.cookie(second_response, "__Host-symphony-control"), response: second_response}
    old_token = AuthHttpFixture.cookie(first.response, "__Host-symphony-csrf") |> String.split("=", parts: 2) |> List.last()
    assert local(f, second, headers: [{"origin", f.origin}, {"x-csrf-token", old_token}]).status == 403
    assert local(f, second).status == 303
  end

  test "unknown local COMMIT is never success and is reconciled without a second mutation" do
    {f, login, _path} = fixture()
    ref = AuthDbFixture.barrier!("COMMIT")
    request = Task.async(fn -> local(f, login) end)
    assert_receive {:query_result_held, ^ref, worker}, 2000
    reply = Task.await(request, 2000)
    assert reply.status == 503
    send(worker, {:release_query, ref})
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
    assert local(f, login).status == 403
  end

  test "RP user-agent session confirmation is separate from a backend GET or local commit" do
    {f, login, path} = fixture(post_logout_path: "/account/session-ended")
    local_response = local(f, login)
    assert local_response.status == 303
    assert OidcFixture.calls(f.provider, :logout) == 0
    [location] = Req.Response.get_header(local_response, "location")
    options = AuthHttpFixture.request_options(f)
    assert Req.get!(location, options).status == 400
    assert Agent.get(f.provider.state, & &1.op_active)
    browser = Req.get!(location, [headers: [{"cookie", login.provider_cookie}]] ++ options)
    assert browser.status == 200
    assert browser.body == %{"confirmation_required" => true}
    assert Agent.get(f.provider.state, & &1.op_active)
    params = location |> URI.parse() |> Map.fetch!(:query) |> URI.decode_query() |> Map.put("confirm", "yes")
    confirmed = Req.post!(f.config.end_session_url, [form: params, headers: [{"cookie", login.provider_cookie}]] ++ options)
    assert confirmed.status == 303
    assert Req.Response.get_header(confirmed, "location") == [f.config.post_logout_uri]
    refute Agent.get(f.provider.state, & &1.op_active)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
  end

  for selector <- [:intersection, :subject, :sid] do
    @selector selector
    test "verified #{@selector} selectors stay within the exact issuer and binding" do
      {f, login, _path} = fixture()
      [_, first] = String.split(login.cookie, "=", parts: 2)
      assert {:ok, actor} = Store.local_actor(f.config, first, Clock.now())
      assert {:ok, material} = Store.session_material(f.config, actor, Clock.now())
      AuthDbFixture.seed_user!(f.db, subject: "human-2")
      base = %{issuer: f.config.issuer, subject: "human-1", sid: "session-1", credential_expires_at_ms: Clock.now().utc_ms + 120_000, tokens: material.tokens}
      assert {:ok, same_subject_other_sid} = Store.open_session(f.config, %{base | sid: "other-sid"}, nil, Clock.now())
      assert {:ok, other_subject_same_sid} = Store.open_session(f.config, %{base | subject: "human-2"}, nil, Clock.now())

      drop =
        case @selector do
          :intersection -> []
          :subject -> ["sid"]
          :sid -> ["sub"]
        end

      assert backchannel(f, OidcFixture.logout_token(f.provider, %{}, drop: drop)).status == 200
      assert {:error, :forbidden} = Store.local_actor(f.config, first, Clock.now())
      other_sid = Store.local_actor(f.config, same_subject_other_sid, Clock.now())
      other_sub = Store.local_actor(f.config, other_subject_same_sid, Clock.now())
      assert match?({:error, :forbidden}, other_sid) == (@selector == :subject)
      assert match?({:error, :forbidden}, other_sub) == (@selector == :sid)
      assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[1]]
    end
  end

  test "a signed foreign subject has no session effect and a replay survives control restart" do
    {f, login, _path} = fixture()
    jwt = OidcFixture.logout_token(f.provider, %{"sub" => "foreign-subject"})
    assert backchannel(f, jwt).status == 200
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[0]]
    AuthDbFixture.set_clock!(f.db, Clock.now())
    AuthDbFixture.restart_control!(f.db)
    assert backchannel(f, jwt).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[1]]
    assert local(f, login).status == 403
  end

  test "verified time arithmetic includes exact age future-skew and expiry boundaries" do
    {f, _login, _path} = fixture()
    jwt = OidcFixture.logout_token(f.provider)
    assert {:ok, verified} = Oidc.verify_logout(f.config, jwt, System.monotonic_time(:millisecond) + 5000)
    now = div(Clock.now().utc_ms, 1000) * 1000
    valid = %{verified | expires_ms: now + 600_000}
    assert Oidc.logout_current?(%{valid | issued_ms: now - 300_000}, now)
    refute Oidc.logout_current?(%{valid | issued_ms: now - 301_000}, now)
    assert Oidc.logout_current?(%{valid | issued_ms: now + 30_000}, now)
    refute Oidc.logout_current?(%{valid | issued_ms: now + 31_000}, now)
    refute Oidc.logout_current?(%{valid | expires_ms: now}, now)
  end

  test "unknown kid refreshes JWKS once under the same budget and never posts a code" do
    {f, _login, _path} = fixture()
    before = OidcFixture.calls(f.provider, :jwks)
    posts = OidcFixture.calls(f.provider, :token)
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :logout_key_rotation, before + 1)})
    assert backchannel(f, OidcFixture.logout_token(f.provider)).status == 200
    assert OidcFixture.calls(f.provider, :jwks) == before + 2
    absent = OidcFixture.logout_token(f.provider, %{}, fault: :never_known_kid)
    assert backchannel(f, absent).status == 403
    assert OidcFixture.calls(f.provider, :jwks) == before + 4
    assert OidcFixture.calls(f.provider, :token) == posts
  end

  test "unknown signed COMMIT has durable replay protection without a repeated effect" do
    {f, _login, _path} = fixture()
    jwt = OidcFixture.logout_token(f.provider)
    ref = AuthDbFixture.barrier!("COMMIT")
    request = Task.async(fn -> backchannel(f, jwt) end)
    assert_receive {:query_result_held, ^ref, worker}, 2000
    assert Task.await(request, 2000).status == 503
    send(worker, {:release_query, ref})
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[1]]
    assert backchannel(f, jwt).status == 403
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
  end

  test "server APIs keep malformed and exhausted operations closed" do
    {f, login, _path} = fixture()
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    expired = System.monotonic_time() - 1
    assert {:error, :dependency_unavailable} = Logout.local(f.config, actor, Clock.now(), expired)
    assert {:error, :forbidden} = Logout.local(f.config, actor, Clock.now(), "bad deadline")
    assert {:error, :forbidden} = Oidc.verify_logout(nil, "bad", 0)
    refute Oidc.logout_current?(%{}, 0)
    assert {:error, :forbidden} = Oidc.verify_logout(f.config, nil, System.monotonic_time(:millisecond) + 1000)
    jwt = OidcFixture.logout_token(f.provider)
    assert :ok = Logout.backchannel(f.config, jwt, Clock.now())
    other = OidcFixture.logout_token(f.provider)
    assert {:error, :forbidden} = Logout.backchannel(f.config, other, Clock.now(), "bad deadline")
    assert {:error, :forbidden} = Logout.backchannel(f.config, other, Clock.now(), RequestContext.deadline() - System.convert_time_unit(4500, :millisecond, :native))
    assert {:error, :forbidden} = Logout.local(f.config, actor, Clock.now())
    assert backchannel(f, other, body: <<255>>).status == 403
    stop_supervised!(SymphonyControl.AuthDbFixture.SnapshotClock)
    assert local(f, login).status == 503
    assert {:error, :invalid_request} = Logout.local(f.config, actor, %{}, RequestContext.deadline())
    assert :deny == Authorizer.authorize(actor, :project_read, Ecto.UUID.generate())
  end

  test "loss of the actual operation Clock never commits a local or signed effect" do
    {f, login, _path} = fixture()
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    snapshot = Clock.now()
    stop_supervised!(AuthDbFixture.SnapshotClock)
    start_supervised!({AuthDbFixture.OperationFaultClock, agent: f.db.clock_agent, module: Logout})
    assert {:error, :dependency_unavailable} = Logout.local(f.config, actor, snapshot)
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[0]]
    stop_supervised!(AuthDbFixture.OperationFaultClock)
    start_supervised!({AuthDbFixture.OperationFaultClock, agent: f.db.clock_agent, module: Logout})
    jwt = OidcFixture.logout_token(f.provider)
    assert {:error, :dependency_unavailable} = Logout.backchannel(f.config, jwt, snapshot)
    assert Repo.query!("SELECT count(*) FROM control_auth_logout_jtis", [], log: false).rows == [[0]]
  end

  test "an unavailable Repo and malformed form encoding give fixed errors before mutation" do
    {f, login, _path} = fixture()
    jwt = OidcFixture.logout_token(f.provider)
    assert backchannel(f, jwt, body: "logout_token=%ZZ").status == 403
    stop_supervised!(SymphonyControl.Application)
    assert local(f, login).status == 503
  end
end
