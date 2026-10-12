defmodule SymphonyElixir.ControlBoundary do
  @moduledoc false

  @auth_vars ~w(SYMPHONY_CONTROL_AUTH_CONFIG SYMPHONY_CONTROL_CLIENT_SECRET_REF SYMPHONY_CONTROL_SESSION_KEY_REF)

  @type reason :: :control_agent_runtime_unsupported | :credential_environment_unverifiable

  @spec check() :: :ok | {:error, reason()}
  def check do
    if Application.get_env(:symphony_elixir, :control_enabled, false) == true or
         Application.get_env(:symphony_elixir, SymphonyControl.Repo, [])[:url] != nil or
         System.get_env("SYMPHONY_CONTROL_DATABASE_URL") != nil or
         Process.whereis(SymphonyControl.Application) != nil or
         Process.whereis(SymphonyControl.Auth.Access) != nil or
         Application.get_env(:symphony_elixir, :control_auth_config) != nil or
         System.get_env("SYMPHONY_CONTROL_AUTH_ENABLED") == "true" or
         Enum.any?(@auth_vars, &(System.get_env(&1) != nil)) do
      {:error, :control_agent_runtime_unsupported}
    else
      # Linux retains the environment from exec even after System.delete_env/1.
      # Only inspect this VM; absence of readable startup evidence is a denial.
      "/proc/self/environ" |> File.read() |> validate_startup_environment()
    end
  end

  @doc false
  @spec validate_startup_environment({:ok, binary()} | {:error, File.posix()}) :: :ok | {:error, reason()}
  def validate_startup_environment({:ok, environment}) do
    if Enum.any?(:binary.split(environment, <<0>>, [:global]), &database_assignment?/1) do
      {:error, :control_agent_runtime_unsupported}
    else
      :ok
    end
  end

  def validate_startup_environment({:error, _reason}), do: {:error, :credential_environment_unverifiable}

  defp database_assignment?(<<"SYMPHONY_CONTROL_DATABASE_URL=", _value::binary>>), do: true

  defp database_assignment?(assignment) do
    Enum.any?(@auth_vars, &String.starts_with?(assignment, &1 <> "=")) or assignment == "SYMPHONY_CONTROL_AUTH_ENABLED=true"
  end
end
