defmodule SymphonyControl.Application do
  @moduledoc """
  Opt-in supervision boundary for the native control domain.

  Enabling this supervisor starts the dedicated repository and an optional
  loopback HTTP listener, never another scheduler or an automatic migration.
  Execution admission remains separate.
  """

  use Supervisor

  alias SymphonyControl.Auth.{Access, Clock, Config, RateLimiter}
  alias SymphonyControl.{Repo, Router}

  @spec start_link(keyword()) :: Supervisor.on_start() | :ignore
  def start_link(opts \\ []) do
    if Keyword.get(opts, :enabled, Application.get_env(:symphony_elixir, :control_enabled, false)) == true do
      with {:ok, auth} <- auth_options(opts),
           {:ok, http_children} <- http_children(Keyword.get(opts, :http), auth) do
        Supervisor.start_link(__MODULE__, {opts, auth, http_children}, name: __MODULE__)
      end
    else
      :ignore
    end
  end

  @impl true
  def init({opts, auth, http_children}) do
    repo_opts =
      opts
      |> Keyword.get(:repo, Application.get_env(:symphony_elixir, Repo, []))
      |> Keyword.put(:show_sensitive_data_on_connection_error, false)

    Supervisor.init([{Repo, repo_opts}] ++ auth_children(auth) ++ http_children, strategy: :one_for_one)
  end

  defp auth_options(opts) do
    auth = Keyword.get(opts, :auth)

    case auth do
      nil -> production_auth()
      [config: %Config{} = cfg] -> validate_auth(cfg, auth)
      [config: %Config{} = cfg, eligibility_confirm: callback] when is_function(callback, 4) -> validate_auth(cfg, auth)
      _ -> {:error, :invalid_auth_options}
    end
  end

  defp production_auth do
    case Application.get_env(:symphony_elixir, :control_auth_config) do
      %Config{} = cfg -> if Config.activation_allowed?(cfg), do: {:ok, [config: cfg]}, else: {:ok, nil}
      _ -> {:ok, nil}
    end
  end

  defp validate_auth(cfg, auth) do
    case cfg |> Map.from_struct() |> Map.delete(:tls_cacerts) |> Config.load() do
      {:ok, _} -> {:ok, auth}
      _ -> {:error, :invalid_auth_options}
    end
  end

  defp auth_children(nil), do: []
  defp auth_children(auth), do: [{Clock, []}, {Access, auth}, {RateLimiter, []}]

  defp http_children(nil, _auth), do: {:ok, []}

  defp http_children([port: port], auth) when is_integer(port) and port >= 0 and port <= 65_535 do
    config = if auth, do: Keyword.fetch!(auth, :config), else: nil
    options = [plug: {Router, [auth: config]}, scheme: :http, ip: {127, 0, 0, 1}, port: port, startup_log: false]
    {:ok, [Supervisor.child_spec({Bandit, options}, id: Router)]}
  end

  defp http_children(_options, _auth), do: {:error, :invalid_control_http_options}
end
