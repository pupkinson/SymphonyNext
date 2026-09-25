defmodule SymphonyControl.RuntimeConfigTest do
  use ExUnit.Case, async: false

  @keys ~w(SYMPHONY_CONTROL_ENABLED SYMPHONY_CONTROL_DATABASE_URL)

  setup do
    original = Map.new(@keys, &{&1, System.get_env(&1)})
    Enum.each(@keys, &System.delete_env/1)

    on_exit(fn ->
      Enum.each(original, fn
        {key, nil} -> System.delete_env(key)
        {key, value} -> System.put_env(key, value)
      end)
    end)

    :ok
  end

  test "control remains disabled without explicit configuration" do
    config = Config.Reader.read!("config/runtime.exs", env: :test)
    refute Keyword.get(config[:symphony_elixir], :control_enabled, false)
  end

  test "explicit enablement requires a dedicated database configuration" do
    System.put_env("SYMPHONY_CONTROL_ENABLED", "true")
    assert_raise System.EnvError, fn -> Config.Reader.read!("config/runtime.exs", env: :test) end

    database = "postgresql://sn004_fixture@localhost/sn004_test"
    System.put_env("SYMPHONY_CONTROL_DATABASE_URL", database)
    config = Config.Reader.read!("config/runtime.exs", env: :test)[:symphony_elixir]
    assert config[:control_enabled]
    assert config[SymphonyControl.Repo][:url] == database
    refute config[SymphonyControl.Repo][:show_sensitive_data_on_connection_error]
  end
end
