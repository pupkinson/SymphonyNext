defmodule SymphonyControl.RuntimeConfig do
  @moduledoc """
  Load control settings before an escript starts the application.

  Mix embeds config/runtime.exs in Elixir escripts and applies its merged
  configuration persistently before invoking the CLI, even with app: nil.
  This helper retains the explicit CLI environment-validation contract; it is
  not a workaround for missing escript runtime configuration. Control remains
  opt-in through SYMPHONY_CONTROL_ENABLED being exactly "true".
  """

  alias SymphonyControl.Auth.Config
  alias SymphonyControl.Repo
  @auth_keys Map.new(Map.keys(Map.from_struct(%Config{})) -- [:tls_cacerts], &{Atom.to_string(&1), &1})

  @spec configure() :: :ok | {:error, :missing_database_url}
  def configure do
    configure_auth()

    case System.get_env("SYMPHONY_CONTROL_ENABLED") do
      "true" ->
        case System.get_env("SYMPHONY_CONTROL_DATABASE_URL") do
          url when is_binary(url) and byte_size(url) > 0 ->
            Application.put_env(:symphony_elixir, Repo,
              url: url,
              pool_size: 5,
              show_sensitive_data_on_connection_error: false
            )

            Application.put_env(:symphony_elixir, :control_enabled, true)
            configure_identity()

          _missing ->
            {:error, :missing_database_url}
        end

      _disabled ->
        Application.put_env(:symphony_elixir, :control_enabled, false)
        configure_identity()
    end
  end

  @spec load_auth_config(term()) :: {:ok, Config.t()} | {:error, :invalid_auth_config}
  def load_auth_config(path) when is_binary(path) and byte_size(path) in 1..4096 do
    with {:ok, json} <- File.open(path, [:read, :binary], &IO.binread(&1, 32_769)),
         true <- is_binary(json) and byte_size(json) <= 32_768,
         {:ok, input} when is_map(input) <- Jason.decode(json),
         true <- Enum.all?(Map.keys(input), &Map.has_key?(@auth_keys, &1)),
         bindings = Map.new(input, fn {key, value} -> {Map.fetch!(@auth_keys, key), value} end),
         {:ok, config} <- Config.load(bindings) do
      {:ok, config}
    else
      _ -> {:error, :invalid_auth_config}
    end
  end

  def load_auth_config(_), do: {:error, :invalid_auth_config}

  defp configure_auth do
    {config, status} =
      case System.get_env("SYMPHONY_CONTROL_AUTH_CONFIG") do
        nil ->
          {nil, :absent}

        path ->
          case load_auth_config(path) do
            {:ok, cfg} -> {cfg, :unverified}
            _ -> {nil, :invalid}
          end
      end

    Application.put_env(:symphony_elixir, :control_auth_config, config)
    Application.put_env(:symphony_elixir, :control_auth_status, status)
  end

  defp configure_identity do
    Application.put_env(:symphony_elixir, :runtime_identity,
      commit_sha: System.get_env("SYMPHONY_CONTROL_COMMIT_SHA"),
      image_digest: System.get_env("SYMPHONY_CONTROL_IMAGE_DIGEST"),
      config_sha256: System.get_env("SYMPHONY_CONTROL_CONFIG_SHA256")
    )
  end
end
