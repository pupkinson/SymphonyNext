defmodule SymphonyControl.Auth.EnvironmentTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Access, Config}
  alias SymphonyControl.{AuthHttpFixture, RuntimeConfig}
  alias SymphonyElixir.{ControlBoundary, SubprocessEnv}

  setup do
    names = ~w(SYMPHONY_CONTROL_AUTH_CONFIG SYMPHONY_CONTROL_AUTH_ENABLED SYMPHONY_CONTROL_ENABLED SYMPHONY_CONTROL_DATABASE_URL SYMPHONY_CONTROL_CLIENT_SECRET_REF SYMPHONY_CONTROL_SESSION_KEY_REF)
    env = Map.new(names, &{&1, System.get_env(&1)})
    config = Map.new([:control_auth_config, :control_auth_status, :control_enabled, :runtime_identity, SymphonyControl.Repo], &{&1, Application.fetch_env(:symphony_elixir, &1)})

    on_exit(fn ->
      Enum.each(env, fn {key, value} -> if value, do: System.put_env(key, value), else: System.delete_env(key) end)

      Enum.each(config, fn {key, value} ->
        case value do
          {:ok, v} -> Application.put_env(:symphony_elixir, key, v)
          :error -> Application.delete_env(:symphony_elixir, key)
        end
      end)
    end)

    Enum.each(names, &System.delete_env/1)
    :ok
  end

  test "closed nonsecret JSON configuration loads before startup but never activates production" do
    f = AuthHttpFixture.start!()
    root = Agent.get(f.provider.state, & &1.root)
    path = Path.join(root, "operator.json")
    bindings = f.config |> Map.from_struct() |> Map.delete(:tls_cacerts)
    File.write!(path, Jason.encode!(bindings))
    assert {:ok, cfg} = RuntimeConfig.load_auth_config(path)
    assert cfg == %{f.config | tls_cacerts: nil}
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
    assert :ok = RuntimeConfig.configure()
    assert Application.get_env(:symphony_elixir, :control_auth_config) == cfg
    refute Config.activation_allowed?(cfg)
    assert {:error, :control_agent_runtime_unsupported} = ControlBoundary.check()
    System.delete_env("SYMPHONY_CONTROL_AUTH_CONFIG")
    assert {:error, :control_agent_runtime_unsupported} = ControlBoundary.check()

    for invalid <- [Map.put(bindings, :callback_module, "Elixir.Evil"), Map.put(bindings, :tls_cacerts, []), [], nil, %{"generation" => "x"}] do
      File.write!(path, Jason.encode!(invalid))
      assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(path)
      System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", path)
      assert :ok = RuntimeConfig.configure()
      assert Application.get_env(:symphony_elixir, :control_auth_config) == nil
    end

    File.write!(path, String.duplicate("x", 32_769))
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(path)
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(path <> "/missing")
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(nil)
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(<<255>>)
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(root)
    File.write!(path, <<255, 0, 1>>)
    assert {:error, :invalid_auth_config} = RuntimeConfig.load_auth_config(path)
  end

  test "auth configuration and loaded secret references block agents before children" do
    old = System.get_env("SYMPHONY_CONTROL_AUTH_CONFIG")
    System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", "/synthetic/no-read")
    on_exit(fn -> if old, do: System.put_env("SYMPHONY_CONTROL_AUTH_CONFIG", old), else: System.delete_env("SYMPHONY_CONTROL_AUTH_CONFIG") end)
    assert {:error, :control_agent_runtime_unsupported} = ControlBoundary.check()
  end

  test "a separately started auth worker also blocks agent admission" do
    start_supervised!({Access, config: nil})
    assert {:error, :control_agent_runtime_unsupported} = ControlBoundary.check()
  end

  test "actual synthetic shell initialization cannot pass auth config or references to child" do
    command =
      "export SYMPHONY_CONTROL_AUTH_CONFIG=/synthetic; export SYMPHONY_CONTROL_CLIENT_SECRET_REF=/synthetic/secret; export SYMPHONY_CONTROL_SESSION_KEY_REF=/synthetic/key; export SYMPHONY_CONTROL_AUTH_ENABLED=true; " <>
        SubprocessEnv.unset_command() <>
        " && test -z \"${SYMPHONY_CONTROL_AUTH_CONFIG+x}\" && test -z \"${SYMPHONY_CONTROL_CLIENT_SECRET_REF+x}\" && test -z \"${SYMPHONY_CONTROL_SESSION_KEY_REF+x}\" && test \"$SYMPHONY_CONTROL_AUTH_ENABLED\" = false"

    assert {"", 0} = System.cmd("bash", ["-c", command], env: SubprocessEnv.system_cmd_env())
  end

  test "actual own child loads runtime config with auth and control disabled" do
    executable = System.find_executable("elixir")

    code = ~S"""
    config = Config.Reader.read!("config/runtime.exs", env: :test)[:symphony_elixir]
    disabled = Keyword.get(config, :control_auth_config) == nil and Keyword.get(config, :control_auth_status) == :absent and not Keyword.get(config, :control_enabled, false)
    clean = Enum.all?(~w(SYMPHONY_CONTROL_AUTH_CONFIG SYMPHONY_CONTROL_CLIENT_SECRET_REF SYMPHONY_CONTROL_SESSION_KEY_REF), &(System.get_env(&1) == nil))
    IO.puts(to_string(disabled and clean and System.get_env("SYMPHONY_CONTROL_AUTH_ENABLED") == "false"))
    """

    env =
      SubprocessEnv.system_cmd_env([{"SYMPHONY_CONTROL_AUTH_CONFIG", "/synthetic/no-read"}, {"SYMPHONY_CONTROL_CLIENT_SECRET_REF", "/synthetic/no-read"}, {"SYMPHONY_CONTROL_AUTH_ENABLED", "true"}])

    assert {"true\n", 0} = System.cmd(executable, ["-e", code], env: env, stderr_to_stdout: true)
  end
end
