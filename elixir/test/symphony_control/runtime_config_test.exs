defmodule SymphonyControl.RuntimeConfigTest do
  use ExUnit.Case, async: false

  @keys ~w(SYMPHONY_CONTROL_ENABLED SYMPHONY_CONTROL_DATABASE_URL SYMPHONY_CONTROL_COMMIT_SHA SYMPHONY_CONTROL_IMAGE_DIGEST SYMPHONY_CONTROL_CONFIG_SHA256)

  setup do
    original = Map.new(@keys, &{&1, System.get_env(&1)})
    original_app = Map.new([:control_enabled, SymphonyControl.Repo, :runtime_identity], &{&1, Application.fetch_env(:symphony_elixir, &1)})
    Enum.each(@keys, &System.delete_env/1)

    on_exit(fn ->
      Enum.each(original, fn
        {key, nil} -> System.delete_env(key)
        {key, value} -> System.put_env(key, value)
      end)

      Enum.each(original_app, fn
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
      end)
    end)

    :ok
  end

  test "control remains disabled without explicit configuration" do
    config = Config.Reader.read!("config/runtime.exs", env: :test)
    refute Keyword.get(config[:symphony_elixir], :control_enabled, false)
  end

  test "explicit enablement requires a dedicated database configuration" do
    System.put_env("SYMPHONY_CONTROL_ENABLED", "true")
    assert_raise System.EnvError, fn -> Config.Reader.read!("config/runtime.exs", env: :test) end

    database = "postgresql://sn004_fixture@localhost/sn004_test"
    System.put_env("SYMPHONY_CONTROL_DATABASE_URL", database)
    config = Config.Reader.read!("config/runtime.exs", env: :test)[:symphony_elixir]
    assert config[:control_enabled]
    assert config[SymphonyControl.Repo][:url] == database
    refute config[SymphonyControl.Repo][:show_sensitive_data_on_connection_error]
  end

  test "escript CLI applies control env before app startup" do
    parent = self()
    database = "postgresql://sn004_fixture@localhost/sn004_test"
    System.put_env("SYMPHONY_CONTROL_ENABLED", "true")
    System.put_env("SYMPHONY_CONTROL_DATABASE_URL", database)
    commit = String.duplicate("a", 40)
    System.put_env("SYMPHONY_CONTROL_COMMIT_SHA", commit)

    deps = %{
      file_regular?: fn _path -> true end,
      set_workflow_file_path: fn _path -> :ok end,
      ensure_all_started: fn ->
        config = Application.get_env(:symphony_elixir, SymphonyControl.Repo, [])
        enabled = Application.get_env(:symphony_elixir, :control_enabled, false)
        identity = Application.get_env(:symphony_elixir, :runtime_identity, [])
        sensitive = config[:show_sensitive_data_on_connection_error]
        send(parent, {:booted_with, enabled, config[:url], sensitive, identity[:commit_sha]})
        {:ok, [:symphony_elixir]}
      end
    }

    assert :ok = SymphonyElixir.CLI.run("WORKFLOW.md", deps)
    assert_received {:booted_with, true, ^database, false, ^commit}
  end

  test "escript CLI refuses to start when explicitly enabled without database URL" do
    parent = self()
    System.put_env("SYMPHONY_CONTROL_ENABLED", "true")

    deps = %{
      file_regular?: fn _path -> true end,
      set_workflow_file_path: fn _path -> :ok end,
      ensure_all_started: fn ->
        send(parent, :started)
        {:ok, [:symphony_elixir]}
      end
    }

    assert {:error, message} = SymphonyElixir.CLI.run("WORKFLOW.md", deps)
    assert message =~ "SYMPHONY_CONTROL_DATABASE_URL"
    refute_received :started
  end
end
