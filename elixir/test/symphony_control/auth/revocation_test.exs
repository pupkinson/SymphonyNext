defmodule SymphonyControl.Auth.RevocationTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, Clock, Eligibility, OidcFixture}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Repo}

  defp fixture do
    f = AuthHttpFixture.start!(task4: true, project_authorizer: Authorizer, runtime_identity_authorizer: Authorizer)
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
    login = AuthHttpFixture.login!(f)
    AuthDbFixture.set_clock!(f.db, Clock.now())
    {f, login, "/api/v1/projects/" <> project}
  end

  test "fresh observation is reused and never renewed by reads at 49999ms" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligible, false)})
    AuthDbFixture.advance!(f.db, 49_999)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    AuthDbFixture.advance!(f.db, 1)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 2
    AuthDbFixture.advance!(f.db, 10_000)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
  end

  for kind <- [:app_group, :user_active, :idp_session] do
    @kind kind
    test "wire #{@kind} removal after success refuses at 50000ms and later" do
      {f, login, path} = fixture()
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
      Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, @kind, false)})
      AuthDbFixture.advance!(f.db, 50_000)
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
      AuthDbFixture.advance!(f.db, 10_000)
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    end
  end

  test "outage cannot revive stale success and current membership always wins" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    Repo.query!("DELETE FROM control_auth_memberships", [], log: false)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    stop_supervised!(f.provider.server_id)
    AuthDbFixture.advance!(f.db, 50_000)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status in [403, 503]
    AuthDbFixture.advance!(f.db, 10_000)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status in [403, 503]
  end

  test "invalidation prevents an accepted but delayed observation from publishing" do
    {f, login, path} = fixture()
    ref = make_ref()
    owner = self()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligibility_barrier, {owner, ref})})
    read = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
    assert_receive {:eligibility_accepted, ^ref, provider}, 2000
    assert :ok == Eligibility.invalidate(f.config, {:subject, f.config.issuer, "human-1"}, System.monotonic_time(:millisecond) + 1000)
    send(provider, {ref, :release})
    assert Task.await(read, 3000).status in [403, 503]
    Agent.update(f.provider.state, &%{&1 | opts: &1.opts |> Keyword.delete(:eligibility_barrier) |> Keyword.put(:eligible, false)})
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
  end

  test "control epoch replacement denies old cookie and needs a new login" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    current = Clock.now()
    AuthDbFixture.set_clock!(f.db, %{current | epoch: :crypto.strong_rand_bytes(32)})
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    fresh_login = AuthHttpFixture.login!(f)
    assert AuthHttpFixture.get(f, path, cookie: fresh_login.cookie).status == 200
  end

  test "private project bytes wait for a final fresh decision after the project query" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    ref = AuthDbFixture.barrier!("FROM \"projects\"")
    read = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
    assert_receive {:query_result_held, ^ref, worker}, 2000
    AuthDbFixture.advance!(f.db, 50_000)
    send(worker, {:release_query, ref})
    reply = Task.await(read, 3000)
    assert reply.status == 403
    refute Map.has_key?(reply.body, "project")
    assert OidcFixture.calls(f.provider, :eligibility) == 1
  end
end
