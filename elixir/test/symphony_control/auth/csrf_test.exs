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
end
