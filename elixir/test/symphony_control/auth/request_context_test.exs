defmodule SymphonyControl.Auth.RequestContextTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Clock, Login, Store}
  alias SymphonyControl.{AuthHttpFixture, Repo}

  @tag repair_r2: true
  test "R2 begin cannot publish a flow after its stored monotonic axis expires" do
    f = AuthHttpFixture.start!()
    AuthHttpFixture.login_clock!(f, 3)
    clock = Clock.now()
    result = Login.begin(f.config, nil, clock)
    assert_receive {:lifetime_projection, later, issued, measured}, 1000
    assert later.utc_ms == issued.utc_ms + 299_999
    assert later.monotonic_ms - issued.monotonic_ms == 300_000
    assert later.native_clock == Process.whereis(Clock)
    assert issued.native_clock == later.native_clock
    assert issued.epoch == later.epoch
    assert issued.native_unit == later.native_unit
    assert later.native_unit == System.convert_time_unit(1, :second, :native)
    assert measured >= later.native_anchor
    assert elem(result, 0) == :error
    assert elem(result, 1) == :forbidden
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows == [[1]]
  end

  @tag repair_r2: true
  test "R2 committed session cannot be released after monotonic expiry with UTC still before expiry" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    AuthHttpFixture.login_clock!(f, 4)
    browser = flow.cookie |> String.split("=", parts: 2) |> List.last()
    result = Login.finish(f.config, flow.params["code"], flow.params["state"], browser, nil, Clock.now())
    assert_receive {:lifetime_projection, later, issued, measured}, 1000
    [[expiry, issued_utc, issued_mono]] = Repo.query!("SELECT expires_at_ms,issued_at_ms,monotonic_issued_ms FROM control_auth_sessions", [], log: false).rows
    assert issued.utc_ms == issued_utc
    assert issued.monotonic_ms == issued_mono
    assert issued.native_clock == later.native_clock
    assert issued.epoch == later.epoch
    assert issued.native_unit == later.native_unit
    assert later.utc_ms == expiry - 1
    assert later.monotonic_ms - issued_mono == expiry - issued_utc
    assert later.native_anchor < measured
    assert elem(result, 0) == :error
    assert elem(result, 1) == :forbidden
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]
  end

  test "production Clock positive preserves public Login begin finish and committed actor" do
    f = AuthHttpFixture.start!()
    stop_supervised!(SymphonyControl.AuthDbFixture.SnapshotClock)
    start_supervised!({Clock, []})
    session = AuthHttpFixture.login!(f)
    handle = session.cookie |> String.split("=", parts: 2) |> List.last()
    assert {:ok, _} = Store.local_actor(f.config, handle, Clock.now())
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
  end

  test "R2 delayed measured worker sample withholds a committed browser flow" do
    f = AuthHttpFixture.start!()
    AuthHttpFixture.login_clock!(f, 3, delivery: :delayed)
    result = Login.begin(f.config, nil, Clock.now())
    assert elem(result, 0) == :error
    assert elem(result, 1) == :forbidden
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows == [[1]]
  end

  test "R2 paused caller with a measured worker sample cannot publish its browser flow" do
    f = AuthHttpFixture.start!()
    AuthHttpFixture.login_clock!(f, 3, delivery: :held)
    caller = Task.async(fn -> Login.begin(f.config, nil, Clock.now()) end)
    assert_receive {:login_sample_held, clock, worker}, 1000
    :erlang.suspend_process(caller.pid)
    on_exit(fn -> if Process.alive?(caller.pid), do: :erlang.resume_process(caller.pid) end)
    monitor = Process.monitor(worker)
    send(clock, :release_login_sample)
    assert_receive {:DOWN, ^monitor, :process, ^worker, :normal}, 1000
    Process.sleep(10)
    :erlang.resume_process(caller.pid)
    result = Task.await(caller)
    assert elem(result, 0) == :error
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows == [[1]]
  end

  test "R2 HTTP expiry refusal retains confirmed consume insertion and rotation without cookie" do
    f = AuthHttpFixture.start!()
    first = AuthHttpFixture.login!(f)
    flow = AuthHttpFixture.login!(f, phase: :begin)
    AuthHttpFixture.login_clock!(f, 4)
    reply = AuthHttpFixture.callback(f, flow: flow, cookie: flow.cookie <> "; " <> first.cookie)
    assert reply.status == 403
    assert is_nil(AuthHttpFixture.cookie(reply, "__Host-symphony-control"))
    assert AuthHttpFixture.counts(f) == %{exchanges: 2, sessions: 2}
    assert Repo.query!("SELECT count(*) FROM control_auth_sessions WHERE revoked_at_ms IS NOT NULL", [], log: false).rows == [[1]]
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[2]]
  end

  for fault <- [:repo_lost, :identity_inactive] do
    test "final Login caller refuses #{fault} after confirmed session insertion" do
      f = AuthHttpFixture.start!()
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
      assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
      assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[1]]

      if unquote(fault) == :repo_lost do
        :ok = Supervisor.terminate_child(SymphonyControl.Application, Repo)
      else
        Repo.query!("UPDATE control_auth_users SET active=false", [], log: false)
      end

      :erlang.resume_process(caller.pid)
      result = Task.await(caller, 2000)
      assert elem(result, 0) == :error
      expected = if unquote(fault) == :repo_lost, do: :dependency_unavailable, else: :forbidden
      assert elem(result, 1) == expected
    end
  end
end
