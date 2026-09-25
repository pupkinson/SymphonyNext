import Config

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
