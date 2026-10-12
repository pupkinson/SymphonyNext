defmodule SymphonyControl.Auth.Login do
  @moduledoc "Browser-bound login composition. One deadline; confirmed consumption is never retried."
  alias SymphonyControl.Auth.{Clock, Config, Oidc, RequestContext, Store}
  @type result(value) :: {:ok, value} | {:error, Config.reason()}

  @spec begin(Config.t(), binary() | nil, Clock.t()) :: result(map())
  def begin(cfg, browser, clock), do: begin(cfg, browser, clock, RequestContext.deadline())

  @spec begin(Config.t(), binary() | nil, Clock.t(), integer()) :: result(map())
  def begin(cfg, browser, clock, deadline) do
    bounded(deadline, fn deadline ->
      with :ok <- configuration(cfg),
           {:ok, browser} <- browser_binding(browser),
           {:ok, fresh} <- sample(clock, deadline),
           flow = %{state: random(), nonce: random(), verifier: random(), issued_ms: fresh.utc_ms},
           :ok <- store_budget(deadline),
           {:ok, _id} <- Store.put_login(cfg, browser, flow, fresh),
           {:ok, _} <- sample(fresh, deadline, fresh.utc_ms + 300_000),
           {:ok, location} <- Oidc.authorization_url(cfg, flow, milliseconds(deadline)),
           {:ok, accepted} <- sample(fresh, deadline, fresh.utc_ms + 300_000) do
        {:guarded, %{location: location, browser_handle: browser}, accepted, fresh, fresh.utc_ms + 300_000}
      end
    end)
  end

  @spec finish(Config.t(), binary(), binary(), binary(), binary() | nil, Clock.t()) :: result(binary())
  def finish(cfg, code, state, browser, old_session, clock), do: finish(cfg, code, state, browser, old_session, clock, RequestContext.deadline())

  @spec finish(Config.t(), binary(), binary(), binary(), binary() | nil, Clock.t(), integer()) :: result(binary())
  def finish(cfg, code, state, browser, old_session, clock, deadline) do
    bounded(deadline, fn deadline ->
      with :ok <- configuration(cfg),
           :ok <- inputs(code, state, browser, old_session),
           {:ok, fresh} <- sample(clock, deadline),
           :ok <- store_budget(deadline),
           {:ok, flow} <- Store.consume_login(cfg, state, browser, fresh),
           flow_expiry = flow.issued_ms + 300_000,
           {:ok, _} <- sample(fresh, deadline, flow_expiry),
           {:ok, identity} <- Oidc.exchange(cfg, code, flow, milliseconds(deadline)),
           expiry = min(flow_expiry, identity.credential_expires_at_ms),
           {:ok, issued} <- sample(fresh, deadline, expiry),
           :ok <- store_budget(deadline),
           {:ok, handle} <- Store.open_session(cfg, identity, old_session, issued),
           {:ok, accepted} <- sample(issued, deadline, expiry) do
        {:session, cfg, handle, accepted, issued, expiry}
      end
    end)
  end

  defp bounded(deadline, operation) do
    task = Task.async(fn -> safely(fn -> operation.(deadline) end) end)

    case Task.yield(task, remaining(deadline)) do
      {:ok, {:guarded, value, clock, issued, expiry}} ->
        if timely?(clock, issued, deadline, expiry), do: {:ok, value}, else: {:error, :forbidden}

      {:ok, {:session, cfg, handle, clock, issued, expiry}} ->
        timely = timely?(clock, issued, deadline, expiry)
        if timely, do: accept_session(cfg, handle, clock, deadline), else: {:error, :forbidden}

      {:ok, {:error, _} = error} ->
        error

      _ ->
        Task.shutdown(task, :brutal_kill)
        {:error, :unknown_outcome}
    end
  end

  defp store_budget(deadline), do: if(remaining(deadline) >= 750, do: :ok, else: {:error, :dependency_unavailable})

  defp accept_session(cfg, handle, clock, deadline) do
    # Store rereads the committed row, key, expiry axes and revocation in the
    # actual Login caller. No further Clock/DB/provider wait follows acceptance.
    with :ok <- store_budget(deadline),
         {:ok, _actor} <- Store.local_actor(cfg, handle, clock),
         true <- RequestContext.timely?(deadline) do
      {:ok, handle}
    else
      {:error, reason} when reason in [:dependency_unavailable, :unknown_outcome] -> {:error, :dependency_unavailable}
      _ -> {:error, :forbidden}
    end
  end

  defp sample(previous, deadline, expiry \\ nil) do
    if remaining(deadline) > 0 do
      fresh = Clock.now(remaining(deadline))
      valid = native_sample?(previous) and native_sample?(fresh) and fresh.epoch == previous.epoch and fresh.utc_ms >= previous.utc_ms and fresh.monotonic_ms >= previous.monotonic_ms
      if valid and timely?(fresh, previous, deadline, expiry), do: {:ok, fresh}, else: {:error, :forbidden}
    else
      {:error, :dependency_unavailable}
    end
  end

  defp timely?(clock, issued, deadline, expiry) do
    now = System.monotonic_time()
    lifetime = is_nil(expiry) or now < native_expiry(clock, issued, expiry)
    native_sample?(clock) and now < deadline and lifetime
  end

  defp native_expiry(clock, issued, expiry) do
    remaining_ms = min(expiry - clock.utc_ms, expiry - issued.utc_ms - (clock.monotonic_ms - issued.monotonic_ms))
    clock.native_anchor + System.convert_time_unit(remaining_ms, :millisecond, :native)
  end

  defp native_sample?(%{
         sample_valid: true,
         utc_ms: utc,
         monotonic_ms: mono,
         native_anchor: anchor,
         native_unit: unit,
         native_clock: producer,
         epoch: epoch
       }) do
    valid = is_integer(utc) and is_integer(mono) and is_integer(anchor) and is_pid(producer) and is_binary(epoch)
    native = producer == Process.whereis(Clock) and unit == System.convert_time_unit(1, :second, :native)
    valid and native and anchor <= System.monotonic_time()
  end

  defp native_sample?(_), do: false

  defp configuration(%Config{} = cfg) do
    case cfg |> Map.from_struct() |> Map.delete(:tls_cacerts) |> Config.load() do
      {:ok, _} -> :ok
      _ -> {:error, :forbidden}
    end
  end

  defp configuration(_), do: {:error, :forbidden}
  @spec browser_binding(binary() | nil) :: result(binary())
  def browser_binding(nil), do: {:ok, random()}
  def browser_binding(value), do: if(opaque?(value), do: {:ok, value}, else: {:error, :invalid_request})
  defp opaque?(value) when is_binary(value) and byte_size(value) == 43, do: match?({:ok, <<_::256>>}, Base.url_decode64(value, padding: false))
  defp opaque?(_), do: false

  defp inputs(code, state, browser, old) do
    if sized?(code, 4096) and sized?(state, 256) and opaque?(browser) and (is_nil(old) or opaque?(old)),
      do: :ok,
      else: {:error, :invalid_request}
  end

  defp sized?(value, max), do: is_binary(value) and byte_size(value) in 1..max

  defp safely(operation) do
    operation.()
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  defp random, do: Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
  defp milliseconds(deadline), do: System.convert_time_unit(deadline, :native, :millisecond)
  defp remaining(deadline), do: max(milliseconds(deadline - System.monotonic_time()), 0)
end
