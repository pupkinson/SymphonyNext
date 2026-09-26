defmodule SymphonyControl.RuntimeConfig do
  @moduledoc """
  Load control settings before an escript starts the application.

  Mix releases also evaluate config/runtime.exs. The escript does not bundle that
  file, so the CLI applies the same environment contract explicitly. Neither
  path enables control unless SYMPHONY_CONTROL_ENABLED is exactly "true".
  """

  alias SymphonyControl.Repo

  @spec configure() :: :ok | {:error, :missing_database_url}
  def configure do
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

  defp configure_identity do
    Application.put_env(:symphony_elixir, :runtime_identity,
      commit_sha: System.get_env("SYMPHONY_CONTROL_COMMIT_SHA"),
      image_digest: System.get_env("SYMPHONY_CONTROL_IMAGE_DIGEST"),
      config_sha256: System.get_env("SYMPHONY_CONTROL_CONFIG_SHA256")
    )
  end
end
