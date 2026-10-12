defmodule SymphonyControl.Auth.RateLimiter do
  @moduledoc "Bounded local auth counters. Missing limiter fails closed."
  use GenServer
  alias SymphonyControl.Auth.RequestContext
  @type reason :: :rate_limited | :dependency_unavailable

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, :ok, Keyword.put(opts, :name, __MODULE__))

  @impl true
  def init(:ok), do: {:ok, %{}}

  @spec check(:login | :callback | :backchannel, binary() | nil) :: :ok | {:error, reason()}
  def check(kind, browser) do
    check(kind, browser, RequestContext.deadline())
  end

  @spec check(:login | :callback | :backchannel, binary() | nil, integer()) :: :ok | {:error, reason()}
  def check(kind, browser, deadline) do
    GenServer.call(__MODULE__, {kind, browser, deadline}, min(500, RequestContext.remaining(deadline)))
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @impl true
  def handle_call({kind, browser, deadline}, _from, counters) do
    if RequestContext.timely?(deadline), do: charge(kind, browser, counters), else: {:reply, {:error, :dependency_unavailable}, counters}
  end

  defp charge(kind, browser, counters) do
    now = System.monotonic_time(:millisecond)
    counters = Map.reject(counters, fn {_, {until, _}} -> until <= now end)
    limits = limits(kind, browser)

    if Enum.all?(limits, fn {key, limit} -> below?(counters, key, limit) end) and map_size(counters) + Enum.count(limits, fn {key, _} -> not Map.has_key?(counters, key) end) <= 1000 do
      next = Enum.reduce(limits, counters, &increment(&1, &2, now))
      {:reply, :ok, next}
    else
      {:reply, {:error, :rate_limited}, counters}
    end
  end

  defp increment({key, _}, counters, now) do
    Map.update(counters, key, {now + 60_000, 1}, fn {until, count} -> {until, count + 1} end)
  end

  defp limits(:login, browser), do: [{:login, 60}, {{:browser, browser_key(browser)}, 5}]
  defp limits(_kind, _browser), do: [{:callback, 120}]
  defp browser_key(browser) when is_binary(browser) and byte_size(browser) == 43, do: :crypto.hash(:sha256, browser)
  defp browser_key(_browser), do: :unknown

  defp below?(counters, key, limit) do
    case Map.get(counters, key) do
      nil -> true
      {_, count} -> count < limit
    end
  end
end
