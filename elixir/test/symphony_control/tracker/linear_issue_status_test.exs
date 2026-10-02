defmodule SymphonyControl.Tracker.LinearIssueStatusTest do
  use ExUnit.Case, async: true
  alias SymphonyControl.Tracker.LinearIssueStatus
  @workspace "aaaaaaaa-1111-4111-8111-111111111111"
  @team "bbbbbbbb-2222-4222-8222-222222222222"
  @project "cccccccc-3333-4333-8333-333333333333"
  @issue "dddddddd-4444-4444-8444-444444444444"
  @state "eeeeeeee-5555-4555-8555-555555555555"
  @other "ffffffff-6666-4666-8666-666666666666"

  defp scope do
    %{workspace_id: @workspace, team_id: @team, project_id: nil, issue_id: @issue}
  end

  defp payload do
    %{
      "data" => %{
        "organization" => %{"id" => @workspace},
        "issue" => %{
          "id" => @issue,
          "team" => %{"id" => @team},
          "project" => nil,
          "state" => %{"id" => @state, "team" => %{"id" => @team}},
          "archivedAt" => nil
        }
      }
    }
  end

  defp extract(body, bind \\ scope(), mapping \\ %{@state => "started"}) do
    LinearIssueStatus.extract(200, body, bind, mapping)
  end

  test "valid response calls StatusMap and returns only normalized reference fields" do
    assert extract(payload()) ==
             {:ok,
              %{
                provider: :linear,
                workspace_id: @workspace,
                team_id: @team,
                project_id: nil,
                issue_id: @issue,
                state_id: @state,
                category: "started"
              }}
  end

  for category <- ~w(triage backlog unstarted started review completed canceled) do
    test "preserves #{category} as business status without admission" do
      assert {:ok, out} = extract(payload(), scope(), %{@state => unquote(category)})
      assert out.category == unquote(category)
      refute Map.has_key?(out, :admitted)
      refute Map.has_key?(out, :execution_success)
    end
  end

  test "accepts explicitly empty GraphQL errors but not partial success" do
    assert {:ok, _} = extract(Map.put(payload(), "errors", []))

    assert extract(Map.put(payload(), "errors", [%{"message" => "private"}])) ==
             {:error, :graphql_error}

    assert extract(%{"errors" => [%{"message" => "private"}]}) == {:error, :graphql_error}
  end

  test "malformed error containers are invalid, never data success" do
    for value <- [nil, false, %{}, "private", [:error | :bad_tail]] do
      assert extract(Map.put(payload(), "errors", value)) == {:error, :invalid_response}
    end
  end

  test "HTTP failures are categorized without echoing body or using its data" do
    for {code, reason} <- [
          {401, :forbidden},
          {403, :forbidden},
          {429, :rate_limited},
          {500, :unavailable},
          {503, :unavailable},
          {599, :unavailable},
          {302, :unexpected_http_status},
          {404, :unexpected_http_status},
          {204, :unexpected_http_status}
        ] do
      assert LinearIssueStatus.extract(code, payload(), scope(), %{}) == {:error, reason}
    end

    for code <- [nil, "200", 200.0, 99, 600, true, []] do
      assert LinearIssueStatus.extract(code, payload(), scope(), %{}) ==
               {:error, :invalid_response}
    end
  end

  test "binding needs every pinned field and rejects typos or structs" do
    for field <- Map.keys(scope()) do
      assert extract(payload(), Map.delete(scope(), field)) == {:error, :invalid_binding}
    end

    for invalid <- [
          nil,
          [],
          %URI{},
          Map.put(scope(), :project, @project),
          %{
            "workspace_id" => @workspace,
            "team_id" => @team,
            "project_id" => nil,
            "issue_id" => @issue
          }
        ] do
      assert extract(payload(), invalid) == {:error, :invalid_binding}
    end
  end

  test "all binding UUID positions are strict including optional project" do
    for field <- Map.keys(scope()),
        bad <- [0, true, [], "", "TEAM-1", @issue <> "\n", <<255>> <> String.duplicate("a", 35)] do
      assert extract(payload(), Map.put(scope(), field, bad)) == {:error, :invalid_binding}
    end

    for field <- [:workspace_id, :team_id, :issue_id] do
      assert extract(payload(), Map.put(scope(), field, nil)) == {:error, :invalid_binding}
    end
  end

  test "malformed root data organization and null fields never raise" do
    for body <- [
          nil,
          [],
          true,
          "json",
          %URI{},
          %{},
          %{"data" => nil},
          %{"data" => %{}},
          put_in(payload(), ["data", "organization"], nil),
          put_in(payload(), ["data", "organization"], %{}),
          put_in(payload(), ["data", "organization"], %URI{})
        ] do
      assert extract(body) == {:error, :invalid_response}
    end
  end

  test "workspace and exact requested issue identity are required" do
    for path <- [["data", "organization", "id"], ["data", "issue", "id"]] do
      assert extract(put_in(payload(), path, @other)) == {:error, :scope_mismatch}
    end
  end

  test "issue team and workflow state team must match the pinned team" do
    for path <- [["data", "issue", "team", "id"], ["data", "issue", "state", "team", "id"]] do
      assert extract(put_in(payload(), path, @other)) == {:error, :scope_mismatch}
    end
  end

  test "project filter matches exactly; nil filter accepts no project or any valid project" do
    body = put_in(payload(), ["data", "issue", "project"], %{"id" => @project})
    assert {:ok, out} = extract(body, %{scope() | project_id: @project})
    assert out.project_id == @project
    assert {:ok, _} = extract(body)
    assert extract(body, %{scope() | project_id: @other}) == {:error, :scope_mismatch}
    assert extract(payload(), %{scope() | project_id: @project}) == {:error, :scope_mismatch}
  end

  test "UUID text case is normalized for binding and all returned IDs" do
    body = put_in(payload(), ["data", "issue", "project"], %{"id" => @project})

    paths = [
      ["data", "organization", "id"],
      ["data", "issue", "id"],
      ["data", "issue", "team", "id"],
      ["data", "issue", "state", "id"],
      ["data", "issue", "state", "team", "id"],
      ["data", "issue", "project", "id"]
    ]

    upper = Enum.reduce(paths, body, fn path, data -> update_in(data, path, &String.upcase/1) end)
    pins = Map.new(%{scope() | project_id: @project}, fn {k, v} -> {k, String.upcase(v)} end)

    assert extract(upper, pins, %{String.upcase(@state) => "review"}) ==
             extract(body, %{scope() | project_id: @project}, %{@state => "review"})
  end

  test "null issue is not_found only after workspace validation" do
    body = put_in(payload(), ["data", "issue"], nil)
    assert extract(body) == {:error, :not_found}

    assert extract(put_in(body, ["data", "organization", "id"], @other)) ==
             {:error, :scope_mismatch}
  end

  test "removing every required issue field and nested ID returns invalid_response" do
    for key <- Map.keys(payload()["data"]["issue"]) do
      assert extract(update_in(payload(), ["data", "issue"], &Map.delete(&1, key))) ==
               {:error, :invalid_response}
    end

    for path <- [
          ["data", "organization", "id"],
          ["data", "issue", "team", "id"],
          ["data", "issue", "state", "id"],
          ["data", "issue", "state", "team", "id"]
        ] do
      parent = Enum.drop(path, -1)

      assert extract(update_in(payload(), parent, &Map.delete(&1, "id"))) ==
               {:error, :invalid_response}
    end
  end

  test "invalid UUIDs and malformed nested objects cannot be normalized into success" do
    for path <- [
          ["data", "organization", "id"],
          ["data", "issue", "id"],
          ["data", "issue", "team", "id"],
          ["data", "issue", "state", "id"],
          ["data", "issue", "state", "team", "id"]
        ],
        bad <- [nil, [], 1, "TEAM-1", @state <> "\n", <<255>> <> String.duplicate("a", 35)] do
      assert extract(put_in(payload(), path, bad)) == {:error, :invalid_response}
    end

    for path <- [
          ["data", "issue"],
          ["data", "issue", "team"],
          ["data", "issue", "state"],
          ["data", "issue", "state", "team"],
          ["data", "issue", "project"]
        ],
        bad <- [%{}, %URI{}, [], true, "private"] do
      assert extract(put_in(payload(), path, bad)) == {:error, :invalid_response}
    end
  end

  test "archived responses are distinguished and unknown archive values fail" do
    for archived <- ["2026-01-01T10:00:00Z", "2026-01-01T11:00:00+01:00"] do
      assert extract(put_in(payload(), ["data", "issue", "archivedAt"], archived)) ==
               {:error, :archived}
    end

    for archived <- [false, 0, "", "yesterday", <<255>>, String.duplicate("x", 1000)] do
      assert extract(put_in(payload(), ["data", "issue", "archivedAt"], archived)) ==
               {:error, :invalid_response}
    end
  end

  test "mapping errors and unknown valid state are delegated to real StatusMap" do
    assert extract(payload(), scope(), %{@other => "started"}) == {:error, :unknown_status}

    assert extract(payload(), scope(), %{@state => "started", @other => "INVALID"}) ==
             {:error, :invalid_mapping}

    assert extract(payload(), scope(), %{@state => "started", String.upcase(@state) => "started"}) ==
             {:error, :invalid_mapping}

    assert extract(payload(), scope(), %{}) == {:error, :invalid_mapping}
  end

  test "unrelated fields are ignored and never echo into the safe result" do
    body =
      update_in(
        payload(),
        ["data", "issue"],
        &Map.merge(&1, %{"title" => "private", "admitted" => true, "identifier" => "FAKE-1"})
      )

    assert extract(body) == extract(payload())
  end
end
