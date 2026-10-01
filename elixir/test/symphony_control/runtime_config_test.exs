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

  test "CLI boundary applies control env before the injected startup callback" do
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

  test "CLI boundary rejects explicit enablement without a database URL" do
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

  test "merged runtime configuration survives application loading in a fresh VM" do
    result = configuration_load_probe("enabled")
    assert result["before_load"]
    assert result["after_load"]
    assert result["database_preserved"]
    assert result["identity_preserved"]
    refute result["application_started"]
  end

  test "merged configuration keeps control disabled without explicit opt-in" do
    result = configuration_load_probe("disabled")
    refute result["before_load"]
    refute result["after_load"]
    refute result["application_started"]
  end

  test "omitting runtime configuration is a distinguishable negative control" do
    # Deliberately NOT the supported Mix escript path. This confirms that the
    # positive check would detect a missing runtime-config merge.
    result = configuration_load_probe("compile_only")
    assert result["before_load"]
    refute result["after_load"]
    refute result["application_started"]
  end

  defp configuration_load_probe(mode) do
    # Configuration/application-load UNIT fixture, not the generated escript.
    # It never calls CLI.main, Application.ensure_all_started, or a service.
    # Mirrors the documented Mix 1.19.6 config merge and persistent env writes.
    code = ~S"""
    [mode, root] = System.argv()
    false = Enum.any?(Application.loaded_applications(), &(elem(&1, 0) == :symphony_elixir))
    keys = ~w(SYMPHONY_CONTROL_ENABLED SYMPHONY_CONTROL_DATABASE_URL SYMPHONY_CONTROL_COMMIT_SHA SYMPHONY_CONTROL_IMAGE_DIGEST SYMPHONY_CONTROL_CONFIG_SHA256)
    Enum.each(keys, &System.delete_env/1)
    database = "postgresql://sn004_fixture@localhost/sn004_test"
    commit = String.duplicate("a", 40)

    unless mode == "disabled" do
      System.put_env("SYMPHONY_CONTROL_ENABLED", "true")
      System.put_env("SYMPHONY_CONTROL_DATABASE_URL", database)
      System.put_env("SYMPHONY_CONTROL_COMMIT_SHA", commit)
    end

    compile_config = Config.Reader.read!(Path.join(root, "config/config.exs"), env: :test, target: :host)
    runtime_config =
      if mode == "compile_only" do
        []
      else
        path = Path.join(root, "config/runtime.exs")
        Config.Reader.eval!(path, File.read!(path), env: :test, target: :host, imports: :disabled)
      end

    Config.Reader.merge(compile_config, runtime_config)
    |> Enum.each(fn {app, settings} ->
      Enum.each(settings, fn {key, value} ->
        :ok = :application.set_env(app, key, value, persistent: true)
      end)
    end)

    :ok = SymphonyControl.RuntimeConfig.configure()
    before_load = Application.fetch_env!(:symphony_elixir, :control_enabled)
    :ok = Application.load(:symphony_elixir)
    repo = Application.get_env(:symphony_elixir, SymphonyControl.Repo, [])
    identity = Application.get_env(:symphony_elixir, :runtime_identity, [])
    result = %{
      before_load: before_load,
      after_load: Application.fetch_env!(:symphony_elixir, :control_enabled),
      database_preserved: repo[:url] == database and repo[:show_sensitive_data_on_connection_error] == false,
      identity_preserved: identity[:commit_sha] == commit,
      application_started: Enum.any?(Application.started_applications(), &(elem(&1, 0) == :symphony_elixir))
    }
    IO.puts("GH22_CONFIG_LOAD=" <> Jason.encode!(result))
    """

    executable = System.find_executable("elixir") || raise "elixir executable is required"
    code_paths = Enum.flat_map(:code.get_path(), fn path -> ["-pz", List.to_string(path)] end)
    args = code_paths ++ ["--erl", "+S 2:2 +SDcpu 1 +SDio 1 -no_dot_erlang", "-e", code, "--", mode, File.cwd!()]
    port = Port.open({:spawn_executable, executable}, [:binary, :exit_status, :stderr_to_stdout, args: args])
    {:os_pid, pid} = Port.info(port, :os_pid)

    try do
      {output, status} = collect_probe(port, System.monotonic_time(:millisecond) + 15_000, "")
      assert status == 0, output
      line = Enum.find(String.split(output, "\n"), &String.starts_with?(&1, "GH22_CONFIG_LOAD="))
      assert is_binary(line), output
      line |> String.replace_prefix("GH22_CONFIG_LOAD=", "") |> Jason.decode!()
    after
      if Port.info(port) do
        System.cmd("/bin/sh", ["-c", "kill -KILL \"$1\"", "gh22-config-probe", Integer.to_string(pid)], stderr_to_stdout: true)

        try do
          Port.close(port)
        rescue
          ArgumentError -> :ok
        end
      end
    end
  end

  defp collect_probe(port, deadline, output) do
    assert byte_size(output) <= 65_536, "configuration probe output exceeded limit"
    remaining = max(0, deadline - System.monotonic_time(:millisecond))

    receive do
      {^port, {:data, data}} -> collect_probe(port, deadline, output <> data)
      {^port, {:exit_status, status}} -> {output, status}
    after
      remaining -> flunk("configuration probe timed out")
    end
  end
end
