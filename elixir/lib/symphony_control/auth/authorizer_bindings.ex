defmodule SymphonyControl.Auth.AuthorizerBindings do
  @moduledoc """
  Lifecycle-owned effective authorizer without changing operator defaults.

  One published descriptor fences selection and callback acceptance. Its unique
  revision is consistency evidence, never an Actor or an authorization grant.
  Unexpected component loss leaves lookup closed until explicit new startup.
  """
  use GenServer
  alias SymphonyControl.Auth.{Authorizer, RequestContext}
  @keys [:project_authorizer, :runtime_identity_authorizer]
  @context {__MODULE__, :lifecycle}
  @lookup_timeout 250
  @opaque selection :: {term(), term(), integer(), integer() | nil}

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, Keyword.put_new(opts, :owner, self()), name: __MODULE__)

  @spec install(pid()) :: {:ok, reference()} | {:error, term()}
  def install(owner) do
    with :ok <- ensure_owner(owner), do: GenServer.call(__MODULE__, {:install, owner})
  end

  @spec release(reference()) :: :ok
  def release(generation) do
    GenServer.call(__MODULE__, {:release, generation})
  catch
    :exit, _ -> :ok
  end

  @doc "Compatibility lookup. Actual authorization must also guard callback acceptance."
  @spec resolve(atom()) :: {:ok, term()} | {:error, :forbidden}
  def resolve(key) do
    with {:ok, {module, decision, limit, _deadline}} <- prepare(key),
         {:ok, ^module, ^decision} <- accept_selection(module, decision, limit) do
      {:ok, module}
    else
      _ -> {:error, :forbidden}
    end
  end

  @doc false
  @spec authorize(atom(), [term()]) :: :ok | :deny
  def authorize(key, arguments) do
    case prepare(key) do
      {:ok, selection} -> authorize_selected(selection, arguments)
      _ -> :deny
    end
  end

  @doc false
  @spec authorize_selected(selection(), [term()]) :: :ok | :deny
  def authorize_selected({module, decision, limit, deadline}, arguments) do
    with true <- is_atom(module) and not is_nil(module),
         {:ok, ^module, ^decision} <- accept_selection(module, decision, limit),
         :ok <- apply(module, :authorize, arguments),
         true <- accept_authorization(decision, deadline) do
      :ok
    else
      _ -> :deny
    end
  end

  # Internal unaccepted candidate; it carries both the original request deadline
  # and a separate lookup-delivery limit. A module alone is never this proof.
  @doc false
  @spec prepare(atom()) :: {:ok, selection()} | {:error, :forbidden}
  def prepare(key) when key in @keys do
    deadline = Process.get({Authorizer, :deadline})
    limit = lookup_deadline(deadline)

    with true <- RequestContext.timely?(limit),
         {:ok, module, decision} <- candidate(:persistent_term.get(@context, :absent), key, limit) do
      {:ok, {module, decision, limit, deadline}}
    else
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  def prepare(_key), do: {:error, :forbidden}

  defp candidate(:absent, key, _limit), do: {:ok, base(key), :absent}
  defp candidate({:legacy, revision} = decision, key, _limit) when is_reference(revision), do: {:ok, base(key), decision}

  defp candidate({pid, incarnation, _, _, _, _, _}, key, limit) when is_pid(pid) and is_reference(incarnation) do
    with {:ok, mode, decision} <- GenServer.call(pid, {:resolve, incarnation}, RequestContext.remaining(limit)) do
      {:ok, selected(mode, key), decision}
    end
  end

  defp candidate(_decision, _key, _limit), do: {:error, :forbidden}

  defp selected(:managed, _key), do: Authorizer
  defp selected(:base, key), do: base(key)
  defp base(key), do: Application.get_env(:symphony_elixir, key)

  # The closing sample bounds completed state reads; only the local result
  # follows it. All waiting and raw-base reads precede this acceptance guard.
  defp accept_selection(module, decision, limit) do
    if RequestContext.timely?(limit) and current?(decision) and RequestContext.timely?(limit) do
      {:ok, module, decision}
    else
      {:error, :forbidden}
    end
  end

  # The callback runs in the caller, preserving its process-local receipt and
  # Validity. Only the original request deadline applies after lookup completes.
  defp accept_authorization(decision, deadline) do
    request_timely?(deadline) and current?(decision) and request_timely?(deadline)
  end

  defp request_timely?(deadline), do: is_nil(deadline) or RequestContext.timely?(deadline)

  defp current?(decision) do
    live_decision?(decision) and :persistent_term.get(@context, :absent) == decision
  end

  defp live_decision?(:absent), do: is_nil(Process.whereis(__MODULE__))
  defp live_decision?({:legacy, revision}) when is_reference(revision), do: is_nil(Process.whereis(__MODULE__))

  defp live_decision?({pid, incarnation, revision, phase, generation, owner, writer})
       when is_pid(pid) and is_reference(incarnation) and is_reference(revision) and is_pid(owner) do
    Process.whereis(__MODULE__) == pid and Process.alive?(pid) and Process.alive?(owner) and live_phase?(phase, generation, writer)
  end

  defp live_decision?(_decision), do: false
  defp live_phase?(:inactive, nil, nil), do: true
  defp live_phase?(:active, generation, writer) when is_reference(generation) and is_pid(writer), do: Process.alive?(writer)
  defp live_phase?(_phase, _generation, _writer), do: false

  defp lookup_deadline(nil), do: System.monotonic_time() + System.convert_time_unit(@lookup_timeout, :millisecond, :native)

  defp lookup_deadline(deadline) when is_integer(deadline) do
    limit = System.monotonic_time() + System.convert_time_unit(@lookup_timeout, :millisecond, :native)
    min(limit, deadline)
  end

  defp ensure_owner(owner) do
    case GenServer.start(__MODULE__, [owner: owner, automatic: true], name: __MODULE__) do
      {:ok, _pid} -> :ok
      {:error, {:already_started, _pid}} -> :ok
      {:error, _} = error -> error
    end
  end

  @impl true
  def init(opts) do
    Process.flag(:trap_exit, true)
    owner = Keyword.fetch!(opts, :owner)

    if is_pid(owner) and Process.alive?(owner) do
      state = %{
        owner: owner,
        monitor: Process.monitor(owner),
        automatic: opts[:automatic] == true,
        incarnation: make_ref(),
        revision: make_ref(),
        phase: if(Keyword.get(opts, :managed, true) == false, do: :inactive, else: :pending),
        generation: nil,
        writer: nil
      }

      {:ok, publish(state)}
    else
      {:stop, :invalid_binding_owner}
    end
  end

  @impl true
  def handle_call({:install, owner}, {writer, _}, %{owner: owner} = state) do
    generation = state.generation || make_ref()
    next = %{state | phase: :active, generation: generation, writer: writer}
    state = if next == state, do: state, else: publish(%{next | revision: make_ref()})
    {:reply, {:ok, generation}, state}
  end

  def handle_call({:install, _owner}, _from, state), do: {:reply, {:error, :binding_owner_conflict}, state}

  def handle_call({:release, generation}, {writer, _}, %{generation: generation, writer: writer} = state) when is_reference(generation) do
    state = publish(%{state | phase: :inactive, generation: nil, writer: nil, revision: make_ref()})
    if state.automatic, do: {:stop, :normal, :ok, state}, else: {:reply, :ok, state}
  end

  def handle_call({:release, _generation}, _from, state), do: {:reply, :ok, state}

  def handle_call({:resolve, incarnation}, _from, %{incarnation: incarnation} = state) do
    result =
      cond do
        not Process.alive?(state.owner) -> {:error, :forbidden}
        state.phase == :inactive -> {:ok, :base, descriptor(state)}
        state.phase == :active and Process.alive?(state.writer) -> {:ok, :managed, descriptor(state)}
        true -> {:error, :forbidden}
      end

    {:reply, result, state}
  end

  def handle_call({:resolve, _incarnation}, _from, state), do: {:reply, {:error, :forbidden}, state}

  @impl true
  def handle_info({:DOWN, monitor, :process, owner, _}, %{monitor: monitor, owner: owner} = state), do: {:stop, :normal, state}
  def handle_info({:EXIT, _, _}, state), do: {:noreply, state}

  defp descriptor(state), do: {self(), state.incarnation, state.revision, state.phase, state.generation, state.owner, state.writer}

  defp publish(state) do
    :persistent_term.put(@context, descriptor(state))
    state
  end

  @impl true
  def terminate(reason, state) when reason in [:normal, :shutdown] do
    # Keep a unique known-legacy revision: erasing would allow an old absent
    # selection to become equal again after an entire managed lifecycle.
    if :persistent_term.get(@context, :absent) == descriptor(state), do: :persistent_term.put(@context, {:legacy, make_ref()})
    :ok
  end

  def terminate(_reason, _state), do: :ok
end
