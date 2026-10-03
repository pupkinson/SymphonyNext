defmodule SymphonyElixir.ControlEnvironmentTest do
  use SymphonyElixir.TestSupport

  alias SymphonyControl.{Repo, RuntimeConfig}
  alias SymphonyElixir.{SSH, SubprocessEnv}

  @database_url "SYMPHONY_CONTROL_DATABASE_URL"
  @canary "postgres://synthetic_user:synthetic_password@example.invalid/control_fixture"
  @ordinary "SYMP_TEST_ORDINARY_ENV"

  setup do
    root = Path.join(System.tmp_dir!(), "symphony-control-env-#{System.unique_integer([:positive])}")
    File.mkdir_p!(root)

    names = [@database_url, @ordinary, "SYMPHONY_CONTROL_ENABLED", "PATH", "BASH_ENV"]
    previous_env = Map.new(names, &{&1, System.get_env(&1)})
    keys = [Repo, :control_enabled, :runtime_identity]
    previous_config = Map.new(keys, &{&1, Application.fetch_env(:symphony_elixir, &1)})

    on_exit(fn ->
      Enum.each(previous_env, fn {name, value} -> restore_env(name, value) end)

      Enum.each(previous_config, fn
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
      end)

      File.rm_rf!(root)
    end)

    System.delete_env(@database_url)
    System.put_env(@ordinary, "ordinary-value")
    System.put_env("SYMPHONY_CONTROL_ENABLED", "true")
    Application.put_env(:symphony_elixir, :control_enabled, false)
    Application.delete_env(:symphony_elixir, Repo)

    %{root: root}
  end

  test "local Codex loses the database URL even when a shell profile introduces it", %{root: root} do
    workspace_root = Path.join(root, "workspaces")
    workspace = Path.join(workspace_root, "CONTROL-LOCAL")
    trace = Path.join(root, "codex.env")
    binary = Path.join(root, "fake-codex")
    profile = Path.join(root, "profile.sh")
    File.mkdir_p!(workspace)
    install_codex!(binary, trace)
    marker = Path.join(root, "profile-ran")
    File.write!(profile, "printf ran > '#{marker}'\nexport #{@database_url}='#{@canary}'\nexport SYMPHONY_CONTROL_ENABLED=true\nexport #{@ordinary}='ordinary-value'\n")
    System.put_env("BASH_ENV", profile)

    write_workflow_file!(Workflow.workflow_file_path(),
      workspace_root: workspace_root,
      codex_command: "#{binary} app-server"
    )

    assert {:ok, _result} = AppServer.run(workspace, "Check child environment", issue())
    assert File.read!(marker) == "ran"
    assert File.read!(trace) == "DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n"
    assert_credential_free_parent()
  end

  test "all local workspace hooks lose the database URL and keep ordinary environment", %{root: root} do
    trace = Path.join(root, "hooks.env")
    command = environment_report(trace)

    write_workflow_file!(Workflow.workflow_file_path(),
      workspace_root: Path.join(root, "workspaces"),
      hook_after_create: command,
      hook_before_run: command,
      hook_after_run: command,
      hook_before_remove: command
    )

    assert {:ok, workspace} = Workspace.create_for_issue(issue())
    assert :ok = Workspace.run_before_run_hook(workspace, issue())
    assert :ok = Workspace.run_after_run_hook(workspace, issue())
    assert {:ok, _removed} = Workspace.remove(workspace)
    assert File.read!(trace) == String.duplicate("DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n", 4)
    assert_credential_free_parent()
  end

  test "SSH command children lose the database URL including an explicit override", %{root: root} do
    trace = Path.join(root, "ssh.env")
    install_ssh!(root, environment_report(trace))

    assert {:ok, {"", 0}} = SSH.run("fixture.invalid", "printf ok")

    assert {:ok, {"", 0}} =
             SSH.run("fixture.invalid", "printf ok", env: [{@database_url, @canary}, {"SYMPHONY_CONTROL_ENABLED", "true"}, {@ordinary, "override-value"}])

    assert File.read!(trace) ==
             "DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n" <>
               "DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:override-value\n"

    assert_credential_free_parent()
  end

  test "SSH port children lose the database URL with either output mode", %{root: root} do
    trace = Path.join(root, "ssh-port.env")
    install_ssh!(root, environment_report(trace))

    for opts <- [[], [line: 128]] do
      assert {:ok, port} = SSH.start_port("fixture.invalid", "printf ok", opts)
      assert_receive {^port, {:exit_status, 0}}, 5_000
    end

    assert File.read!(trace) == String.duplicate("DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n", 2)
    assert_credential_free_parent()
  end

  test "remote Codex launch clears a database URL introduced on the worker", %{root: root} do
    workspace_root = Path.join(root, "workspaces")
    workspace = Path.join(workspace_root, "CONTROL-REMOTE")
    trace = Path.join(root, "remote-codex.env")
    binary = Path.join(root, "fake-codex")
    File.mkdir_p!(workspace)
    install_codex!(binary, trace)

    install_ssh!(root, """
    export #{@database_url}='#{@canary}'
    export SYMPHONY_CONTROL_ENABLED=true
    for arg do command="$arg"; done
    exec /bin/sh -c "$command"
    """)

    write_workflow_file!(Workflow.workflow_file_path(),
      workspace_root: workspace_root,
      codex_command: "#{binary} app-server"
    )

    assert {:ok, _result} =
             AppServer.run(workspace, "Check worker environment", issue(), worker_host: "fixture.invalid")

    assert File.read!(trace) == "DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n"
    assert_credential_free_parent()
  end

  test "children also run when the control database variable is absent", %{root: root} do
    System.delete_env(@database_url)
    trace = Path.join(root, "absent.env")
    install_ssh!(root, environment_report(trace))

    assert {:ok, {"", 0}} = SSH.run("fixture.invalid", "printf ok")
    assert File.read!(trace) == "DATABASE_URL:absent\nCONTROL_ENABLED:false\nORDINARY:ordinary-value\n"
    assert System.get_env(@database_url) == nil
    assert_credential_free_parent()
  end

  test "a real trusted configuration child disables control while parent Repo stays configured" do
    System.put_env(@database_url, @canary)
    assert :ok = RuntimeConfig.configure()

    code = ~S"""
    config = Config.Reader.read!("config/runtime.exs", env: :test)[:symphony_elixir]
    IO.puts("CONTROL_ENABLED:" <> to_string(Keyword.get(config, :control_enabled, false)))
    IO.puts("DATABASE_URL:" <> to_string(System.get_env("SYMPHONY_CONTROL_DATABASE_URL") != nil))
    """

    executable = System.find_executable("elixir") || raise "elixir executable is required"

    assert {"CONTROL_ENABLED:false\nDATABASE_URL:false\n", 0} =
             System.cmd(executable, ["-e", code],
               env: SubprocessEnv.system_cmd_env([{"SYMPHONY_CONTROL_ENABLED", "true"}, {@database_url, @canary}]),
               stderr_to_stdout: true
             )

    assert Application.fetch_env!(:symphony_elixir, Repo)[:url] == @canary
    assert Application.fetch_env!(:symphony_elixir, :control_enabled)
    assert System.get_env(@database_url) == @canary
  end

  test "child policies retain tracker filtering and forbid enabling overrides" do
    env = SubprocessEnv.port_env(["TRACKER_SECRET", "SYMPHONY_CONTROL_ENABLED"])
    assert {~c"TRACKER_SECRET", false} in env
    assert {~c"SYMPHONY_CONTROL_DATABASE_URL", false} in env
    assert {~c"SYMPHONY_CONTROL_ENABLED", ~c"false"} in env
    assert Enum.count(env, &(elem(&1, 0) == ~c"SYMPHONY_CONTROL_ENABLED")) == 1

    assert SubprocessEnv.unset_command(["TRACKER_SECRET"]) ==
             "unset TRACKER_SECRET SYMPHONY_CONTROL_DATABASE_URL && export SYMPHONY_CONTROL_ENABLED=false"
  end

  defp assert_credential_free_parent do
    assert System.get_env(@database_url) == nil
    assert System.get_env("SYMPHONY_CONTROL_ENABLED") == "true"
    refute Application.get_env(:symphony_elixir, :control_enabled, false)
    refute Application.get_env(:symphony_elixir, Repo, [])[:url]
  end

  defp environment_report(trace) do
    """
    if [ "\${#{@database_url}+present}" = present ]; then state=present; else state=absent; fi
    printf 'DATABASE_URL:%s\\nCONTROL_ENABLED:%s\\nORDINARY:%s\\n' "$state" "$SYMPHONY_CONTROL_ENABLED" "$#{@ordinary}" >> '#{trace}'
    """
  end

  defp install_ssh!(root, script) do
    binary = Path.join(root, "ssh")
    File.write!(binary, "#!/bin/sh\n" <> script)
    File.chmod!(binary, 0o755)
    System.put_env("PATH", root <> ":" <> System.fetch_env!("PATH"))
  end

  defp install_codex!(binary, trace) do
    File.write!(binary, """
    #!/bin/sh
    #{environment_report(trace)}
    count=0
    while IFS= read -r line; do
      count=$((count + 1))
      case "$count" in
        1) printf '%s\\n' '{"id":1,"result":{}}' ;;
        2) printf '%s\\n' '{"id":2,"result":{"thread":{"id":"thread-control"}}}' ;;
        3) printf '%s\\n' '{"id":3,"result":{"turn":{"id":"turn-control"}}}' ;;
        4) printf '%s\\n' '{"method":"turn/completed"}'; exit 0 ;;
      esac
    done
    """)

    File.chmod!(binary, 0o755)
  end

  defp issue do
    %Issue{id: "control-env", identifier: "CONTROL-ENV", title: "Keep control credential in Symphony", state: "In Progress"}
  end
end
