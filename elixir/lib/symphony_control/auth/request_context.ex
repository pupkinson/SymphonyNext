defmodule SymphonyControl.Auth.RequestContext do
  @moduledoc "One absolute native deadline from auth handler entry, including initial waits."

  @spec deadline() :: integer()
  def deadline, do: System.monotonic_time() + System.convert_time_unit(5_000, :millisecond, :native)

  @spec milliseconds(integer()) :: integer()
  def milliseconds(native), do: System.convert_time_unit(native, :native, :millisecond)

  @spec remaining(integer()) :: non_neg_integer()
  def remaining(deadline), do: max(milliseconds(deadline - System.monotonic_time()), 0)

  @spec timely?(integer()) :: boolean()
  def timely?(deadline), do: System.monotonic_time() < deadline
end
