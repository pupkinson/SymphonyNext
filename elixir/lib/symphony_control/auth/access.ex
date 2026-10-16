defmodule SymphonyControl.Auth.Access do
  @moduledoc "Server-only session confirmation. Production eligibility remains denied in Task3."
  use GenServer
  alias SymphonyControl.Auth.{Actor, AuthorizerBindings, Clock, Config, Csrf, Eligibility}
  alias SymphonyControl.Auth.{RequestContext, Routes, Store, Validity}

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, opts, name: __MODULE__)

  @impl true
  def init(opts) do
    Process.flag(:trap_exit, true)
    Process.put({Csrf, :secret}, :crypto.strong_rand_bytes(32))
    callback = Keyword.get(opts, :eligibility_confirm, &Eligibility.confirm/4)
    if not Keyword.has_key?(opts, :eligibility_confirm), do: install_authorizers(Keyword.get(opts, :config))
    if is_function(callback, 4), do: {:ok, {Keyword.get(opts, :config), callback}}, else: {:stop, :invalid_auth_options}
  end

  @impl true
  def handle_call(:binding, _from, state), do: {:reply, state, state}

  def handle_call({:csrf, cfg, actor, operation}, _from, {cfg, _callback} = state),
    do: {:reply, Csrf.perform(actor, operation, Process.get({Csrf, :secret})), state}

  def handle_call({:csrf, _, _, _}, _from, state), do: {:reply, {:error, :forbidden}, state}

  @spec task4?(Config.t(), integer()) :: boolean()
  def task4?(cfg, native_deadline) do
    case GenServer.call(__MODULE__, :binding, RequestContext.remaining(native_deadline)) do
      {^cfg, callback} -> callback == (&Eligibility.confirm/4)
      _ -> false
    end
  catch
    _, _ -> false
  end

  @impl true
  def terminate(_reason, _state) do
    if generation = Process.get({__MODULE__, :authorizers}), do: AuthorizerBindings.release(generation)

    :ok
  end

  defp install_authorizers(%Config{} = cfg) do
    with {:ok, _} <- cfg |> Map.from_struct() |> Map.delete(:tls_cacerts) |> Config.load(),
         :ok <- Routes.validate(cfg) do
      parent = Process.get(:"$ancestors") |> hd()
      owner = if is_pid(parent), do: parent, else: Process.whereis(parent)
      {:ok, generation} = AuthorizerBindings.install(owner)
      Process.put({__MODULE__, :authorizers}, generation)
    end
  end

  defp install_authorizers(_), do: :ok

  @spec configuration(integer()) :: {:ok, Config.t()} | {:error, Config.reason()}
  def configuration(native_deadline) do
    case GenServer.call(__MODULE__, :binding, RequestContext.remaining(native_deadline)) do
      {%Config{} = cfg, _callback} -> {:ok, cfg}
      _ -> {:error, :forbidden}
    end
  catch
    _, _ -> {:error, :forbidden}
  end

  @spec deliverable?(Config.t(), term(), integer()) :: boolean()
  def deliverable?(cfg, actor, native_deadline) do
    deadline = RequestContext.milliseconds(native_deadline)

    with true <- remaining(deadline) > 0,
         {^cfg, callback} <- GenServer.call(__MODULE__, :binding, remaining(deadline)),
         true <- match?(%Validity{deadline: ^native_deadline}, Process.get({__MODULE__, :validity})) do
      accepted_receipt?(confirmation_receipt(callback), cfg, actor, deadline, Process.get({__MODULE__, :validity})) and remaining(deadline) > 0
    else
      _ -> false
    end
  catch
    _, _ -> false
  end

  @spec authorize(Config.t(), term(), term(), term(), Clock.t()) :: :ok | {:error, Config.reason()}
  def authorize(cfg, actor, action, scope, clock),
    do: authorize(cfg, actor, action, scope, clock, Process.get({SymphonyControl.Auth.Authorizer, :deadline}) || RequestContext.deadline())

  @spec authorize(Config.t(), term(), term(), term(), Clock.t(), integer()) :: :ok | {:error, Config.reason()}
  def authorize(cfg, actor, action, scope, clock, native_deadline) do
    deadline = RequestContext.milliseconds(native_deadline)

    with true <- read_action?(action, scope),
         {^cfg, callback} <- GenServer.call(__MODULE__, :binding, remaining(deadline)),
         true <- remaining(deadline) >= 750,
         true <- Store.actor_current?(cfg, actor, clock),
         :ok <- callback.(cfg, actor, clock, deadline),
         receipt = confirmation_receipt(callback),
         true <- remaining(deadline) >= 1_000,
         fresh = Clock.now(250),
         true <- remaining(deadline) >= 750,
         {:ok, {rights, witness}} <- Store.permissions(cfg, actor, scope, fresh, native_deadline),
         true <- MapSet.member?(rights, action),
         true <- remaining(deadline) > 0,
         true <- accepted_receipt?(receipt, cfg, actor, deadline, witness) do
      Process.put({__MODULE__, :validity}, witness)
      :ok
    else
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  defp read_action?(:runtime_identity_read, :platform), do: true
  defp read_action?(:project_read, scope) when is_binary(scope), do: match?({:ok, _}, Ecto.UUID.cast(scope))
  defp read_action?(_, _), do: false

  @spec authenticate(Config.t(), binary(), Clock.t()) :: {:ok, Actor.t()} | {:error, Config.reason()}
  def authenticate(cfg, handle, clock), do: authenticate(cfg, handle, clock, RequestContext.deadline())

  @spec authenticate(Config.t(), binary(), Clock.t(), integer()) :: {:ok, Actor.t()} | {:error, Config.reason()}
  def authenticate(cfg, handle, clock, native_deadline) do
    deadline = RequestContext.milliseconds(native_deadline)
    task = Task.async(fn -> confirm(cfg, handle, clock, deadline) end)

    # Reserve the accepted Clock and Store bounds for the caller's final read.
    # An actor queued by a worker is only a candidate until that decision.
    case Task.yield(task, max(remaining(deadline) - 1_000, 0)) do
      {:ok, {:confirmed, actor, receipt}} ->
        accept(cfg, handle, actor, deadline, receipt, native_deadline)

      {:ok, result} ->
        result

      _ ->
        Task.shutdown(task, :brutal_kill)
        {:error, :dependency_unavailable}
    end
  catch
    _, _ -> {:error, :forbidden}
  end

  defp confirm(%Config{} = cfg, handle, clock, deadline) do
    with {^cfg, callback} <- GenServer.call(__MODULE__, :binding, remaining(deadline)),
         true <- remaining(deadline) >= 750,
         {:ok, actor} <- Store.local_actor(cfg, handle, clock),
         true <- remaining(deadline) > 0,
         :ok <- callback.(cfg, actor, clock, deadline),
         true <- remaining(deadline) > 0 do
      {:confirmed, actor, confirmation_receipt(callback)}
    else
      {:error, reason} when reason in [:dependency_unavailable, :unknown_outcome] -> {:error, :dependency_unavailable}
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :forbidden}
  end

  defp confirm(_, _, _, _), do: {:error, :forbidden}

  defp accept(cfg, handle, actor, deadline, receipt, native_deadline) do
    with true <- remaining(deadline) >= 1_000,
         fresh = Clock.now(250),
         true <- remaining(deadline) >= 750,
         {:ok, {^actor, witness}} <- Store.local_actor(cfg, handle, fresh, native_deadline),
         true <- remaining(deadline) > 0,
         true <- accepted_receipt?(receipt, cfg, actor, deadline, witness) do
      Process.put({__MODULE__, :validity}, witness)
      {:ok, actor}
    else
      {:error, reason} when reason in [:dependency_unavailable, :unknown_outcome] -> {:error, :dependency_unavailable}
      _ -> {:error, :forbidden}
    end
  end

  defp confirmation_receipt(callback) do
    if callback == (&Eligibility.confirm/4), do: {:eligibility, Eligibility.receipt()}, else: :legacy_fixture
  end

  defp accepted_receipt?({:eligibility, receipt}, cfg, actor, deadline, witness), do: Eligibility.current?(receipt, cfg, actor, deadline, witness)
  defp accepted_receipt?(:legacy_fixture, cfg, actor, _deadline, %Validity{deadline: request} = witness), do: Validity.current?(witness, cfg, actor, request)

  defp remaining(deadline), do: max(deadline - System.monotonic_time(:millisecond), 0)
end
