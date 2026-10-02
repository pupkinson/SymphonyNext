defmodule SymphonyControl.Tracker.StatusMapTest do
  use ExUnit.Case, async: true

  alias SymphonyControl.Tracker.StatusMap

  @categories ~w(triage backlog unstarted started review completed canceled)
  @nonterminal ~w(triage backlog unstarted started review)
  @state_id "a1b2c3d4-1234-4567-89ab-abcdef012345"
  @other_id "b2c3d4e5-2345-4678-9abc-bcdef0123456"
  @mapping %{"workflow:todo" => "unstarted", "workflow:doing" => "started"}
  @wrong_types [nil, :started, 1, 1.0, true, [], ["started"], %{}, {"started"}, <<1::size(1)>>]
  @invalid_text ["", <<255>>, <<192, 175>>, "bad\ntext", "bad\rtext", "bad\ttext", <<0>>, <<127>>]

  describe "native/1" do
    for category <- @categories do
      test "accepts exactly #{category}" do
        category = unquote(category)
        assert StatusMap.native(category) == {:ok, category}
      end
    end

    test "does not trim, fold case, translate or guess unknown categories" do
      for category <- ["Todo", "STARTED", " started", "started ", "in_progress", "готово", " ", String.duplicate("x", 257)] do
        assert StatusMap.native(category) == {:error, :unknown_status}
      end
    end

    test "rejects malformed strings and non-string categories" do
      for category <- @wrong_types ++ @invalid_text do
        assert StatusMap.native(category) == {:error, :invalid_input}
      end
    end

    test "rejects every ASCII control character even inside a category" do
      for control <- Enum.to_list(0..31) ++ [127] do
        assert StatusMap.native("started" <> <<control>>) == {:error, :invalid_input}
      end
    end
  end

  describe "github/5 open issues" do
    for category <- @nonterminal do
      test "uses the #{category} default without managed labels" do
        category = unquote(category)
        assert StatusMap.github("open", nil, [], %{}, category) == {:ok, category}
        assert StatusMap.github("open", "reopened", ["unmanaged"], @mapping, category) == {:ok, category}
      end

      test "maps a single managed label to #{category}" do
        category = unquote(category)
        assert StatusMap.github("open", nil, ["workflow", "other"], %{"workflow" => category}, "triage") == {:ok, category}
      end
    end

    test "counts duplicate occurrences of one managed label only once" do
      assert StatusMap.github("open", "reopened", ["workflow:doing", "other", "workflow:doing"], @mapping, "triage") == {:ok, "started"}
    end

    test "rejects competing labels regardless of order or duplicates" do
      for labels <- [["workflow:todo", "workflow:doing"], ["workflow:doing", "workflow:todo", "workflow:doing"]] do
        assert StatusMap.github("open", nil, labels, @mapping, "triage") == {:error, :ambiguous_status}
      end
    end

    test "rejects distinct managed labels even when their categories agree" do
      mapping = %{"first" => "started", "second" => "started"}
      assert StatusMap.github("open", nil, ["first", "second"], mapping, "triage") == {:error, :ambiguous_status}
    end

    test "matches labels exactly without case, whitespace or Unicode normalization" do
      mapping = %{"Doing" => "started", "é" => "review"}
      assert StatusMap.github("open", nil, ["doing", " Doing", "Doing ", "e\u0301"], mapping, "backlog") == {:ok, "backlog"}
      assert StatusMap.github("open", nil, ["é"], mapping, "backlog") == {:ok, "review"}
      assert StatusMap.github("open", nil, [" "], %{" " => "review"}, "backlog") == {:ok, "review"}
    end

    test "rejects every valid reason other than nil or reopened" do
      for reason <- ["completed", "not_planned", "future_reason", "REOPENED", " reopened", " ", String.duplicate("r", 257)] do
        assert StatusMap.github("open", reason, [], %{}, "triage") == {:error, :contradictory_status}
      end
    end
  end

  describe "github/5 closed issues" do
    for {reason, expected} <- [
          {"completed", {:ok, "completed"}},
          {"not_planned", {:ok, "canceled"}},
          {nil, {:error, :unknown_status}},
          {"future_reason", {:error, :unknown_status}},
          {"COMPLETED", {:error, :unknown_status}},
          {" completed", {:error, :unknown_status}},
          {" ", {:error, :unknown_status}},
          {"reopened", {:error, :contradictory_status}}
        ] do
      test "classifies reason #{inspect(reason)} with and without stale workflow labels" do
        for labels <- [[], ["workflow:todo", "workflow:doing", "workflow:doing"]] do
          assert StatusMap.github("closed", unquote(reason), labels, @mapping, "triage") == unquote(Macro.escape(expected))
        end
      end
    end
  end

  describe "github/5 validation" do
    test "returns unknown_status for unrecognized well-formed states" do
      for state <- ["pending", "OPEN", "Closed", " open", "closed ", " "] do
        assert StatusMap.github(state, nil, [], %{}, "triage") == {:error, :unknown_status}
      end
    end

    test "rejects malformed states before classification" do
      for state <- @wrong_types ++ @invalid_text do
        assert StatusMap.github(state, nil, [], %{}, "triage") == {:error, :invalid_input}
      end
    end

    test "rejects malformed reasons for open, closed and unknown states" do
      for state <- ["open", "closed", "unknown"], reason <- Enum.reject(@wrong_types, &is_nil/1) ++ @invalid_text do
        assert StatusMap.github(state, reason, [], %{}, "triage") == {:error, :invalid_input}
      end
    end

    test "requires a proper list of label-name strings" do
      for labels <- [nil, "workflow:doing", :labels, %{}, {"label"}, ["valid" | "tail"], ["valid" | nil]] do
        assert StatusMap.github("open", nil, labels, %{}, "triage") == {:error, :invalid_input}
      end
    end

    test "validates every label even after a managed match or terminal reason" do
      for {state, reason} <- [{"open", nil}, {"closed", "completed"}, {"closed", "not_planned"}, {"unknown", nil}],
          invalid <- @wrong_types ++ @invalid_text ++ [String.duplicate("x", 257), %{"name" => "label"}] do
        assert StatusMap.github(state, reason, ["workflow:doing", invalid], @mapping, "triage") == {:error, :invalid_input}
      end
    end

    test "validates every mapping key including unused entries for all issue states" do
      for {state, reason} <- [{"open", nil}, {"closed", "completed"}, {"closed", "not_planned"}, {"unknown", nil}],
          key <- @wrong_types ++ @invalid_text ++ [String.duplicate("x", 257)] do
        mapping = Map.put(@mapping, key, "review")
        assert StatusMap.github(state, reason, ["workflow:doing"], mapping, "triage") == {:error, :invalid_mapping}
      end
    end

    test "validates every mapping target including unused and terminal categories" do
      for {state, reason} <- [{"open", nil}, {"closed", "completed"}, {"unknown", nil}],
          category <- @wrong_types ++ @invalid_text ++ ["completed", "canceled", "STARTED", "started ", "unknown"] do
        mapping = Map.put(@mapping, "unused", category)
        assert StatusMap.github(state, reason, ["workflow:doing"], mapping, "triage") == {:error, :invalid_mapping}
      end
    end

    test "rejects non-map schemas and structs" do
      for mapping <- [nil, [], [{"workflow:doing", "started"}], "mapping", :mapping, %URI{}] do
        assert StatusMap.github("open", nil, [], mapping, "triage") == {:error, :invalid_mapping}
      end
    end

    test "validates defaults even when a label or closed state determines the result" do
      for {state, reason} <- [{"open", nil}, {"closed", "completed"}, {"closed", "not_planned"}],
          default <- @wrong_types ++ @invalid_text ++ ["completed", "canceled", "unknown", "STARTED", "started "] do
        assert StatusMap.github(state, reason, ["workflow:doing"], @mapping, default) == {:error, :invalid_mapping}
      end
    end

    test "enforces label and mapping-key lengths in bytes" do
      for label <- [String.duplicate("x", 256), String.duplicate("я", 128)] do
        assert StatusMap.github("open", nil, [label], %{label => "review"}, "triage") == {:ok, "review"}
        assert StatusMap.github("open", nil, [label <> "x"], %{}, "triage") == {:error, :invalid_input}
        assert StatusMap.github("open", nil, [], %{(label <> "x") => "review"}, "triage") == {:error, :invalid_mapping}
      end
    end

    test "counts all label occurrences toward the 256-label input limit" do
      assert StatusMap.github("open", nil, List.duplicate("workflow:doing", 256), @mapping, "triage") == {:ok, "started"}
      assert StatusMap.github("open", nil, List.duplicate("workflow:doing", 257), @mapping, "triage") == {:error, :invalid_input}
      assert StatusMap.github("closed", "completed", List.duplicate("unmanaged", 257), %{}, "triage") == {:error, :invalid_input}
    end

    test "accepts 256 mapping entries and rejects 257 even if unused" do
      mapping = Map.new(1..256, fn index -> {"label-#{index}", "started"} end)
      assert StatusMap.github("open", nil, ["label-256"], mapping, "triage") == {:ok, "started"}
      assert StatusMap.github("closed", "completed", [], Map.put(mapping, "extra", "review"), "triage") == {:error, :invalid_mapping}
    end

    test "rejects every ASCII control character in states, reasons, labels and mapping keys" do
      for control <- Enum.to_list(0..31) ++ [127] do
        text = "text" <> <<control>>
        assert StatusMap.github(text, nil, [], %{}, "triage") == {:error, :invalid_input}
        assert StatusMap.github("closed", text, [], %{}, "triage") == {:error, :invalid_input}
        assert StatusMap.github("closed", "completed", [text], %{}, "triage") == {:error, :invalid_input}
        assert StatusMap.github("closed", "completed", [], %{text => "started"}, "triage") == {:error, :invalid_mapping}
      end
    end
  end

  describe "linear/2" do
    for category <- @categories do
      test "maps UUIDs to #{category}" do
        category = unquote(category)
        assert StatusMap.linear(@state_id, %{@state_id => category}) == {:ok, category}
      end
    end

    test "matches hexadecimal UUID text case in both input and mapping" do
      for state_id <- [@state_id, String.upcase(@state_id)], key <- [@state_id, String.upcase(@state_id)] do
        assert StatusMap.linear(state_id, %{key => "review"}) == {:ok, "review"}
      end
    end

    test "returns unknown_status for a well-formed unmapped UUID" do
      assert StatusMap.linear(@other_id, %{@state_id => "started"}) == {:error, :unknown_status}
    end

    test "rejects malformed IDs instead of treating names, issue keys or aliases as states" do
      for state_id <- @wrong_types ++ @invalid_text ++ invalid_uuids() do
        assert StatusMap.linear(state_id, %{@state_id => "started"}) == {:error, :invalid_input}
      end
    end

    test "rejects empty, oversized and non-map schemas" do
      for mapping <- [%{}, nil, [], [{@state_id, "started"}], "mapping", :mapping, %URI{}] do
        assert StatusMap.linear(@state_id, mapping) == {:error, :invalid_mapping}
      end

      mapping = Map.new(1..257, fn index -> {uuid(index), "started"} end)
      assert StatusMap.linear(uuid(1), mapping) == {:error, :invalid_mapping}
    end

    test "accepts 256 valid mapping entries and looks up the last entry" do
      mapping = Map.new(1..256, fn index -> {uuid(index), "started"} end)
      assert StatusMap.linear(uuid(256), mapping) == {:ok, "started"}
    end

    test "validates every mapping key before returning a match or unknown status" do
      for key <- @wrong_types ++ @invalid_text ++ invalid_uuids(), state_id <- [@state_id, @other_id] do
        assert StatusMap.linear(state_id, %{@state_id => "started", key => "review"}) == {:error, :invalid_mapping}
      end
    end

    test "validates every mapping target before returning a match or unknown status" do
      for category <- @wrong_types ++ @invalid_text ++ ["Todo", "STARTED", "started ", "unknown"],
          state_id <- [@state_id, uuid(0)] do
        assert StatusMap.linear(state_id, %{@state_id => "started", @other_id => category}) == {:error, :invalid_mapping}
      end
    end

    test "rejects duplicate normalized keys even for equal targets or unused states" do
      for category <- ["started", "review"], state_id <- [@state_id, @other_id, uuid(0)] do
        mapping = %{@state_id => "started", String.upcase(@state_id) => category, @other_id => "completed"}
        assert StatusMap.linear(state_id, mapping) == {:error, :invalid_mapping}
      end
    end
  end

  test "returns only category tuples and fixed errors, never execution admission or echoed input" do
    for category <- @categories do
      assert StatusMap.native(category) == {:ok, category}
      assert StatusMap.linear(@state_id, %{@state_id => category}) == {:ok, category}
    end

    assert StatusMap.github("closed", "completed", [], %{}, "triage") == {:ok, "completed"}
    assert StatusMap.github("closed", "not_planned", [], %{}, "triage") == {:ok, "canceled"}
    assert StatusMap.github("open", nil, [], %{}, "unstarted") == {:ok, "unstarted"}
    assert StatusMap.native("private-status-do-not-echo") == {:error, :unknown_status}
    assert StatusMap.github("closed", "private-reason-do-not-echo", [], %{}, "triage") == {:error, :unknown_status}
  end

  defp invalid_uuids do
    [
      "In Progress",
      "В работе",
      "TEAM-123",
      "started",
      String.replace(@state_id, "-", ""),
      "{" <> @state_id <> "}",
      "urn:uuid:" <> @state_id,
      " " <> @state_id,
      @state_id <> " ",
      @state_id <> "\n",
      "g1b2c3d4-1234-4567-89ab-abcdef012345",
      "a1b2c3d-12345-4567-89ab-abcdef012345",
      "a1b2c3d4_1234-4567-89ab-abcdef012345",
      binary_part(@state_id, 0, 35),
      @state_id <> "0"
    ]
  end

  defp uuid(index) do
    "00000000-0000-4000-8000-" <> String.pad_leading(Integer.to_string(index, 16), 12, "0")
  end
end
