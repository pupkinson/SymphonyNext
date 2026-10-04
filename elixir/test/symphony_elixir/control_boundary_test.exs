defmodule SymphonyElixir.ControlBoundaryTest do
  use SymphonyElixir.TestSupport

  alias SymphonyControl.Repo
  alias SymphonyElixir.{AgentRuntimeSupervisor, ControlBoundary, SSH}

  @database_url "SYMPHONY_CONTROL_DATABASE_URL"
  @canary "postgres://synthetic:synthetic-secret@example.invalid/control_fixture"
  @blocked {:error, :control_agent_runtime_unsupported}

  setup do
    env = System.get_env(@database_url)
    config = Map.new([Repo, :control_enabled], &{&1, Application.fetch_env(:symphony_elixir, &1)})
    System.delete_env(@database_url)
    Application.delete_env(:symphony_elixir, Repo)
    Application.put_env(:symphony_elixir, :control_enabled, false)

    on_exit(fn ->
      restore_env(@database_url, env)

      Enum.each(config, fn
        {key, {:ok, value}} -> Application.put_env(:symphony_elixir, key, value)
        {key, :error} -> Application.delete_env(:symphony_elixir, key)
      end)
    end)

    :ok
  end

  test "credential-free legacy runtime remains admissible" do
    assert :ok = ControlBoundary.check()
  end

  test "configured control, retained Repo URL and current environment each block runtime startup" do
    Application.put_env(:symphony_elixir, :control_enabled, true)
    assert @blocked == SymphonyElixir.Application.start_runtime()
    assert @blocked == SymphonyElixir.start_link()
    assert @blocked == AgentRuntimeSupervisor.start_link(name: :blocked_agent_runtime)
    assert {:stop, :control_agent_runtime_unsupported} = AgentRuntimeSupervisor.init([])
    refute Process.whereis(:blocked_agent_runtime)

    Application.put_env(:symphony_elixir, :control_enabled, false)
    Application.put_env(:symphony_elixir, Repo, url: @canary)
    assert @blocked == ControlBoundary.check()
    assert Application.fetch_env!(:symphony_elixir, Repo)[:url] == @canary

    Application.delete_env(:symphony_elixir, Repo)
    System.put_env(@database_url, @canary)
    assert @blocked == ControlBoundary.check()
    assert System.get_env(@database_url) == @canary
  end

  test "a live control supervisor also prevents new agents" do
    spec = %{
      id: :control_fixture,
      start: {Supervisor, :start_link, [[], [strategy: :one_for_one, name: SymphonyControl.Application]]}
    }

    pid = start_supervised!(spec)
    assert Process.alive?(pid)
    assert @blocked == AgentRuntimeSupervisor.start_link(name: :blocked_live_control)
    refute Process.whereis(:blocked_live_control)
  end

  test "restart callbacks reject credentials before starting either child" do
    Application.put_env(:symphony_elixir, Repo, url: @canary)

    assert {:stop, :control_agent_runtime_unsupported} =
             AgentRuntimeSupervisor.init(task_supervisor_name: :blocked_tasks, orchestrator_name: :blocked_orchestrator)

    refute Process.whereis(:blocked_tasks)
    refute Process.whereis(:blocked_orchestrator)
  end

  test "agents, SSH and hooks refuse execution while preserving cleanup and Repo configuration" do
    root = Path.dirname(Workflow.workflow_file_path())
    marker = Path.join(root, "child-executed")
    command = "printf executed >> '#{marker}'"
    workspace_root = Path.join(root, "workspaces")
    workspace = Path.join(workspace_root, "CONTROL-BLOCKED")
    File.mkdir_p!(workspace)

    write_workflow_file!(Workflow.workflow_file_path(),
      workspace_root: workspace_root,
      codex_command: command,
      hook_after_create: command,
      hook_before_run: command,
      hook_after_run: command,
      hook_before_remove: command
    )

    Application.put_env(:symphony_elixir, Repo, url: @canary)
    issue = %Issue{id: "blocked", identifier: "CONTROL-BLOCKED", title: "Block unsafe child", state: "In Progress"}
    assert @blocked == AppServer.start_session(workspace)
    assert @blocked == AppServer.start_session(workspace, worker_host: "fixture.invalid")
    assert @blocked == SSH.run("fixture.invalid", command)
    assert @blocked == SSH.start_port("fixture.invalid", command)
    assert @blocked == Workspace.run_before_run_hook(workspace, issue)
    assert :ok = Workspace.run_after_run_hook(workspace, issue)
    assert @blocked == Workspace.run_before_run_hook(workspace, issue, "fixture.invalid")
    assert :ok = Workspace.run_after_run_hook(workspace, issue, "fixture.invalid")
    assert {:ok, _} = Workspace.remove(workspace)
    refute File.exists?(workspace)
    assert @blocked == Workspace.create_for_issue(issue)
    refute File.exists?(workspace)
    refute File.exists?(marker)
    assert Application.fetch_env!(:symphony_elixir, Repo)[:url] == @canary
  end

  test "startup evidence matches an assignment and fails closed when unreadable" do
    assert @blocked == ControlBoundary.validate_startup_environment({:ok, "PATH=/bin\0#{@database_url}=#{@canary}\0"})
    assert @blocked == ControlBoundary.validate_startup_environment({:ok, "#{@database_url}=\0"})
    assert :ok = ControlBoundary.validate_startup_environment({:ok, "OTHER=#{@database_url}=text\0PATH=/bin\0"})
    assert :ok = ControlBoundary.validate_startup_environment({:ok, ""})

    for reason <- [:enoent, :eacces] do
      expected = {:error, :credential_environment_unverifiable}
      assert expected == ControlBoundary.validate_startup_environment({:error, reason})
    end
  end

  test "clearing a startup URL cannot admit a same-UID child that can read the parent's proc environment" do
    root = Path.dirname(Workflow.workflow_file_path())
    probe = Path.join(root, "owned-proc-probe.exs")
    marker = Path.join(root, "proc-child")
    executable = System.find_executable("elixir") || raise "elixir executable is required"

    File.write!(probe, ~S"""
    parent = System.fetch_env!("OWN_SNCI_PARENT_PID")
    initial = File.read!("/proc/" <> parent <> "/environ")
    readable = String.contains?(initial, "synthetic-secret")
    File.write!(System.fetch_env!("OWN_SNCI_MARKER"), to_string(readable))
    """)

    ssh = Path.join(root, "ssh")
    File.write!(ssh, "#!/bin/sh\nexec \"$OWN_SNCI_ELIXIR\" \"$OWN_SNCI_PROBE\"\n")
    File.chmod!(ssh, 0o755)

    code = ~S"""
    [root, probe, marker, executable] = System.argv()
    System.delete_env("SYMPHONY_CONTROL_DATABASE_URL")
    Application.put_env(:symphony_elixir, :control_enabled, false)
    Application.delete_env(:symphony_elixir, SymphonyControl.Repo)
    System.put_env("PATH", root <> ":" <> System.fetch_env!("PATH"))
    System.put_env("OWN_SNCI_PARENT_PID", System.pid())
    System.put_env("OWN_SNCI_MARKER", marker)
    System.put_env("OWN_SNCI_PROBE", probe)
    System.put_env("OWN_SNCI_ELIXIR", executable)
    {"", 0} = System.cmd(Path.join(root, "ssh"), [])
    readable = File.read!(marker) == "true"
    File.rm!(marker)
    result = SymphonyElixir.SSH.run("fixture.invalid", "ignored")
    callback = SymphonyElixir.AgentRuntimeSupervisor.init([])
    IO.puts("PROC_BOUNDARY=" <> Jason.encode!(%{
      current_url_absent: System.get_env("SYMPHONY_CONTROL_DATABASE_URL") == nil,
      same_uid_canary_readable: readable,
      child_blocked: result == {:error, :control_agent_runtime_unsupported},
      callback_blocked: callback == {:stop, :control_agent_runtime_unsupported},
      child_executed: File.exists?(marker)
    }))
    """

    paths = Enum.flat_map(:code.get_path(), &["-pz", List.to_string(&1)])
    args = paths ++ ["-e", code, "--", root, probe, marker, executable]

    {output, status} = System.cmd(executable, args, env: [{@database_url, @canary}], stderr_to_stdout: true)
    assert status == 0, output
    line = Enum.find(String.split(output, "\n"), &String.starts_with?(&1, "PROC_BOUNDARY="))
    assert is_binary(line), output
    result = line |> String.replace_prefix("PROC_BOUNDARY=", "") |> Jason.decode!()
    assert result["current_url_absent"]
    assert result["same_uid_canary_readable"]
    assert result["child_blocked"]
    assert result["callback_blocked"]
    refute result["child_executed"]
  end
end
