defmodule SymphonyControl.Auth.RevocationTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, Clock, Eligibility, OidcFixture, Store}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Projects, Repo}

  defp fixture do
    f = AuthHttpFixture.start!(task4: true, project_authorizer: Authorizer, runtime_identity_authorizer: Authorizer)
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
    login = AuthHttpFixture.login!(f)
    AuthDbFixture.set_clock!(f.db, Clock.now())
    {f, login, "/api/v1/projects/" <> project}
  end

  test "real HTTPS cache hit retains the original observation with measured decision headroom" do
    {f, login, path} = fixture()
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    entry = cache_entry()
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligible, false)})
    AuthDbFixture.set_clock!(f.db, entry.clock)
    AuthDbFixture.advance!(f.db, 49_000)
    ref = AuthDbFixture.barrier!("FROM \"projects\"")
    read = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
    assert_receive {:query_result_held, ^ref, worker}, 2000
    caller = trace_decisions!(worker)
    send(worker, {:release_query, ref})
    assert Task.await(read, 3000).status == 200
    decisions = completed_decisions(caller, [])
    {actual, measured, decision, producer} = List.last(decisions)
    assert actual.ref == entry.ref
    assert Eligibility.observation_current?(entry, measured, decision, producer)
    utc_age = measured.utc_ms - entry.clock.utc_ms
    mono_age = measured.monotonic_ms - entry.clock.monotonic_ms
    delivery_ms = System.convert_time_unit(decision - measured.native_anchor, :native, :microsecond) / 1000
    final_age = max(utc_age, mono_age) + delivery_ms
    assert final_age >= 49_000 and final_age < 50_000
    IO.puts("fresh cache decision (no credentials): " <> inspect(%{utc_age: utc_age, monotonic_age: mono_age, delivery_ms: delivery_ms, final_age_ms: final_age}))
    assert OidcFixture.calls(f.provider, :eligibility) == 1
    assert cache_entry() == entry
    AuthDbFixture.advance!(f.db, 1000)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert OidcFixture.calls(f.provider, :eligibility) == 2
    assert :sys.get_state(Eligibility).cache == %{}
    AuthDbFixture.advance!(f.db, 10_000)
    assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
    assert :sys.get_state(Eligibility).cache == %{}
  end

  for {age, status} <- [{49_000, 200}, {49_999, 403}] do
    @age age
    @status status
    test "already measured #{@age}ms observation held inside the HTTP request returns#{@status} without renewal" do
      {f, login, path} = fixture()
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
      entry = cache_entry()
      Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :eligible, false)})
      ref = AuthDbFixture.barrier!("FROM \"projects\"")
      started = System.monotonic_time(:millisecond)
      read = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
      assert_receive {:query_result_held, ^ref, worker}, 2000
      AuthDbFixture.set_clock!(f.db, entry.clock)
      AuthDbFixture.advance!(f.db, @age)
      held = AuthDbFixture.hold_clock_reply!({:stack, Eligibility, :current?, 1})
      send(worker, {:release_query, ref})
      assert_receive {:clock_reply_held, ^held, _from, producer}, 1000
      assert_receive {:clock_sample_measured, ^held, _from, ^producer, sample, _measured}, 1000
      assert sample.utc_ms - entry.clock.utc_ms == @age
      assert sample.monotonic_ms - entry.clock.monotonic_ms == @age
      Process.sleep(20)
      expiry = sample.native_anchor + System.convert_time_unit(50_000 - @age, :millisecond, :native)
      crossed = System.monotonic_time() >= expiry
      assert crossed == (@status == 403)
      send(producer, {:release_clock, held})
      reply = Task.await(read, 3000)
      assert reply.status == @status
      assert System.monotonic_time(:millisecond) - started < 5000
      refute Map.has_key?(reply.headers, "set-cookie")
      if @status == 403, do: assert(reply.body == %{"error" => "forbidden"})
      assert OidcFixture.calls(f.provider, :eligibility) == 1
      assert cache_entry() == entry
      [_, handle] = String.split(login.cookie, "=", parts: 2)
      assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
      assert actor == entry.actor
      AuthDbFixture.advance!(f.db, 50_000 - @age)
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
      assert :sys.get_state(Eligibility).cache == %{}
      AuthDbFixture.advance!(f.db, 10_000)
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 403
      assert :sys.get_state(Eligibility).cache == %{}
    end
  end

  defp cache_entry, do: :sys.get_state(Eligibility).cache |> Map.values() |> hd()

  defp trace_decisions!(worker) do
    {:dictionary, dictionary} = Process.info(worker, :dictionary)
    [caller | _] = Keyword.fetch!(dictionary, :"$callers")
    {:current_stacktrace, frames} = Process.info(caller, :current_stacktrace)
    assert Enum.any?(frames, fn {module, function, _, _} -> module == Projects and function == :database end)
    1 = :erlang.trace_pattern({Eligibility, :observation_current?, 4}, true, [:local])
    1 = :erlang.trace(caller, true, [:call])

    on_exit(fn ->
      if Process.alive?(caller), do: :erlang.trace(caller, false, [:call])
      :erlang.trace_pattern({Eligibility, :observation_current?, 4}, false, [:local])
    end)

    caller
  end

  defp completed_decisions(worker, decisions) do
    marker = :erlang.trace_delivered(worker)
    assert_receive {:trace_delivered, ^worker, ^marker}, 1000
    collect_decisions(worker, decisions)
  end

  defp collect_decisions(worker, decisions) do
    receive do
      {:trace, ^worker, :call, {Eligibility, :observation_current?, [entry, measured, now, producer]}} ->
        collect_decisions(worker, decisions ++ [{entry, measured, now, producer}])
    after
      0 -> decisions
    end
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
