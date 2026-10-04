defmodule SymphonyControl.Application do
  @moduledoc """
  Opt-in supervision boundary for the native control domain.

  Enabling this supervisor starts the dedicated repository and an optional
  loopback HTTP listener, never another scheduler or an automatic migration.
  Execution admission remains separate.
  """

  use Supervisor

  alias SymphonyControl.{Repo, Router}

  @spec start_link(keyword()) :: Supervisor.on_start() | :ignore
  def start_link(opts \\ []) do
    if Keyword.get(opts, :enabled, Application.get_env(:symphony_elixir, :control_enabled, false)) == true do
      with {:ok, http_children} <- http_children(Keyword.get(opts, :http)) do
        Supervisor.start_link(__MODULE__, {opts, http_children}, name: __MODULE__)
      end
    else
      :ignore
    end
  end

  @impl true
  def init({opts, http_children}) do
    repo_opts =
      opts
      |> Keyword.get(:repo, Application.get_env(:symphony_elixir, Repo, []))
      |> Keyword.put(:show_sensitive_data_on_connection_error, false)

    Supervisor.init([{Repo, repo_opts} | http_children], strategy: :one_for_one)
  end

  defp http_children(nil), do: {:ok, []}

  defp http_children(port: port) when is_integer(port) and port >= 0 and port <= 65_535 do
    options = [plug: Router, scheme: :http, ip: {127, 0, 0, 1}, port: port, startup_log: false]
    {:ok, [Supervisor.child_spec({Bandit, options}, id: Router)]}
  end

  defp http_children(_options), do: {:error, :invalid_control_http_options}
end
