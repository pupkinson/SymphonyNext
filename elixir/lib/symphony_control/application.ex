defmodule SymphonyControl.Application do
  @moduledoc """
  Opt-in supervision boundary for the native control domain.

  Enabling this supervisor starts the dedicated repository, never another
  scheduler or an automatic migration. Execution admission remains separate.
  """

  use Supervisor

  alias SymphonyControl.Repo

  @spec start_link(keyword()) :: Supervisor.on_start() | :ignore
  def start_link(opts \\ []) do
    if Keyword.get(opts, :enabled, Application.get_env(:symphony_elixir, :control_enabled, false)) == true do
      Supervisor.start_link(__MODULE__, opts, name: __MODULE__)
    else
      :ignore
    end
  end

  @impl true
  def init(opts) do
    repo_opts =
      opts
      |> Keyword.get(:repo, Application.get_env(:symphony_elixir, Repo, []))
      |> Keyword.put(:show_sensitive_data_on_connection_error, false)

    Supervisor.init([{Repo, repo_opts}], strategy: :one_for_one)
  end
end
