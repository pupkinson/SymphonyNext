defmodule SymphonyControl.Health do
  @moduledoc """
  Bounded, read-only liveness and PostgreSQL schema readiness.

  Readiness never creates Ecto's migration table, applies migrations or opens
  execution admission. SQL and connection errors remain inside the boundary.
  """

  alias SymphonyControl.Repo

  @timeout_ms 500
  @schema_versions [[20_260_925_000_000]]

  # This is the required contract of CreateProjects, not a general schema audit.
  # Catalog expressions use PostgreSQL's non-pretty deparser representation.
  @projects_contract_sql """
  WITH relation AS (
    SELECT oid FROM pg_catalog.pg_class
    WHERE oid = pg_catalog.to_regclass('projects') AND relkind = 'r'
  ), expected_columns (name, type, modifier, default_expression) AS (
    VALUES
      ('id', 'uuid'::pg_catalog.regtype, -1, NULL::text),
      ('key', 'text'::pg_catalog.regtype, -1, NULL::text),
      ('name', 'text'::pg_catalog.regtype, -1, NULL::text),
      ('lock_version', 'integer'::pg_catalog.regtype, -1, '1'),
      ('inserted_at', 'timestamp'::pg_catalog.regtype, -1, NULL::text),
      ('updated_at', 'timestamp'::pg_catalog.regtype, -1, NULL::text)
  ), expected_checks (name, expression) AS (
    VALUES
      ('projects_key_not_blank', '(length(btrim(key)) > 0)'),
      ('projects_name_not_blank', '(length(btrim(name)) > 0)'),
      ('projects_lock_version_positive', '(lock_version > 0)')
  )
  SELECT EXISTS (SELECT FROM relation)
    AND NOT EXISTS (
      SELECT FROM expected_columns e
      LEFT JOIN pg_catalog.pg_attribute a
        ON a.attrelid = (SELECT oid FROM relation)
        AND a.attname = e.name AND a.attnum > 0 AND NOT a.attisdropped
      LEFT JOIN pg_catalog.pg_attrdef d ON d.adrelid = a.attrelid AND d.adnum = a.attnum
      WHERE a.attname IS NULL OR NOT a.attnotnull
        OR a.atttypid IS DISTINCT FROM e.type
        OR a.atttypmod IS DISTINCT FROM e.modifier
        OR a.attidentity <> '' OR a.attgenerated <> ''
        OR pg_catalog.pg_get_expr(d.adbin, d.adrelid, false) IS DISTINCT FROM e.default_expression
    )
    AND NOT EXISTS (
      SELECT FROM (VALUES ('id', true), ('key', false)) AS required_key (name, primary_key)
      WHERE NOT EXISTS (
        SELECT FROM pg_catalog.pg_index i
        JOIN pg_catalog.pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
        WHERE i.indrelid = (SELECT oid FROM relation) AND a.attname = required_key.name
          AND i.indnkeyatts = 1 AND i.indisunique AND i.indimmediate
          AND i.indisvalid AND i.indisready AND i.indislive
          AND i.indpred IS NULL AND i.indexprs IS NULL
          AND (NOT required_key.primary_key OR i.indisprimary)
      )
    )
    AND NOT EXISTS (
      SELECT FROM expected_checks e
      LEFT JOIN pg_catalog.pg_constraint c
        ON c.conrelid = (SELECT oid FROM relation) AND c.conname = e.name AND c.contype = 'c'
      WHERE c.oid IS NULL OR NOT c.convalidated
        OR pg_catalog.pg_get_expr(c.conbin, c.conrelid, false) IS DISTINCT FROM e.expression
    )
  """

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
      query("SELECT id, key, name, lock_version, inserted_at, updated_at FROM projects LIMIT 0") == {:ok, []} and
      query(@projects_contract_sql) == {:ok, [[true]]}
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
