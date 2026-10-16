defmodule SymphonyControl.Auth.Eligibility do
  @moduledoc "Bounded current observation lifecycle. Unproved production observation stays closed."
  use GenServer
  alias SymphonyControl.Auth.{Actor, Clock, Config, Store, Validity}
  @age 50_000
  @max_cache 1000
  @max_inflight 32
  @max_waiters 32

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, opts, name: __MODULE__)

  @impl true
  def init(opts) do
    Process.flag(:trap_exit, true)
    observer = Keyword.get(opts, :observer)
    binding = Keyword.get(opts, :observation_binding)

    if is_nil(observer) or (is_function(observer, 3) and observation_binding?(binding)),
      do: {:ok, %{config: Keyword.get(opts, :config), observer: observer, observation_binding: binding, cache: %{}, inflight: %{}}},
      else: {:stop, :invalid_auth_options}
  end

  @spec confirm(Config.t(), Actor.t(), Clock.t(), integer()) :: :ok | {:error, Config.reason()}
  def confirm(cfg, actor, clock, deadline) do
    Process.delete({__MODULE__, :receipt})

    with true <- is_integer(deadline) and remaining(deadline) >= 750,
         {:ok, material} <- Store.session_material(cfg, actor, clock),
         true <- remaining(deadline) > 0,
         {:ok, receipt} <- GenServer.call(__MODULE__, {:confirm, cfg, material, clock, deadline}, remaining(deadline)),
         true <- current?(receipt, cfg, actor, deadline) do
      Process.put({__MODULE__, :receipt}, receipt)
      :ok
    else
      {:error, :dependency_unavailable} = error -> error
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  @doc "Internal non-token receipt for a later caller decision; never authorization by itself."
  @spec receipt() :: map() | nil
  def receipt, do: Process.get({__MODULE__, :receipt})

  @spec current?(term(), Config.t(), term(), integer()) :: boolean()
  def current?(receipt, cfg, actor, deadline), do: current?(receipt, cfg, actor, deadline, nil)

  @spec current?(term(), Config.t(), term(), integer(), Validity.t() | nil) :: boolean()
  def current?(%{key: key, ref: ref, actor: actor} = receipt, cfg, actor, deadline, witness) do
    with true <- remaining(deadline) > 0,
         clock = Clock.now(min(remaining(deadline), 250)),
         true <- fresh?(receipt, clock),
         :ok <- GenServer.call(__MODULE__, {:accept, cfg, key, ref}, remaining(deadline)) do
      local_valid = local_current?(witness, cfg, actor, clock)
      now = System.monotonic_time()

      now < System.convert_time_unit(deadline, :millisecond, :native) and
        observation_current?(receipt, clock, now, Process.whereis(Clock)) and local_valid
    else
      _ -> false
    end
  rescue
    _ -> false
  catch
    _, _ -> false
  end

  def current?(_, _, _, _, _), do: false

  defp local_current?(nil, _, _, _), do: true
  defp local_current?(%Validity{deadline: request} = witness, cfg, actor, clock), do: Validity.current?(witness, cfg, actor, request, clock)
  defp local_current?(_, _, _, _), do: false

  @spec invalidate(Config.t(), Store.selector(), integer()) :: :ok | {:error, Config.reason()}
  def invalidate(cfg, selector, deadline) do
    GenServer.call(__MODULE__, {:invalidate, cfg, selector}, remaining(deadline))
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @impl true
  def handle_call({:confirm, cfg, material, clock, deadline}, from, %{config: cfg, observer: observer} = state)
      when is_function(observer, 3) do
    key = key(material)
    cache = Map.reject(state.cache, fn {_key, entry} -> not fresh?(entry, clock) end)
    state = %{state | cache: cache}

    case Map.get(cache, key) do
      nil -> refresh(state, key, material, deadline, from)
      receipt -> {:reply, {:ok, receipt}, state}
    end
  end

  def handle_call({:confirm, _, _, _, _}, _from, state), do: {:reply, {:error, :forbidden}, state}

  def handle_call({:accept, cfg, key, ref}, _from, %{config: cfg} = state) do
    result = if match?(%{ref: ^ref}, Map.get(state.cache, key)), do: :ok, else: {:error, :forbidden}
    {:reply, result, state}
  end

  def handle_call({:accept, _, _, _}, _from, state), do: {:reply, {:error, :forbidden}, state}

  def handle_call({:invalidate, cfg, selector}, _from, %{config: cfg} = state) do
    if valid_selector?(cfg, selector) do
      cache = Map.reject(state.cache, fn {key, _} -> selected?(key, selector) end)
      state = %{state | cache: cache}
      keys = for {key, _} <- state.inflight, selected?(key, selector), do: key
      state = Enum.reduce(keys, state, &finish(&2, &1, {:error, :forbidden}, true))
      {:reply, :ok, state}
    else
      {:reply, {:error, :forbidden}, state}
    end
  end

  def handle_call({:invalidate, _, _}, _from, state), do: {:reply, {:error, :forbidden}, state}

  @impl true
  def handle_info({:observed, key, ref, result}, state) do
    case Map.get(state.inflight, key) do
      %{ref: ^ref, deadline: deadline} ->
        result = if remaining(deadline) > 0, do: result, else: {:error, :dependency_unavailable}
        {state, result} = publish(state, key, result)
        {:noreply, finish(state, key, result, false)}

      _ ->
        {:noreply, state}
    end
  end

  def handle_info({:timeout, key, ref}, state) do
    if match?(%{ref: ^ref}, Map.get(state.inflight, key)),
      do: {:noreply, finish(state, key, {:error, :dependency_unavailable}, true)},
      else: {:noreply, state}
  end

  def handle_info({:DOWN, monitor, :process, _pid, _reason}, state) do
    case Enum.find(state.inflight, fn {_key, job} -> job.monitor == monitor end) do
      {key, _job} -> {:noreply, finish(state, key, {:error, :dependency_unavailable}, false)}
      nil -> {:noreply, state}
    end
  end

  def handle_info({:EXIT, _pid, _reason}, state), do: {:noreply, state}

  @impl true
  def terminate(_reason, state) do
    Enum.each(state.inflight, fn {_key, job} -> Process.exit(job.pid, :kill) end)
    :ok
  end

  defp refresh(state, key, material, deadline, from) do
    case Map.get(state.inflight, key) do
      %{waiters: waiters} = job when length(waiters) < @max_waiters ->
        {:noreply, put_in(state.inflight[key], %{job | waiters: [from | waiters]})}

      nil when map_size(state.inflight) < @max_inflight and map_size(state.cache) + map_size(state.inflight) < @max_cache ->
        start_refresh(state, key, material, deadline, from)

      _ ->
        {:reply, {:error, :dependency_unavailable}, state}
    end
  end

  defp start_refresh(state, key, material, deadline, from) do
    owner = self()
    ref = make_ref()
    {pid, monitor} = :erlang.spawn_opt(fn -> send(owner, {:observed, key, ref, observe(state.config, state.observer, state.observation_binding, material, deadline, ref)}) end, [:link, :monitor])
    timer = Process.send_after(self(), {:timeout, key, ref}, remaining(deadline))
    job = %{pid: pid, monitor: monitor, timer: timer, ref: ref, deadline: deadline, waiters: [from]}
    {:noreply, put_in(state.inflight[key], job)}
  end

  defp observe(cfg, observer, binding, material, deadline, ref) do
    with true <- remaining(deadline) > 0,
         measured = Clock.now(min(remaining(deadline), 250)),
         true <- valid_clock?(measured) and measured.epoch == material.actor.boot_epoch,
         {:ok, observation} <- observer.(cfg, material, deadline),
         true <- observation?(cfg, material, binding, observation),
         true <- remaining(deadline) > 0 do
      {:ok, %{key: key(material), ref: ref, actor: material.actor, clock: measured, until_native: measured.native_anchor + System.convert_time_unit(@age, :millisecond, :native)}}
    else
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  defp observation?(cfg, material, binding, observation) when is_map(observation) do
    bindings = %{
      "issuer" => cfg.issuer,
      "subject" => material.actor.subject,
      "sid" => material.sid,
      "client_id" => cfg.client_id,
      "application_id" => cfg.application_id,
      "provider_id" => cfg.provider_id,
      "resource_id" => cfg.resource_id,
      "generation" => cfg.generation,
      "app_group" => true,
      "user_active" => true,
      "idp_session" => true,
      "version" => binding.version,
      "evidence" => binding.evidence
    }

    observation_binding?(binding) and map_size(observation) == map_size(bindings) and
      Enum.all?(bindings, fn {key, value} -> Map.fetch(observation, key) == {:ok, value} end)
  end

  defp observation?(_, _, _, _), do: false

  defp observation_binding?(%{version: version, evidence: evidence} = binding) do
    map_size(binding) == 2 and Enum.all?([version, evidence], &(is_binary(&1) and byte_size(&1) in 1..256))
  end

  defp observation_binding?(_), do: false

  defp publish(state, key, {:ok, receipt}) do
    if System.monotonic_time() < receipt.until_native and (Map.has_key?(state.cache, key) or map_size(state.cache) < @max_cache),
      do: {put_in(state.cache[key], receipt), {:ok, receipt}},
      else: {state, {:error, :dependency_unavailable}}
  end

  defp publish(state, _key, failure), do: {state, failure}

  defp finish(state, key, result, kill?) do
    {job, inflight} = Map.pop(state.inflight, key)
    Process.cancel_timer(job.timer)
    Process.demonitor(job.monitor, [:flush])
    if kill?, do: Process.exit(job.pid, :kill)
    Enum.each(job.waiters, &GenServer.reply(&1, result))
    %{state | inflight: inflight}
  end

  defp key(%{actor: actor, sid: sid}),
    do: {actor.issuer, actor.subject, sid, actor.config_generation, actor.boot_epoch, actor.session_id}

  @doc "Internal age predicate at an explicit native decision; config, actor and cache-ref acceptance remain separate."
  @spec observation_current?(term(), term(), integer(), pid() | nil) :: boolean()
  def observation_current?(%{clock: observed, until_native: until}, measured, now, producer)
      when is_integer(now) and is_integer(until) do
    with true <- valid_clock?(observed, now, producer),
         true <- valid_clock?(measured, now, producer),
         true <- measured.epoch == observed.epoch,
         ages = [measured.utc_ms - observed.utc_ms, measured.monotonic_ms - observed.monotonic_ms],
         true <- Enum.all?(ages, &(&1 >= 0 and &1 < @age)) do
      remaining = @age - Enum.max(ages)
      now < until and now < measured.native_anchor + System.convert_time_unit(remaining, :millisecond, :native)
    else
      _ -> false
    end
  end

  def observation_current?(_, _, _, _), do: false

  defp fresh?(entry, clock), do: observation_current?(entry, clock, System.monotonic_time(), Process.whereis(Clock))
  defp valid_clock?(clock), do: valid_clock?(clock, System.monotonic_time(), Process.whereis(Clock))

  defp valid_clock?(%{sample_valid: true} = clock, now, current_producer) do
    numbers = Enum.map([:utc_ms, :monotonic_ms, :native_anchor, :native_unit], &Map.get(clock, &1))
    producer = Map.get(clock, :native_clock)

    Enum.all?(numbers, &is_integer/1) and is_binary(Map.get(clock, :epoch)) and is_pid(producer) and
      producer == current_producer and clock.native_unit == System.convert_time_unit(1, :second, :native) and
      clock.native_anchor <= now
  end

  defp valid_clock?(_, _, _), do: false

  defp valid_selector?(%Config{issuer: issuer}, {:subject, issuer, sub}), do: is_binary(sub) and byte_size(sub) > 0
  defp valid_selector?(%Config{issuer: issuer}, {:sid, issuer, sid, sub}), do: is_binary(sid) and byte_size(sid) > 0 and (is_nil(sub) or (is_binary(sub) and byte_size(sub) > 0))
  defp valid_selector?(_cfg, {:session, id}), do: match?({:ok, _}, Ecto.UUID.cast(id))
  defp valid_selector?(_, _), do: false
  defp selected?({_issuer, _sub, _sid, _generation, _epoch, id}, {:session, id}), do: true
  defp selected?({issuer, sub, _sid, _generation, _epoch, _id}, {:subject, issuer, sub}), do: true
  defp selected?({issuer, _sub, sid, _generation, _epoch, _id}, {:sid, issuer, sid, nil}), do: true
  defp selected?({issuer, sub, sid, _generation, _epoch, _id}, {:sid, issuer, sid, sub}), do: true
  defp selected?(_, _), do: false
  defp remaining(deadline), do: max(deadline - System.monotonic_time(:millisecond), 0)
end
