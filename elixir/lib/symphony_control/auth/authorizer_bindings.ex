defmodule SymphonyControl.Auth.AuthorizerBindings do
  @moduledoc "Supervisor-lifetime owner of original global authorizer bindings across Access restarts."
  use GenServer
  alias SymphonyControl.Auth.Authorizer
  @keys [:project_authorizer, :runtime_identity_authorizer]

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, Keyword.put_new(opts, :owner, self()), name: __MODULE__)

  @spec install(pid()) :: {:ok, reference()} | {:error, term()}
  def install(owner) do
    with :ok <- ensure_owner(owner), do: GenServer.call(__MODULE__, {:install, owner, self()})
  end

  @spec release(reference()) :: :ok
  def release(generation) do
    GenServer.call(__MODULE__, {:release, generation, self()})
  catch
    :exit, _ -> :ok
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
        prior: nil,
        generation: nil,
        writer: nil
      }

      {:ok, state}
    else
      {:stop, :invalid_binding_owner}
    end
  end

  @impl true
  def handle_call({:install, owner, writer}, _from, %{owner: owner, prior: nil} = state) do
    prior = for key <- @keys, do: {key, Application.fetch_env(:symphony_elixir, key)}
    generation = make_ref()
    Enum.each(@keys, &Application.put_env(:symphony_elixir, &1, Authorizer))
    {:reply, {:ok, generation}, %{state | prior: prior, generation: generation, writer: writer}}
  end

  def handle_call({:install, owner, writer}, _from, %{owner: owner} = state),
    do: {:reply, {:ok, state.generation}, %{state | writer: writer}}

  def handle_call({:install, _, _}, _from, state), do: {:reply, {:error, :binding_owner_conflict}, state}

  def handle_call({:release, generation, writer}, _from, %{generation: generation, writer: writer} = state) do
    restore(state.prior)
    state = %{state | prior: nil, generation: nil, writer: nil}
    if state.automatic, do: {:stop, :normal, :ok, state}, else: {:reply, :ok, state}
  end

  def handle_call({:release, _, _}, _from, state), do: {:reply, :ok, state}

  @impl true
  def handle_info({:DOWN, monitor, :process, owner, _}, %{monitor: monitor, owner: owner} = state), do: {:stop, :normal, state}
  def handle_info({:EXIT, _, _}, state), do: {:noreply, state}

  @impl true
  def terminate(_reason, state), do: restore(state.prior)

  defp restore(nil), do: :ok

  defp restore(prior) do
    Enum.each(prior, fn {key, previous} ->
      if Application.fetch_env(:symphony_elixir, key) == {:ok, Authorizer}, do: restore_key(key, previous)
    end)
  end

  defp restore_key(key, :error), do: Application.delete_env(:symphony_elixir, key)
  defp restore_key(key, {:ok, value}), do: Application.put_env(:symphony_elixir, key, value)
end
