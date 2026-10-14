defmodule SymphonyControl.Auth.CsrfTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Actor, Clock, Csrf, RequestContext, Store}
  alias SymphonyControl.AuthHttpFixture

  test "a random token binds every actor field and never substitutes for a local session" do
    f = AuthHttpFixture.start!(task4: true)
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    assert {:ok, token} = Csrf.issue(f.config, actor, RequestContext.deadline())
    assert :ok == Csrf.verify(f.config, actor, token, RequestContext.deadline())

    for forged <- [
          %{actor | session_id: Ecto.UUID.generate()},
          %{actor | local_user_id: Ecto.UUID.generate()},
          %{actor | subject: "foreign"},
          %{actor | config_generation: "foreign"},
          %{actor | boot_epoch: "foreign"}
        ] do
      assert {:error, :forbidden} == Csrf.verify(f.config, forged, token, RequestContext.deadline())
    end

    for malformed <- [nil, %{}, String.duplicate("x", 257), "wrong"] do
      assert {:error, :forbidden} == Csrf.verify(f.config, actor, malformed, RequestContext.deadline())
    end

    assert {:error, :forbidden} == Csrf.issue(%{f.config | generation: "foreign"}, actor, RequestContext.deadline())
    assert {:error, :forbidden} == Csrf.perform(%{}, :issue, :crypto.strong_rand_bytes(32))
    malformed = struct(Actor)
    assert {:error, :forbidden} == Csrf.perform(malformed, :issue, :crypto.strong_rand_bytes(32))
    assert {:error, :forbidden} == Csrf.perform(actor, :issue, nil)
  end

  test "missing Access dependency makes issuance and verification unavailable" do
    deadline = RequestContext.deadline()
    assert {:error, :dependency_unavailable} = Csrf.issue(nil, nil, deadline)
    assert {:error, :dependency_unavailable} = Csrf.verify(nil, nil, nil, deadline)
  end

  @tag :repair_r1
  test "R1 callback queued CSRF reply past credential lifetime sends no session or CSRF cookie" do
    f = AuthHttpFixture.start!(task4: true, expires_in: 3)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    owner = self()
    ref = make_ref()

    debug = fn
      false, {:in, {:"$gen_call", _from, {:csrf, _cfg, _actor, :issue}}}, _extra ->
        send(owner, {:csrf_reply_held, ref, self()})

        receive do
          {:release_csrf, ^ref} -> :ok
        after
          4000 -> :ok
        end

        true

      state, _event, _extra ->
        state
    end

    :ok = :sys.install(SymphonyControl.Auth.Access, {debug, false})
    request = Task.async(fn -> AuthHttpFixture.callback(f, flow: flow) end)
    assert_receive {:csrf_reply_held, ^ref, producer}, 2000
    [[expiry]] = SymphonyControl.Repo.query!("SELECT credential_expires_at_ms FROM control_auth_sessions", [], log: false).rows
    now = Clock.now().utc_ms
    assert now < expiry
    Process.sleep(expiry - now + 30)
    send(producer, {:release_csrf, ref})
    response = Task.await(request, 2000)
    assert response.status in [403, 503]
    assert Req.Response.get_header(response, "set-cookie") == []
    assert Req.Response.get_header(response, "location") == []
  end
end
