defmodule SymphonyControl.Tracker.StatusMap do
  @moduledoc """
  Maps extracted tracker status fields to business categories.

  Validates the entire supplied scheme before classification. Results establish
  neither execution admission nor execution success, review or release approval.
  This module performs no provider calls or mutations.
  """

  @nonterminal ~w(triage backlog unstarted started review)
  @categories @nonterminal ++ ~w(completed canceled)
  @ascii_controls ~r/[\x00-\x1F\x7F]/
  @uuid ~r/\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z/
  @limit 256

  @type reason :: :invalid_input | :invalid_mapping | :unknown_status | :ambiguous_status | :contradictory_status
  @type result :: {:ok, String.t()} | {:error, reason()}

  @doc "Accepts an exact native business-category string."
  @spec native(term()) :: result()
  def native(category) do
    cond do
      not valid_text?(category) -> {:error, :invalid_input}
      category in @categories -> {:ok, category}
      true -> {:error, :unknown_status}
    end
  end

  @doc "Maps GitHub issue state/reason and exact managed label names."
  @spec github(term(), term(), term(), term(), term()) :: result()
  def github(state, state_reason, labels, mapping, default_category) do
    cond do
      not valid_text?(state) or not valid_reason?(state_reason) or not valid_labels?(labels, 0) ->
        {:error, :invalid_input}

      not valid_github_mapping?(mapping, default_category) ->
        {:error, :invalid_mapping}

      true ->
        github_category(state, state_reason, labels, mapping, default_category)
    end
  end

  @doc "Maps a UUID workflow-state ID using a fully validated Linear scheme."
  @spec linear(term(), term()) :: result()
  def linear(state_id, mapping) do
    if valid_uuid?(state_id) do
      with {:ok, normalized} <- normalize_linear_mapping(mapping) do
        case Map.fetch(normalized, String.downcase(state_id, :ascii)) do
          {:ok, category} -> {:ok, category}
          :error -> {:error, :unknown_status}
        end
      end
    else
      {:error, :invalid_input}
    end
  end

  defp valid_text?(text) when is_binary(text) do
    text != "" and String.valid?(text) and not Regex.match?(@ascii_controls, text)
  end

  defp valid_text?(_text), do: false

  defp valid_reason?(nil), do: true
  defp valid_reason?(reason), do: valid_text?(reason)

  defp valid_label?(label) do
    is_binary(label) and byte_size(label) <= @limit and valid_text?(label)
  end

  defp valid_labels?([], _count), do: true

  defp valid_labels?([label | rest], count) when count < @limit do
    valid_label?(label) and valid_labels?(rest, count + 1)
  end

  defp valid_labels?(_labels, _count), do: false

  defp valid_github_mapping?(mapping, default_category) when is_map(mapping) and not is_struct(mapping) do
    default_category in @nonterminal and map_size(mapping) <= @limit and
      Enum.all?(mapping, fn {label, category} -> valid_label?(label) and category in @nonterminal end)
  end

  defp valid_github_mapping?(_mapping, _default_category), do: false

  defp github_category("open", reason, labels, mapping, default_category) when reason in [nil, "reopened"] do
    managed_labels = labels |> Enum.uniq() |> Enum.filter(&Map.has_key?(mapping, &1))

    case managed_labels do
      [] -> {:ok, default_category}
      [label] -> {:ok, Map.fetch!(mapping, label)}
      _competing_labels -> {:error, :ambiguous_status}
    end
  end

  defp github_category("open", _reason, _labels, _mapping, _default_category), do: {:error, :contradictory_status}
  defp github_category("closed", "completed", _labels, _mapping, _default_category), do: {:ok, "completed"}
  defp github_category("closed", "not_planned", _labels, _mapping, _default_category), do: {:ok, "canceled"}
  defp github_category("closed", "reopened", _labels, _mapping, _default_category), do: {:error, :contradictory_status}
  defp github_category(_state, _reason, _labels, _mapping, _default_category), do: {:error, :unknown_status}

  defp valid_uuid?(uuid) do
    is_binary(uuid) and byte_size(uuid) == 36 and Regex.match?(@uuid, uuid)
  end

  defp normalize_linear_mapping(mapping) when is_map(mapping) and not is_struct(mapping) and map_size(mapping) in 1..@limit do
    Enum.reduce_while(mapping, {:ok, %{}}, fn {state_id, category}, {:ok, normalized} ->
      if valid_uuid?(state_id) and category in @categories do
        key = String.downcase(state_id, :ascii)

        if Map.has_key?(normalized, key) do
          {:halt, {:error, :invalid_mapping}}
        else
          {:cont, {:ok, Map.put(normalized, key, category)}}
        end
      else
        {:halt, {:error, :invalid_mapping}}
      end
    end)
  end

  defp normalize_linear_mapping(_mapping), do: {:error, :invalid_mapping}
end
