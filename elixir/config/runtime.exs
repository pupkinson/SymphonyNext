import Config

case System.get_env("SYMPHONY_CONTROL_AUTH_CONFIG") do
  nil ->
    config :symphony_elixir, control_auth_config: nil, control_auth_status: :absent

  path ->
    case SymphonyControl.RuntimeConfig.load_auth_config(path) do
      {:ok, cfg} -> config :symphony_elixir, control_auth_config: cfg, control_auth_status: :unverified
      _ -> raise "invalid_control_auth_config"
    end
end

if System.get_env("SYMPHONY_CONTROL_ENABLED") == "true" do
  config :symphony_elixir, :control_enabled, true

  config :symphony_elixir, SymphonyControl.Repo,
    url: System.fetch_env!("SYMPHONY_CONTROL_DATABASE_URL"),
    pool_size: 5,
    show_sensitive_data_on_connection_error: false
end

config :symphony_elixir, :runtime_identity,
  commit_sha: System.get_env("SYMPHONY_CONTROL_COMMIT_SHA"),
  image_digest: System.get_env("SYMPHONY_CONTROL_IMAGE_DIGEST"),
  config_sha256: System.get_env("SYMPHONY_CONTROL_CONFIG_SHA256")
