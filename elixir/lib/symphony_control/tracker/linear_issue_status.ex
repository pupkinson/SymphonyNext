defmodule SymphonyControl.Tracker.LinearIssueStatus do
  @moduledoc """
  Validates one decoded Linear GraphQL issue-status response against pinned scope.

  This pure extraction boundary consumes an authenticated transport's response,
  not user assertions or webhook data. It checks shape and scope consistency,
  not transport authenticity, token permissions, freshness or execution admission.
  Binding has exactly workspace_id, team_id, project_id (UUID or nil), issue_id.
  All UUIDs normalize by case. State.team must match the issue's pinned team.
  Nonempty GraphQL errors reject partial data. Null issue is not_found, not proof
  of deletion. Archive, unknown state and failed mapping never become completed.
  Only safe identifiers and a business category are returned; no private text.
  """
  alias SymphonyControl.Tracker.StatusMap

  defguardp plain(value) when is_map(value) and not is_struct(value)
  @uuid ~r/\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z/
  @type reason ::
          :invalid_binding
          | :invalid_response
          | :scope_mismatch
          | :not_found
          | :archived
          | :graphql_error
          | :forbidden
          | :rate_limited
          | :unavailable
          | :unexpected_http_status
          | StatusMap.reason()
  @spec extract(term(), term(), term(), term()) :: {:ok, map()} | {:error, reason()}
  def extract(http_status, body, binding, mapping) do
    with {:ok, pins} <- binding_values(binding) do
      response(http_status, body, pins, mapping)
    end
  end

  defp binding_values(%{workspace_id: w, team_id: t, project_id: p, issue_id: i} = value)
       when plain(value) and map_size(value) == 4 do
    with {:ok, w} <- uuid(w),
         {:ok, t} <- uuid(t),
         {:ok, p} <- optional_uuid(p),
         {:ok, i} <- uuid(i) do
      {:ok, %{workspace_id: w, team_id: t, project_id: p, issue_id: i}}
    else
      _invalid -> {:error, :invalid_binding}
    end
  end

  defp binding_values(_value), do: {:error, :invalid_binding}

  defp response(code, _body, _pins, _mapping) when code in [401, 403], do: {:error, :forbidden}
  defp response(429, _body, _pins, _mapping), do: {:error, :rate_limited}

  defp response(code, _body, _pins, _mapping) when is_integer(code) and code in 500..599,
    do: {:error, :unavailable}

  defp response(200, body, pins, mapping) when plain(body) do
    with :ok <- errors(body) do
      response_data(Map.get(body, "data"), pins, mapping)
    end
  end

  defp response(200, _body, _pins, _mapping), do: {:error, :invalid_response}

  defp response(code, _body, _pins, _mapping) when is_integer(code) and code in 100..599,
    do: {:error, :unexpected_http_status}

  defp response(_code, _body, _pins, _mapping), do: {:error, :invalid_response}

  defp errors(body) do
    case Map.fetch(body, "errors") do
      :error ->
        :ok

      {:ok, []} ->
        :ok

      {:ok, [_ | _] = items} ->
        if bounded_list?(items, 0),
          do: {:error, :graphql_error},
          else: {:error, :invalid_response}

      _invalid ->
        {:error, :invalid_response}
    end
  end

  defp bounded_list?([], _count), do: true
  defp bounded_list?([_ | rest], count) when count < 256, do: bounded_list?(rest, count + 1)
  defp bounded_list?(_value, _count), do: false

  defp response_data(%{"organization" => organization, "issue" => issue} = data, pins, mapping)
       when plain(data) do
    with {:ok, workspace} <- object_id(organization) do
      if workspace == pins.workspace_id,
        do: issue_data(issue, pins, mapping),
        else: {:error, :scope_mismatch}
    end
  end

  defp response_data(_data, _pins, _mapping), do: {:error, :invalid_response}

  defp issue_data(nil, _pins, _mapping), do: {:error, :not_found}

  defp issue_data(
         %{
           "id" => issue,
           "team" => team,
           "state" => state,
           "project" => project,
           "archivedAt" => archived
         } = data,
         pins,
         mapping
       )
       when plain(data) do
    with {:ok, issue} <- uuid(issue),
         {:ok, team} <- object_id(team),
         {:ok, project} <- project_id(project),
         {:ok, {state, state_team}} <- state_ids(state),
         :ok <- matches(pins, issue, team, project, state_team),
         :ok <- active_archive(archived),
         {:ok, category} <- StatusMap.linear(state, mapping) do
      {:ok,
       %{
         provider: :linear,
         workspace_id: pins.workspace_id,
         team_id: team,
         project_id: project,
         issue_id: issue,
         state_id: state,
         category: category
       }}
    end
  end

  defp issue_data(_data, _pins, _mapping), do: {:error, :invalid_response}

  defp matches(pins, issue, team, project, state_team) do
    if issue == pins.issue_id and team == pins.team_id and state_team == pins.team_id and
         (is_nil(pins.project_id) or project == pins.project_id),
       do: :ok,
       else: {:error, :scope_mismatch}
  end

  defp state_ids(%{"id" => id, "team" => team} = state) when plain(state) do
    with {:ok, id} <- uuid(id), {:ok, team} <- object_id(team), do: {:ok, {id, team}}
  end

  defp state_ids(_state), do: {:error, :invalid_response}
  defp object_id(%{"id" => id} = value) when plain(value), do: uuid(id)
  defp object_id(_value), do: {:error, :invalid_response}
  defp project_id(nil), do: {:ok, nil}
  defp project_id(value), do: object_id(value)
  defp optional_uuid(nil), do: {:ok, nil}
  defp optional_uuid(value), do: uuid(value)

  defp active_archive(nil), do: :ok

  defp active_archive(value) when is_binary(value) and byte_size(value) in 1..64 do
    if String.valid?(value) do
      case DateTime.from_iso8601(value) do
        {:ok, _datetime, _offset} -> {:error, :archived}
        _invalid -> {:error, :invalid_response}
      end
    else
      {:error, :invalid_response}
    end
  end

  defp active_archive(_value), do: {:error, :invalid_response}

  defp uuid(value) when is_binary(value) and byte_size(value) == 36 do
    if Regex.match?(@uuid, value),
      do: {:ok, String.downcase(value, :ascii)},
      else: {:error, :invalid_response}
  end

  defp uuid(_value), do: {:error, :invalid_response}
end
