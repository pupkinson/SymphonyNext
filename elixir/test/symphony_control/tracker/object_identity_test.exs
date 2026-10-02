defmodule SymphonyControl.Tracker.ObjectIdentityTest do
  use ExUnit.Case, async: true
  alias SymphonyControl.Tracker.ObjectIdentity

  @installation "aaaaaaaa-1111-4111-8111-111111111111"
  @workspace "bbbbbbbb-2222-4222-8222-222222222222"
  @issue "cccccccc-3333-4333-8333-333333333333"

  test "native identity is installation and issue, with no connection" do
    assert {:ok, value} = ObjectIdentity.native(@installation, @issue)
    assert ObjectIdentity.key(value) == {:native, @installation, @issue}
  end

  test "UUID text case does not split one native identity" do
    assert {:ok, lower} = ObjectIdentity.native(@installation, @issue)

    assert {:ok, upper} =
             ObjectIdentity.native(String.upcase(@installation), String.upcase(@issue))

    assert lower == upper
  end

  test "native installations are different namespaces" do
    {:ok, a} = ObjectIdentity.native(@installation, @issue)
    {:ok, b} = ObjectIdentity.native(@workspace, @issue)
    refute ObjectIdentity.key(a) == ObjectIdentity.key(b)
  end

  test "github uses REST database ID, not repository or issue display number" do
    assert {:ok, value} = ObjectIdentity.github(5_675_863_392)
    assert ObjectIdentity.key(value) == {:github, "github.com", 5_675_863_392}
    assert Map.keys(Map.from_struct(value)) |> Enum.sort() == [:namespace, :object_id, :provider]
  end

  test "github integer identity is exact above JavaScript safe integer range" do
    {:ok, a} = ObjectIdentity.github(9_007_199_254_740_992)
    {:ok, b} = ObjectIdentity.github(9_007_199_254_740_993)
    refute ObjectIdentity.key(a) == ObjectIdentity.key(b)
  end

  test "github rejects negative, zero, floats, IDs encoded as other types" do
    for id <- [0, -1, 1.0, "42", "GH-42", nil, true, [], %{}, <<255>>] do
      assert ObjectIdentity.github(id) == {:error, :invalid_object_identity}
    end
  end

  test "linear namespace is workspace, not team, project filter or token" do
    assert {:ok, value} = ObjectIdentity.linear(@workspace, @issue)
    assert ObjectIdentity.key(value) == {:linear, @workspace, @issue}
  end

  test "linear UUIDs normalize without depending on display IDs" do
    {:ok, a} = ObjectIdentity.linear(@workspace, @issue)
    {:ok, b} = ObjectIdentity.linear(String.upcase(@workspace), String.upcase(@issue))
    assert ObjectIdentity.key(a) == ObjectIdentity.key(b)
    assert {:error, :invalid_object_identity} = ObjectIdentity.linear(@workspace, "TEAM-123")
  end

  test "providers and workspaces never alias" do
    {:ok, a} = ObjectIdentity.native(@workspace, @issue)
    {:ok, b} = ObjectIdentity.linear(@workspace, @issue)
    {:ok, c} = ObjectIdentity.linear(@installation, @issue)

    assert MapSet.size(
             MapSet.new([ObjectIdentity.key(a), ObjectIdentity.key(b), ObjectIdentity.key(c)])
           ) == 3
  end

  test "all UUID positions are strict and bounded" do
    for bad <- [
          nil,
          1,
          [],
          %{},
          "",
          @issue <> "\n",
          " " <> @issue,
          <<255>>,
          String.duplicate("a", 1000)
        ] do
      assert ObjectIdentity.native(bad, @issue) == {:error, :invalid_object_identity}
      assert ObjectIdentity.native(@installation, bad) == {:error, :invalid_object_identity}
      assert ObjectIdentity.linear(bad, @issue) == {:error, :invalid_object_identity}
      assert ObjectIdentity.linear(@workspace, bad) == {:error, :invalid_object_identity}
    end
  end

  test "Inspect hides provider object and namespace values" do
    {:ok, value} = ObjectIdentity.linear(@workspace, @issue)
    refute inspect(value) =~ @workspace
    refute inspect(value) =~ @issue
    assert inspect(value) =~ ":linear"
  end
end
