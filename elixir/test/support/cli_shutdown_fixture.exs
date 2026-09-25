defmodule SymphonyElixir.CLIShutdownFixture.Application do
  use Application

  @impl true
  def start(_type, marker) do
    {:ok, pid} = Supervisor.start_link([], strategy: :one_for_one, name: SymphonyElixir.Supervisor)
    {:ok, pid, marker}
  end

  @impl true
  def stop(marker) do
    # A premature halt after supervisor DOWN must not pass the shutdown test.
    Process.sleep(100)
    File.write!(marker, "application_stop_completed\n")
  end
end

defmodule SymphonyElixir.CLIShutdownFixture do
  @ack "--i-understand-that-this-will-be-running-without-the-usual-guardrails"

  def run([mode, marker]) do
    :ok =
      :application.load(
        {:application, :snv_cli_shutdown_fixture,
         [
           description: ~c"CLI shutdown regression fixture",
           vsn: ~c"1",
           modules: [SymphonyElixir.CLIShutdownFixture.Application],
           registered: [],
           applications: [:kernel, :stdlib, :elixir],
           mod: {SymphonyElixir.CLIShutdownFixture.Application, marker}
         ]}
      )

    start = fn ->
      if mode == "missing" do
        {:ok, []}
      else
        Application.ensure_all_started(:snv_cli_shutdown_fixture, :temporary)
      end
    end

    cli = spawn(fn -> SymphonyElixir.CLI.main([@ack, __ENV__.file], start) end)

    if mode == "missing" do
      Process.sleep(:infinity)
    end

    supervisor = await_monitor(cli, System.monotonic_time(:millisecond) + 10_000)
    IO.puts("SNV_CLI_MONITOR_READY")

    case IO.gets("") do
      "go\n" -> :ok
      _ -> System.halt(90)
    end

    trigger_shutdown(mode, supervisor)
    Process.sleep(:infinity)
  end

  defp trigger_shutdown(mode, supervisor) do
    case mode do
      "vm42" -> System.stop(42)
      "crash" -> Process.exit(supervisor, :kill)
      "shutdown" -> Supervisor.stop(supervisor, :shutdown)
      "normal" -> Supervisor.stop(supervisor, :normal)
      "sigterm" -> :ok
    end
  end

  defp await_monitor(cli, deadline) do
    supervisor = Process.whereis(SymphonyElixir.Supervisor)

    if is_pid(supervisor) and cli in elem(Process.info(supervisor, :monitored_by), 1) do
      supervisor
    else
      if System.monotonic_time(:millisecond) >= deadline, do: System.halt(91)
      Process.sleep(10)
      await_monitor(cli, deadline)
    end
  end
end
