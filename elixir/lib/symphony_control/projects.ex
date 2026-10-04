defmodule SymphonyControl.Projects do
  @moduledoc """
  Internal project domain API for trusted control callers.

  The server selects `:project_authorizer` with `authorize(actor, action,
  scope)`. Create uses `:project_create`/`:platform`; read and rename use
  `:project_read` or `:project_rename` and the normalized project UUID.
  Missing or failing authorization denies access. No authenticated public
  endpoint, Authentik integration or agent capability is implemented here.

  Each call owns its bounded database work. Do not compose these calls inside
  another repository transaction. They never retry, migrate, open execution
  admission or accept commands/outbox work.
  """

  alias Ecto.Changeset
  alias SymphonyControl.{Error, Project, Repo}

  @db_options [timeout: 500, queue: false, log: false]
  @database_deadline_ms 750
  @maximum_revision 2_147_483_647
  @type create_attributes :: %{key: String.t(), name: String.t()}
  @type result :: {:ok, Project.t()} | {:error, Error.t()}

  @spec create_project(term(), term()) :: result()
  def create_project(actor, attrs) do
    with :ok <- authorize(actor, :project_create, :platform),
         :ok <- validate_attributes(attrs) do
      id = Ecto.UUID.generate()

      database(:write, id, fn ->
        %Project{id: id}
        |> Changeset.change(Map.take(attrs, [:key, :name]))
        |> Changeset.unique_constraint(:key)
        |> Repo.insert(@db_options)
        |> mutation_result(:key)
      end)
    end
  end

  @spec get_project(term(), term()) :: result()
  def get_project(actor, id) do
    with {:ok, uuid} <- project_id(id),
         :ok <- authorize(actor, :project_read, uuid) do
      database(:read, uuid, fn -> fetch_project(uuid) end)
    end
  end

  @spec rename_project(term(), term(), term(), term()) :: result()
  def rename_project(actor, id, expected_version, name) do
    with {:ok, uuid} <- project_id(id),
         :ok <- authorize(actor, :project_rename, uuid),
         :ok <- validate_rename(expected_version, name) do
      database(:write, uuid, fn -> rename(uuid, expected_version, name) end)
    end
  end

  defp rename(id, expected_version, name) do
    with {:ok, project} <- fetch_project(id) do
      if project.lock_version == expected_version and expected_version < @maximum_revision do
        project
        |> Changeset.change(name: name)
        |> Changeset.optimistic_lock(:lock_version, &(&1 + 1))
        |> Repo.update(Keyword.put(@db_options, :stale_error_field, :lock_version))
        |> mutation_result(:lock_version)
      else
        error(:conflict, [:lock_version])
      end
    end
  end

  defp fetch_project(id) do
    case Repo.get(Project, id, @db_options) do
      nil -> error(:not_found)
      project -> {:ok, project}
    end
  end

  defp mutation_result({:ok, project}, _field), do: {:ok, project}
  defp mutation_result({:error, %Changeset{}}, field), do: error(:conflict, [field])

  defp project_id(value) when is_binary(value) do
    case Ecto.UUID.cast(value) do
      {:ok, uuid} -> {:ok, uuid}
      :error -> error(:invalid_input, [:id])
    end
  end

  defp project_id(_value), do: error(:invalid_input, [:id])

  defp validate_attributes(attrs) when is_map(attrs) do
    if Enum.all?(Map.keys(attrs), &(&1 in [:key, :name])) do
      fields = Enum.reject([:key, :name], &valid_text?(Map.get(attrs, &1)))
      if fields == [], do: :ok, else: error(:invalid_input, fields)
    else
      error(:invalid_input, [:attributes])
    end
  end

  defp validate_attributes(_attrs), do: error(:invalid_input, [:attributes])

  defp validate_rename(version, name) do
    cond do
      not (is_integer(version) and version > 0 and version <= @maximum_revision) ->
        error(:invalid_input, [:lock_version])

      not valid_text?(name) ->
        error(:invalid_input, [:name])

      true ->
        :ok
    end
  end

  defp valid_text?(value) when is_binary(value) do
    String.valid?(value) and not String.contains?(value, <<0>>) and String.trim(value) != ""
  end

  defp valid_text?(_value), do: false

  defp authorize(actor, action, scope) do
    authorizer = Application.get_env(:symphony_elixir, :project_authorizer)

    with module when is_atom(module) and not is_nil(module) <- authorizer,
         :ok <- module.authorize(actor, action, scope) do
      :ok
    else
      _denied -> error(:forbidden)
    end
  rescue
    _error -> error(:forbidden)
  catch
    _kind, _reason -> error(:forbidden)
  end

  defp database(mode, id, operation) do
    if Process.whereis(Repo) do
      unavailable = database_error(mode, id)
      task = Task.async(fn -> safe_operation(operation, unavailable) end)

      case Task.yield(task, @database_deadline_ms) || Task.shutdown(task, :brutal_kill) do
        {:ok, result} -> result
        _unconfirmed -> unavailable
      end
    else
      error(:dependency_unavailable)
    end
  end

  defp safe_operation(operation, unavailable) do
    operation.()
  rescue
    _error -> unavailable
  catch
    :exit, _reason -> unavailable
  end

  defp database_error(:read, _id), do: error(:dependency_unavailable)
  defp database_error(:write, id), do: {:error, %Error{code: :unknown_outcome, reference_id: id}}
  defp error(code, fields \\ []), do: {:error, %Error{code: code, fields: fields}}
end
