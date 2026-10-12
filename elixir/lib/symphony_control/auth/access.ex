defmodule SymphonyControl.Auth.Access do
  @moduledoc "Server-only session confirmation. Production eligibility remains denied in Task3."
  use GenServer
  alias SymphonyControl.Auth.{Actor, Clock, Config, RequestContext, Store}

  @spec start_link(keyword()) :: GenServer.on_start()
  def start_link(opts), do: GenServer.start_link(__MODULE__, opts, name: __MODULE__)

  @impl true
  def init(opts) do
    callback = Keyword.get(opts, :eligibility_confirm, fn _, _, _, _ -> {:error, :forbidden} end)
    if is_function(callback, 4), do: {:ok, {Keyword.get(opts, :config), callback}}, else: {:stop, :invalid_auth_options}
  end

  @impl true
  def handle_call(:binding, _from, state), do: {:reply, state, state}

  @spec authenticate(Config.t(), binary(), Clock.t()) :: {:ok, Actor.t()} | {:error, Config.reason()}
  def authenticate(cfg, handle, clock), do: authenticate(cfg, handle, clock, RequestContext.deadline())

  @spec authenticate(Config.t(), binary(), Clock.t(), integer()) :: {:ok, Actor.t()} | {:error, Config.reason()}
  def authenticate(cfg, handle, clock, native_deadline) do
    deadline = RequestContext.milliseconds(native_deadline)
    task = Task.async(fn -> confirm(cfg, handle, clock, deadline) end)

    # Reserve the accepted Clock and Store bounds for the caller's final read.
    # An actor queued by a worker is only a candidate until that decision.
    case Task.yield(task, max(remaining(deadline) - 1_000, 0)) do
      {:ok, {:confirmed, actor}} ->
        accept(cfg, handle, actor, deadline)

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
      {:confirmed, actor}
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

  defp accept(cfg, handle, actor, deadline) do
    with true <- remaining(deadline) >= 1_000,
         fresh = Clock.now(250),
         true <- remaining(deadline) >= 750,
         {:ok, ^actor} <- Store.local_actor(cfg, handle, fresh),
         true <- remaining(deadline) > 0 do
      {:ok, actor}
    else
      {:error, reason} when reason in [:dependency_unavailable, :unknown_outcome] -> {:error, :dependency_unavailable}
      _ -> {:error, :forbidden}
    end
  end

  defp remaining(deadline), do: max(deadline - System.monotonic_time(:millisecond), 0)
end
