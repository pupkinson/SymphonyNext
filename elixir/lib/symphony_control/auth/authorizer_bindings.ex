defmodule SymphonyControl.Auth.AuthorizerBindings do
  @moduledoc """
  Lifecycle-owned effective authorizer without changing operator defaults.

  The persistent sentinel identifies a lifecycle, never an authorization grant.
  Unexpected component loss leaves lookup closed until explicit new startup.
  """
  use GenServer
  alias SymphonyControl.Auth.{Authorizer, RequestContext}
  @keys [:project_authorizer, :runtime_identity_authorizer]
  @context {__MODULE__, :lifecycle}
  @lookup_timeout 250

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

  @spec resolve(atom()) :: {:ok, term()} | {:error, :forbidden}
  def resolve(key) when key in @keys do
    case :persistent_term.get(@context, :absent) do
      :absent ->
        if is_nil(Process.whereis(__MODULE__)), do: base(key), else: {:error, :forbidden}

      {pid, incarnation} when is_pid(pid) and is_reference(incarnation) ->
        timeout = lookup_timeout()

        with true <- timeout > 0,
             {:ok, selection} <- GenServer.call(pid, {:resolve, incarnation}, timeout),
             true <- :persistent_term.get(@context, :absent) == {pid, incarnation} and Process.whereis(__MODULE__) == pid do
          selected(selection, key)
        else
          _ -> {:error, :forbidden}
        end

      _ ->
        {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  def resolve(_key), do: {:error, :forbidden}

  defp selected(:managed, _key), do: {:ok, Authorizer}
  defp selected(:base, key), do: base(key)
  defp base(key), do: {:ok, Application.get_env(:symphony_elixir, key)}

  defp lookup_timeout do
    case Process.get({Authorizer, :deadline}) do
      nil -> @lookup_timeout
      deadline -> min(@lookup_timeout, RequestContext.remaining(deadline))
    end
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
      incarnation = make_ref()

      state = %{
        owner: owner,
        monitor: Process.monitor(owner),
        automatic: opts[:automatic] == true,
        incarnation: incarnation,
        phase: if(Keyword.get(opts, :managed, true) == false, do: :inactive, else: :pending),
        generation: nil,
        writer: nil
      }

      :persistent_term.put(@context, {self(), incarnation})
      {:ok, state}
    else
      {:stop, :invalid_binding_owner}
    end
  end

  @impl true
  def handle_call({:install, owner}, {writer, _}, %{owner: owner} = state) do
    generation = state.generation || make_ref()
    {:reply, {:ok, generation}, %{state | phase: :active, generation: generation, writer: writer}}
  end

  def handle_call({:install, _owner}, _from, state), do: {:reply, {:error, :binding_owner_conflict}, state}

  def handle_call({:release, generation}, {writer, _}, %{generation: generation, writer: writer} = state) when is_reference(generation) do
    state = %{state | phase: :inactive, generation: nil, writer: nil}
    if state.automatic, do: {:stop, :normal, :ok, state}, else: {:reply, :ok, state}
  end

  def handle_call({:release, _generation}, _from, state), do: {:reply, :ok, state}

  def handle_call({:resolve, incarnation}, _from, %{incarnation: incarnation} = state) do
    result =
      cond do
        not Process.alive?(state.owner) -> {:error, :forbidden}
        state.phase == :inactive -> {:ok, :base}
        state.phase == :active and Process.alive?(state.writer) -> {:ok, :managed}
        true -> {:error, :forbidden}
      end

    {:reply, result, state}
  end

  def handle_call({:resolve, _incarnation}, _from, state), do: {:reply, {:error, :forbidden}, state}

  @impl true
  def handle_info({:DOWN, monitor, :process, owner, _}, %{monitor: monitor, owner: owner} = state), do: {:stop, :normal, state}
  def handle_info({:EXIT, _, _}, state), do: {:noreply, state}

  @impl true
  def terminate(reason, state) when reason in [:normal, :shutdown] do
    if :persistent_term.get(@context, :absent) == {self(), state.incarnation}, do: :persistent_term.erase(@context)
    :ok
  end

  def terminate(_reason, _state), do: :ok
end
