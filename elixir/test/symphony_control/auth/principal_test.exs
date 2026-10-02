defmodule SymphonyControl.Auth.PrincipalTest do
  use ExUnit.Case, async: true
  alias SymphonyControl.Auth.Principal

  @issuer "https://auth.example.test/application/o/symphony/"
  @principal "aaaaaaaa-1111-4111-8111-111111111111"
  @user "bbbbbbbb-2222-4222-8222-222222222222"

  test "user links external issuer/subject to explicit local IDs" do
    assert {:ok, value} = Principal.user(@issuer, "subject-1", @principal, @user)
    assert Principal.key(value) == {:user, @issuer, "subject-1"}
    assert value.principal_id == @principal
    assert value.user_id == @user
  end

  test "local references normalize but issuer and subject do not" do
    assert {:ok, value} =
             Principal.user(
               @issuer,
               " Mixed Case ",
               String.upcase(@principal),
               String.upcase(@user)
             )

    assert value.principal_id == @principal
    assert value.user_id == @user
    assert Principal.key(value) == {:user, @issuer, " Mixed Case "}
  end

  test "different issuer, subject case and trailing issuer slash do not merge" do
    {:ok, a} = Principal.user(@issuer, "User", @principal, @user)
    {:ok, b} = Principal.user(@issuer, "user", @principal, @user)
    {:ok, c} = Principal.user(String.trim_trailing(@issuer, "/"), "User", @principal, @user)
    assert MapSet.size(MapSet.new([Principal.key(a), Principal.key(b), Principal.key(c)])) == 3
  end

  test "local principal remapping does not change external identity" do
    {:ok, a} = Principal.user(@issuer, "User", @principal, @user)
    {:ok, b} = Principal.user(@issuer, "User", @user, @principal)
    assert Principal.key(a) == Principal.key(b)
    refute a == b
  end

  test "service and agent cannot become a user just by sharing issuer and subject" do
    {:ok, user} = Principal.user(@issuer, "id", @principal, @user)
    {:ok, service} = Principal.service(@issuer, "id", @principal)
    {:ok, agent} = Principal.agent(@issuer, "id", @principal)
    assert service.user_id == nil
    assert agent.user_id == nil
    assert MapSet.size(MapSet.new(Enum.map([user, service, agent], &Principal.key/1))) == 3
  end

  test "values contain neither roles nor sessions nor verification flags" do
    {:ok, value} = Principal.user(@issuer, "subject", @principal, @user)

    assert Map.keys(Map.from_struct(value)) |> Enum.sort() == [
             :issuer,
             :kind,
             :principal_id,
             :subject,
             :user_id
           ]
  end

  test "Inspect omits identity and local references" do
    {:ok, value} = Principal.user(@issuer, "private-subject", @principal, @user)

    for private <- [@issuer, "private-subject", @principal, @user] do
      refute inspect(value) =~ private
    end

    assert inspect(value) =~ ":user"
  end

  test "user local IDs are both mandatory and valid UUIDs" do
    for bad <- [nil, false, 7, "", "not-a-uuid", @principal <> "\n", <<255>>] do
      assert Principal.user(@issuer, "id", bad, @user) == {:error, :invalid_principal}
      assert Principal.user(@issuer, "id", @principal, bad) == {:error, :invalid_principal}
      assert Principal.service(@issuer, "id", bad) == {:error, :invalid_principal}
      assert Principal.agent(@issuer, "id", bad) == {:error, :invalid_principal}
    end
  end

  test "subject is nonempty printable ASCII, no coercion or trimming" do
    for bad <- [
          nil,
          true,
          1,
          [],
          %{},
          "",
          "user\n",
          "id\0",
          "café",
          <<255>>,
          String.duplicate("a", 256)
        ] do
      assert Principal.user(@issuer, bad, @principal, @user) == {:error, :invalid_principal}
    end

    assert {:ok, _} = Principal.user(@issuer, String.duplicate("a", 255), @principal, @user)
  end

  test "issuer must be an HTTPS URI without credentials, query or fragment" do
    for bad <- [
          nil,
          true,
          1,
          [],
          %{},
          "",
          "https://",
          "http://auth.test",
          "urn:issuer",
          "https://u:p@auth.test",
          "https://auth.test?q=1",
          "https://auth.test#fragment",
          "https://auth.test:0",
          "https://auth.test:65536",
          "https://auth.test\n",
          <<255>>,
          String.duplicate("a", 2049)
        ] do
      assert Principal.user(bad, "subject", @principal, @user) == {:error, :invalid_principal}
    end
  end

  test "accepted issuer spelling is preserved exactly, including path and port" do
    issuer = "https://Auth.example.test:8443/application/o/Symphony/"
    assert {:ok, value} = Principal.user(issuer, "id", @principal, @user)
    assert value.issuer == issuer
  end

  test "rejects malformed percent escapes in authority and path" do
    for issuer <- [
          "https://auth.test/%",
          "https://auth.test/%ZZ",
          "https://auth.test/%1",
          "https://auth.test/%aG",
          "https://au%ZZth.test/issuer"
        ] do
      assert Principal.user(issuer, "id", @principal, @user) == {:error, :invalid_principal}
    end
  end

  test "rejects invalid authority and raw path delimiters" do
    for issuer <- [
          "https://auth.test/[bad]",
          "https://auth.test/a]b",
          "https://auth.test/a\\b",
          "https://auth.test/{x}",
          "https://auth.test/a|b",
          "https://auth.test/a^b",
          "https://auth.test:/issuer",
          "https://[not-an-ip]/issuer"
        ] do
      assert Principal.user(issuer, "id", @principal, @user) == {:error, :invalid_principal}
    end
  end

  test "valid escaped paths and IPv6 keep exact issuer identity" do
    for issuer <- [
          "https://auth.test/%2fissuer",
          "https://auth.test/%5Bok%5D",
          "https://[::1]:8443/issuer",
          "https://[::ffff:192.0.2.1]/issuer",
          "https://auth.test/a:b@c;d=e!$&'()*+,~_"
        ] do
      assert {:ok, value} = Principal.user(issuer, "id", @principal, @user)
      assert value.issuer == issuer
    end
  end

  test "constructor failures never echo private input" do
    assert Principal.user("not-valid-private-data", "private-token", @principal, @user) ==
             {:error, :invalid_principal}
  end
end
