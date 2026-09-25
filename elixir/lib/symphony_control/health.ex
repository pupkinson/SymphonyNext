defmodule SymphonyControl.Health do
  @moduledoc """
  Bounded, read-only liveness and PostgreSQL schema readiness.

  Readiness never creates Ecto's migration table, applies migrations or opens
  execution admission. SQL and connection errors remain inside the boundary.
  """

  alias SymphonyControl.Repo

  @timeout_ms 500
  @schema_versions [[20_260_925_000_000]]

  @spec live?() :: boolean()
  def live? do
    SymphonyControl.Application
    |> GenServer.call(:count_children, @timeout_ms)
    |> Keyword.has_key?(:specs)
  catch
    :exit, _reason -> false
  end

  @spec readiness() :: %{ready: boolean(), database: boolean(), schema: boolean()}
  def readiness do
    database = live?() and query("SELECT 1") == {:ok, [[1]]}
    schema = database and schema_ready?()
    %{ready: schema, database: database, schema: schema}
  end

  defp schema_ready? do
    query("SELECT version FROM schema_migrations ORDER BY version") == {:ok, @schema_versions} and
      query("SELECT id, key, name, lock_version, inserted_at, updated_at FROM projects LIMIT 0") == {:ok, []}
  end

  defp query(sql) do
    # A driver timeout starts after checkout; a stalled pool also needs a bound.
    task = Task.async(fn -> run_query(sql) end)

    case Task.yield(task, @timeout_ms) || Task.shutdown(task, :brutal_kill) do
      {:ok, result} -> result
      _ -> {:error, :dependency_unavailable}
    end
  end

  defp run_query(sql) do
    case Repo.query(sql, [], timeout: @timeout_ms, queue: false, log: false) do
      {:ok, result} -> {:ok, result.rows}
      {:error, _reason} -> {:error, :dependency_unavailable}
    end
  rescue
    _error -> {:error, :dependency_unavailable}
  catch
    :exit, _reason -> {:error, :dependency_unavailable}
  end
end
