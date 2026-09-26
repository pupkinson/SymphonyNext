defmodule SymphonyControl.RepoTest do
  use ExUnit.Case, async: false

  alias SymphonyControl.Repo

  setup_all do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    :ok
  end

  test "the control repository can read the isolated PostgreSQL fixture" do
    socket = System.fetch_env!("SN004_TEST_PG_SOCKET")

    connection = [
      socket_dir: socket,
      port: 55_474,
      username: "sn004_fixture",
      database: "sn004_test",
      pool_size: 2,
      timeout: 1_000,
      log: false
    ]

    start_supervised!({Repo, connection})

    assert %{rows: [[1]]} = Repo.query!("SELECT 1", [])
  end
end
