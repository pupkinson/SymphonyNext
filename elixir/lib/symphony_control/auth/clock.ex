defmodule SymphonyControl.Auth.Clock do
  @moduledoc "Control boot epoch with independent UTC and monotonic clocks."
  use GenServer
  @type t :: %{utc_ms: integer(), monotonic_ms: integer(), epoch: binary()}

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, :ok, Keyword.put(opts, :name, __MODULE__))

  @spec now() :: t()
  def now, do: GenServer.call(__MODULE__, :now)

  @impl true
  def init(:ok), do: {:ok, :crypto.strong_rand_bytes(32)}

  @impl true
  def handle_call(:now, _from, epoch) do
    clock = %{utc_ms: System.system_time(:millisecond), monotonic_ms: System.monotonic_time(:millisecond), epoch: epoch}
    {:reply, clock, epoch}
  end
end
