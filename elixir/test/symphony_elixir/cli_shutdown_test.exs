defmodule SymphonyElixir.CLIShutdownTest do
  use ExUnit.Case, async: true

  @fixture Path.expand("../support/cli_shutdown_fixture.exs", __DIR__)

  test "SIGTERM preserves zero exit and completes the application stop callback" do
    {output, status, marker} = run_child("sigterm")
    assert status == 0, output
    assert marker == "application_stop_completed\n"
  end

  test "VM shutdown preserves its nonzero exit code and completes callbacks" do
    {output, status, marker} = run_child("vm42")
    assert status == 42, output
    assert marker == "application_stop_completed\n"
  end

  test "unexpected supervisor crash remains a failure" do
    {output, status, _marker} = run_child("crash")
    assert status == 1, output
  end

  test "supervisor shutdown without VM shutdown remains a failure" do
    {output, status, _marker} = run_child("shutdown")
    assert status == 1, output
  end

  test "normal supervisor exit preserves the existing successful exit" do
    {output, status, _marker} = run_child("normal")
    assert status == 0, output
  end

  test "missing supervisor remains a failure" do
    {output, status, _marker} = run_child("missing")
    assert status == 1, output
    assert output =~ "Symphony supervisor is not running"
  end

  defp run_child(mode) do
    root = Path.join(System.tmp_dir!(), "snv-cli-#{System.unique_integer([:positive, :monotonic])}")
    File.mkdir!(root)
    marker = Path.join(root, "stopped")
    on_exit(fn -> File.rm_rf!(root) end)
    elixir = System.find_executable("elixir") || raise "elixir executable is required"
    code_paths = Enum.flat_map(:code.get_path(), fn path -> ["-pz", List.to_string(path)] end)

    args = [
      "--erl", "+S 2:2 +SDcpu 1 +SDio 1",
      "-r", @fixture,
      "-e", "SymphonyElixir.CLIShutdownFixture.run(System.argv())",
      "--", mode, marker
    ]

    port = Port.open({:spawn_executable, elixir}, [:binary, :exit_status, :stderr_to_stdout, args: code_paths ++ args])
    {:os_pid, pid} = Port.info(port, :os_pid)
    deadline = System.monotonic_time(:millisecond) + 15_000

    try do
      {output, status} = collect(port, pid, mode, deadline, "", false)
      witness = if File.regular?(marker), do: File.read!(marker), else: nil
      {output, status, witness}
    after
      if Port.info(port) do
        signal(pid, "KILL")

        try do
          Port.close(port)
        rescue
          ArgumentError -> :ok
        end
      end
    end
  end

  defp collect(port, pid, mode, deadline, output, triggered) do
    remaining = max(0, deadline - System.monotonic_time(:millisecond))

    receive do
      {^port, {:data, data}} ->
        output = output <> data

        triggered =
          if not triggered and String.contains?(output, "SNV_CLI_MONITOR_READY\n") do
            true = Port.command(port, "go\n")
            if mode == "sigterm" do
              assert {_, 0} = signal(pid, "TERM")
            end
            true
          else
            triggered
          end

        collect(port, pid, mode, deadline, output, triggered)

      {^port, {:exit_status, status}} ->
        if mode != "missing", do: assert(triggered, output)
        {output, status}
    after
      remaining -> flunk("CLI child timed out: #{output}")
    end
  end

  defp signal(pid, name) when name in ["TERM", "KILL"] do
    System.cmd("/bin/sh", ["-c", "kill -#{name} \"$1\"", "snv-cli-signal", Integer.to_string(pid)],
      stderr_to_stdout: true
    )
  end
end
