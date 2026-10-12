defmodule SymphonyElixir.SubprocessEnv do
  @moduledoc false

  @control_secrets ~w(SYMPHONY_CONTROL_DATABASE_URL SYMPHONY_CONTROL_AUTH_CONFIG SYMPHONY_CONTROL_CLIENT_SECRET_REF SYMPHONY_CONTROL_SESSION_KEY_REF)
  @auth_enabled "SYMPHONY_CONTROL_AUTH_ENABLED"
  @control_enabled "SYMPHONY_CONTROL_ENABLED"

  @spec system_cmd_env(Enumerable.t()) :: [{String.t(), String.t() | nil}]
  def system_cmd_env(env \\ []) do
    Enum.reject(env, fn {name, _value} -> name in [@control_enabled, @auth_enabled | @control_secrets] end) ++
      Enum.map(@control_secrets, &{&1, nil}) ++ [{@control_enabled, "false"}, {@auth_enabled, "false"}]
  end

  @spec port_env([String.t()]) :: [{charlist(), charlist() | false}]
  def port_env(extra_secrets \\ []) do
    Enum.map(secret_names(extra_secrets), &{String.to_charlist(&1), false}) ++
      [{String.to_charlist(@control_enabled), ~c"false"}, {String.to_charlist(@auth_enabled), ~c"false"}]
  end

  @spec unset_command([String.t()]) :: String.t()
  def unset_command(extra_secrets \\ []) do
    "unset " <> Enum.join(secret_names(extra_secrets), " ") <> " && export #{@control_enabled}=false #{@auth_enabled}=false"
  end

  defp secret_names(extra_secrets), do: Enum.uniq(extra_secrets ++ @control_secrets) -- [@control_enabled, @auth_enabled]
end
