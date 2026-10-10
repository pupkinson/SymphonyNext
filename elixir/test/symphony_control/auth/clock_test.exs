defmodule SymphonyControl.Auth.ClockTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.Clock

  setup do
    start_supervised!({Clock, []})
    :ok
  end

  test "real bracketed samples keep compatible fields and one continuity epoch" do
    first = Clock.now()
    Process.sleep(2)
    second = Clock.now(100)
    assert first.sample_valid and second.sample_valid
    assert is_integer(first.utc_ms) and is_integer(first.monotonic_ms)
    assert byte_size(first.epoch) == 32
    assert second.epoch == first.epoch
    assert second.utc_ms >= first.utc_ms
    assert second.monotonic_ms >= first.monotonic_ms
  end

  for discontinuity <- [:offset, :utc, :monotonic] do
    @discontinuity discontinuity
    test "#{discontinuity} discontinuity invalidates the sample and rotates epoch" do
      first = Clock.now()
      :sys.replace_state(Clock, &discontinue(&1, @discontinuity))
      uncertain = Clock.now()
      refute uncertain.sample_valid
      refute uncertain.epoch == first.epoch
      recovered = Clock.now()
      assert recovered.sample_valid
      assert recovered.epoch == uncertain.epoch
    end
  end

  test "restart changes epoch and a suspended clock respects the supplied timeout" do
    first = Clock.now()
    stop_supervised!(Clock)
    start_supervised!({Clock, []})
    refute Clock.now().epoch == first.epoch
    :ok = :sys.suspend(Clock)

    try do
      assert catch_exit(Clock.now(20)) |> elem(0) == :timeout
    after
      :sys.resume(Clock)
    end

    assert Clock.now().sample_valid
  end

  @tag :f2_native_anchor
  test "native lifetime anchor floors both sampled ms buckets in this VM domain" do
    before = System.monotonic_time()
    sample = Clock.now()
    after_sample = System.monotonic_time()
    unit = System.convert_time_unit(1, :second, :native)
    quantum = System.convert_time_unit(1, :millisecond, :native)
    assert sample.native_unit == unit
    assert sample.native_clock == Process.whereis(Clock)
    assert is_integer(sample.native_anchor)
    assert sample.native_anchor <= after_sample
    assert sample.native_anchor > before - quantum
    assert sample.native_anchor <= System.convert_time_unit(sample.monotonic_ms, :millisecond, :native)
    utc_bucket = System.convert_time_unit(sample.utc_ms, :millisecond, :native) - :erlang.time_offset(:native)
    assert sample.native_anchor <= utc_bucket
    # OTP conversion floors below zero as well; truncation toward zero would
    # put a negative native anchor after the start of its ms bucket.
    assert System.convert_time_unit(-1, :native, :millisecond) == -1
    if after_sample < 0, do: assert(sample.native_anchor < 0)
  end

  defp discontinue(state, :offset), do: %{state | offset: state.offset + 1}
  defp discontinue(state, :utc), do: %{state | last_utc: System.system_time() + System.convert_time_unit(60, :second, :native)}
  defp discontinue(state, :monotonic), do: %{state | last_mono: System.monotonic_time() + System.convert_time_unit(60, :second, :native)}
end
