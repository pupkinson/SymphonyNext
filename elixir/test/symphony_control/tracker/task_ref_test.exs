defmodule SymphonyControl.Tracker.TaskRefTest do
  use ExUnit.Case, async: true
  alias SymphonyControl.Tracker.{ObjectIdentity, TaskRef}
  @id "aaaaaaaa-1111-4111-8111-111111111111"
  @project "bbbbbbbb-2222-4222-8222-222222222222"
  @binding "cccccccc-3333-4333-8333-333333333333"
  @other "dddddddd-4444-4444-8444-444444444444"

  defp ref do
    {:ok, object} = ObjectIdentity.github(42)
    {:ok, ref} = TaskRef.new(@id, @project, object, @binding, 1)
    ref
  end

  test "constructs stable local reference with independent source object" do
    ref = ref()
    assert ref.id == @id
    assert TaskRef.key(ref) == {@project, {:github, "github.com", 42}}
    assert TaskRef.ownership_key(ref) == {:github, "github.com", 42}
  end

  test "all providers work without credentials and display metadata" do
    for {:ok, object} <- [
          ObjectIdentity.native(@id, @other),
          ObjectIdentity.github(42),
          ObjectIdentity.linear(@binding, @other)
        ] do
      assert {:ok, ref} = TaskRef.new(@id, @project, object, @binding, 1)
      assert TaskRef.ownership_key(ref) == ObjectIdentity.key(object)

      assert Map.keys(Map.from_struct(ref)) |> Enum.sort() == [
               :binding_id,
               :generation,
               :id,
               :object,
               :project_id
             ]
    end
  end

  test "normalizes UUIDs but never coerces generation" do
    original = ref()

    assert {:ok, normalized} =
             TaskRef.new(
               String.upcase(@id),
               String.upcase(@project),
               original.object,
               String.upcase(@binding),
               1
             )

    assert normalized == original

    for bad <- [nil, true, 0, -1, 1.0, "1", []] do
      assert TaskRef.new(@id, @project, original.object, @binding, bad) ==
               {:error, :invalid_task_ref}
    end
  end

  test "rejects malformed local IDs at every position" do
    for bad <- [nil, [], %{}, 1, "", @id <> "\n", <<255>>, String.duplicate("a", 1000)] do
      assert TaskRef.new(bad, @project, ref().object, @binding, 1) == {:error, :invalid_task_ref}
      assert TaskRef.new(@id, bad, ref().object, @binding, 1) == {:error, :invalid_task_ref}
      assert TaskRef.new(@id, @project, ref().object, bad, 1) == {:error, :invalid_task_ref}
    end
  end

  test "rejects forged object namespace, invalid ID and plain map" do
    for bad <- [
          nil,
          %{},
          %{ref().object | namespace: "evil.test"},
          %{ref().object | object_id: 1.0},
          %{ref().object | provider: :unknown}
        ] do
      assert TaskRef.new(@id, @project, bad, @binding, 1) == {:error, :invalid_task_ref}
    end
  end

  test "rebinding retains local identity and leaves old snapshot unchanged" do
    old = ref()
    snapshot = TaskRef.snapshot(old)
    assert {:ok, new} = TaskRef.rebind(old, 1, @other, 2)
    assert new.id == old.id and new.project_id == old.project_id and new.object == old.object
    assert new.binding_id == @other and new.generation == 2
    assert old.binding_id == @binding and old.generation == 1
    assert TaskRef.key(new) == TaskRef.key(old)
    assert TaskRef.ownership_key(new) == TaskRef.ownership_key(old)
    assert TaskRef.current?(old, snapshot)
    refute TaskRef.current?(new, snapshot)
  end

  test "rotation within one binding still advances generation" do
    assert {:ok, new} = TaskRef.rebind(ref(), 1, @binding, 5)
    assert new.binding_id == @binding and new.generation == 5
  end

  test "stale expected generation and non-increasing epoch conflict" do
    assert TaskRef.rebind(ref(), 2, @other, 3) == {:error, :conflict}
    assert TaskRef.rebind(ref(), 1, @other, 1) == {:error, :conflict}
    {:ok, newer} = TaskRef.rebind(ref(), 1, @other, 5)
    assert TaskRef.rebind(newer, 5, @binding, 4) == {:error, :conflict}
  end

  test "rebind validates both generations and new binding" do
    for bad <- [nil, 0, -1, 1.0, "2"] do
      assert TaskRef.rebind(ref(), bad, @other, 3) == {:error, :invalid_task_ref}
      assert TaskRef.rebind(ref(), 1, @other, bad) == {:error, :invalid_task_ref}
    end

    assert TaskRef.rebind(ref(), 1, "bad", 2) == {:error, :invalid_task_ref}
    assert TaskRef.rebind(nil, 1, @other, 2) == {:error, :invalid_task_ref}
  end

  test "different local projects share ownership exclusion key, not registry key" do
    old = ref()
    {:ok, other} = TaskRef.new(@other, @id, old.object, @other, 10)
    refute TaskRef.key(old) == TaskRef.key(other)
    assert TaskRef.ownership_key(old) == TaskRef.ownership_key(other)
  end

  test "snapshot includes exact source pin, not mutable task text" do
    assert TaskRef.snapshot(ref()) == %{
             task_ref_id: @id,
             project_id: @project,
             object_key: {:github, "github.com", 42},
             binding_id: @binding,
             generation: 1
           }
  end

  test "current check rejects other identity, unknown shapes and extra fields" do
    ref = ref()
    pin = TaskRef.snapshot(ref)

    for bad <- [
          nil,
          %{},
          Map.put(pin, :admitted, true),
          %{pin | generation: 2},
          %{pin | project_id: @other},
          %{pin | object_key: {:github, "github.com", 43}}
        ] do
      refute TaskRef.current?(ref, bad)
    end
  end

  test "invalid reference cannot be rebound into a trusted shape" do
    forged = %{ref() | project_id: "bad"}
    assert TaskRef.rebind(forged, 1, @other, 2) == {:error, :invalid_task_ref}
  end

  test "Inspect omits local and external object identifiers" do
    text = inspect(ref())

    for private <- [@id, @project, @binding, "github.com"] do
      refute text =~ private
    end
  end
end
