defmodule SymphonyControl.Auth.Clock do
  @moduledoc "Control clock snapshots with bracketed native sampling and a continuity epoch."
  use GenServer
  @type t :: %{utc_ms: integer(), monotonic_ms: integer(), epoch: binary(), sample_valid: boolean()}

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, :ok, Keyword.put(opts, :name, __MODULE__))

  @spec now() :: t()
  @spec now(timeout()) :: t()
  def now(timeout \\ 5000), do: GenServer.call(__MODULE__, :now, timeout)

  @impl true
  def init(:ok), do: {:ok, %{epoch: :crypto.strong_rand_bytes(32), offset: :erlang.time_offset(:native), last_utc: nil, last_mono: nil}}

  @impl true
  def handle_call(:now, _from, state) do
    offset_before = :erlang.time_offset(:native)
    before = System.monotonic_time()
    utc = System.system_time()
    after_sample = System.monotonic_time()
    offset = :erlang.time_offset(:native)
    mono = utc - offset

    # These are separate BIFs. A stable offset and the measured bracket locate
    # the UTC read on the monotonic axis without assuming atomic sampling.
    valid =
      offset_before == offset and offset == state.offset and before <= mono and mono <= after_sample and
        (is_nil(state.last_utc) or utc >= state.last_utc) and (is_nil(state.last_mono) or mono >= state.last_mono)

    epoch = if valid, do: state.epoch, else: :crypto.strong_rand_bytes(32)
    utc_ms = System.convert_time_unit(utc, :native, :millisecond)
    mono_ms = System.convert_time_unit(mono, :native, :millisecond)
    clock = %{utc_ms: utc_ms, monotonic_ms: mono_ms, epoch: epoch, sample_valid: valid}
    next = %{epoch: epoch, offset: offset, last_utc: utc, last_mono: mono}
    {:reply, clock, next}
  end
end
