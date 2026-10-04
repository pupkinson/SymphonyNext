defmodule SymphonyElixir.SubprocessEnv do
  @moduledoc false

  @control_secrets ["SYMPHONY_CONTROL_DATABASE_URL"]
  @control_enabled "SYMPHONY_CONTROL_ENABLED"

  @spec system_cmd_env(Enumerable.t()) :: [{String.t(), String.t() | nil}]
  def system_cmd_env(env \\ []) do
    Enum.reject(env, fn {name, _value} -> name in [@control_enabled | @control_secrets] end) ++
      Enum.map(@control_secrets, &{&1, nil}) ++ [{@control_enabled, "false"}]
  end

  @spec port_env([String.t()]) :: [{charlist(), charlist() | false}]
  def port_env(extra_secrets \\ []) do
    Enum.map(secret_names(extra_secrets), &{String.to_charlist(&1), false}) ++
      [{String.to_charlist(@control_enabled), ~c"false"}]
  end

  @spec unset_command([String.t()]) :: String.t()
  def unset_command(extra_secrets \\ []) do
    "unset " <> Enum.join(secret_names(extra_secrets), " ") <> " && export #{@control_enabled}=false"
  end

  defp secret_names(extra_secrets), do: Enum.uniq(extra_secrets ++ @control_secrets) -- [@control_enabled]
end
