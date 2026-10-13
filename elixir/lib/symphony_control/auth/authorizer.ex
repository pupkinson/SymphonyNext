defmodule SymphonyControl.Auth.Authorizer do
  @moduledoc "Current human read permissions; an Actor never carries rights."
  alias SymphonyControl.Auth.{Access, Clock, RequestContext}

  @spec authorize(term(), term(), term()) :: :ok | :deny
  def authorize(actor, :project_read, scope), do: permit(actor, :project_read, scope)
  def authorize(_, _, _), do: :deny

  @spec authorize(term(), term()) :: :ok | :deny
  def authorize(actor, :runtime_identity_read), do: permit(actor, :runtime_identity_read, :platform)
  def authorize(_, _), do: :deny

  defp permit(actor, action, scope) do
    deadline = Process.get({__MODULE__, :deadline}) || RequestContext.deadline()

    with {:ok, cfg} <- Access.configuration(deadline),
         true <- RequestContext.remaining(deadline) > 0,
         clock = Clock.now(min(RequestContext.remaining(deadline), 250)),
         :ok <- Access.authorize(cfg, actor, action, scope, clock, deadline) do
      :ok
    else
      _ -> :deny
    end
  catch
    _, _ -> :deny
  end
end
