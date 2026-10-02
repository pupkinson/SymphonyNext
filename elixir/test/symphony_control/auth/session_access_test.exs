defmodule SymphonyControl.Auth.SessionAccessTest do
  use ExUnit.Case, async: true
  alias SymphonyControl.Auth.{Principal, SessionAccess}
  @id "aaaaaaaa-1111-4111-8111-111111111111"
  @user "bbbbbbbb-2222-4222-8222-222222222222"
  @project "cccccccc-3333-4333-8333-333333333333"
  @other "dddddddd-4444-4444-8444-444444444444"
  @issuer "https://auth.example.test/o/control/"
  @now 100_000

  defp data do
    {:ok, principal} = Principal.user(@issuer, "subject", @id, @user)

    session = %{
      principal_id: @id,
      user_id: @user,
      issuer: @issuer,
      subject: "subject",
      state: :active,
      checked_at_ms: @now - 1,
      expires_at_ms: @now + 120_000
    }

    permissions = %{
      principal_id: @id,
      state: :active,
      checked_at_ms: @now - 1,
      expires_at_ms: @now + 120_000,
      grants: [{:platform, :runtime_identity_read}]
    }

    {principal, session, permissions}
  end

  test "fresh server snapshots with explicit platform permission allow exactly ok" do
    {p, s, a} = data()
    assert SessionAccess.authorize(p, s, a, :runtime_identity_read, @now) == :ok
  end

  test "session freshness is strictly less than sixty seconds" do
    {p, s, a} = data()

    assert SessionAccess.authorize(
             p,
             %{s | checked_at_ms: @now - 59_999},
             a,
             :runtime_identity_read,
             @now
           ) == :ok

    assert SessionAccess.authorize(
             p,
             %{s | checked_at_ms: @now - 60_000},
             a,
             :runtime_identity_read,
             @now
           ) == {:error, :forbidden}
  end

  test "permissions have their own independent sixty second bound" do
    {p, s, a} = data()

    assert SessionAccess.authorize(
             p,
             s,
             %{a | checked_at_ms: @now - 59_999},
             :runtime_identity_read,
             @now
           ) == :ok

    assert SessionAccess.authorize(
             p,
             s,
             %{a | checked_at_ms: @now - 60_000},
             :runtime_identity_read,
             @now
           ) == {:error, :forbidden}
  end

  test "future checks and expired records fail closed" do
    {p, s, a} = data()

    for patch <- [%{checked_at_ms: @now + 1}, %{expires_at_ms: @now}, %{expires_at_ms: @now - 1}] do
      assert SessionAccess.authorize(p, Map.merge(s, patch), a, :runtime_identity_read, @now) ==
               {:error, :forbidden}

      assert SessionAccess.authorize(p, s, Map.merge(a, patch), :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end
  end

  test "revoked unavailable unknown and boolean state never grant access" do
    {p, s, a} = data()

    for state <- [:revoked, :unavailable, :unknown, true, "active", nil] do
      assert SessionAccess.authorize(p, %{s | state: state}, a, :runtime_identity_read, @now) ==
               {:error, :forbidden}

      assert SessionAccess.authorize(p, s, %{a | state: state}, :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end
  end

  test "session must match all local and external identity fields" do
    {p, s, a} = data()

    for {field, value} <- [
          principal_id: @other,
          user_id: @other,
          issuer: @issuer <> "/",
          subject: "Subject"
        ] do
      assert SessionAccess.authorize(p, Map.put(s, field, value), a, :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end

    assert SessionAccess.authorize(
             p,
             s,
             %{a | principal_id: @other},
             :runtime_identity_read,
             @now
           ) == {:error, :forbidden}
  end

  test "project admin and IdP superuser fields never imply platform permission" do
    {p, s, a} = data()

    a =
      Map.merge(a, %{
        grants: [{:project, @project, :task_read}],
        roles: [:project_admin],
        is_superuser: true
      })

    assert SessionAccess.authorize(p, s, a, :runtime_identity_read, @now) == {:error, :forbidden}
  end

  test "project permission applies only to the server-resolved resource project" do
    {p, s, a} = data()
    a = %{a | grants: [{:project, @project, :task_read}]}
    assert SessionAccess.authorize(p, s, a, {:project, @project, :task_read}, @now) == :ok

    assert SessionAccess.authorize(p, s, a, {:project, @other, :task_read}, @now) ==
             {:error, :forbidden}

    assert SessionAccess.authorize(p, s, a, {:project, @project, :task_write}, @now) ==
             {:error, :forbidden}
  end

  test "platform permission does not imply project membership" do
    {p, s, a} = data()

    assert SessionAccess.authorize(p, s, a, {:project, @project, :task_read}, @now) ==
             {:error, :forbidden}
  end

  test "unknown actions cannot be authorized even by matching caller grant" do
    {p, s, a} = data()

    for action <- [
          :delete_all,
          "runtime_identity_read",
          {:platform, :runtime_identity_read},
          {:project, "bad", :task_read},
          {:project, @project, :task_write}
        ] do
      assert SessionAccess.authorize(p, s, %{a | grants: [action]}, action, @now) ==
               {:error, :forbidden}
    end
  end

  test "service agent and plain forged maps cannot use browser authorization" do
    {p, s, a} = data()
    {:ok, service} = Principal.service(@issuer, "subject", @id)
    {:ok, agent} = Principal.agent(@issuer, "subject", @id)

    for bad <- [
          nil,
          true,
          %{},
          Map.from_struct(p),
          service,
          agent,
          %{p | issuer: "bad"},
          %{p | user_id: nil}
        ] do
      assert SessionAccess.authorize(bad, s, a, :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end
  end

  test "timestamps are integer milliseconds, no coercion" do
    {p, s, a} = data()

    for bad <- [nil, true, 100_000.0, "100000", %{}, []] do
      assert SessionAccess.authorize(p, s, a, :runtime_identity_read, bad) == {:error, :forbidden}

      for field <- [:checked_at_ms, :expires_at_ms] do
        assert SessionAccess.authorize(p, Map.put(s, field, bad), a, :runtime_identity_read, @now) ==
                 {:error, :forbidden}

        assert SessionAccess.authorize(p, s, Map.put(a, field, bad), :runtime_identity_read, @now) ==
                 {:error, :forbidden}
      end
    end
  end

  test "negative monotonic times are valid when chronology is consistent" do
    {p, s, a} = data()
    s = %{s | checked_at_ms: -100_001, expires_at_ms: -99_000}
    a = %{a | checked_at_ms: -100_001, expires_at_ms: -99_000}
    assert SessionAccess.authorize(p, s, a, :runtime_identity_read, -100_000) == :ok
  end

  test "required session and permission fields cannot be omitted" do
    {p, s, a} = data()

    for field <- Map.keys(s) do
      assert SessionAccess.authorize(p, Map.delete(s, field), a, :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end

    for field <- Map.keys(a) do
      assert SessionAccess.authorize(p, s, Map.delete(a, field), :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end
  end

  test "unknown lookup results and non-list grants produce fixed denial" do
    {p, s, a} = data()

    for bad <- [nil, true, {:error, "private-reason"}, %{}, []] do
      assert SessionAccess.authorize(p, bad, a, :runtime_identity_read, @now) ==
               {:error, :forbidden}

      assert SessionAccess.authorize(p, s, bad, :runtime_identity_read, @now) ==
               {:error, :forbidden}

      assert SessionAccess.authorize(p, s, %{a | grants: bad}, :runtime_identity_read, @now) ==
               {:error, :forbidden}
    end
  end
end
