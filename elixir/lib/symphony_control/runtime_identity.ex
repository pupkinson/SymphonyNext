defmodule SymphonyControl.RuntimeIdentity do
  @moduledoc """
  Runtime identity disclosed only through a configured server authorizer.

  No authorizer is installed by default. SN-005 supplies the authenticated
  actor and authorization implementation; browser parameters cannot select it.
  Hashes are reported observations, not proof of independently verified images.
  """

  @type identity :: %{
          schema_version: 1,
          commit_sha: String.t(),
          image_digest: String.t(),
          config_sha256: String.t()
        }

  @spec read(term()) :: {:ok, identity()} | {:error, :forbidden}
  def read(actor) do
    with module when is_atom(module) and not is_nil(module) <-
           Application.get_env(:symphony_elixir, :runtime_identity_authorizer),
         :ok <- module.authorize(actor, :runtime_identity_read) do
      {:ok, snapshot()}
    else
      _denied -> {:error, :forbidden}
    end
  rescue
    _error -> {:error, :forbidden}
  catch
    _kind, _reason -> {:error, :forbidden}
  end

  defp snapshot do
    values = Application.get_env(:symphony_elixir, :runtime_identity, [])

    %{
      schema_version: 1,
      commit_sha: hash(Keyword.get(values, :commit_sha), ~r/\A[0-9a-f]{40}\z/),
      image_digest: hash(Keyword.get(values, :image_digest), ~r/\Asha256:[0-9a-f]{64}\z/),
      config_sha256: hash(Keyword.get(values, :config_sha256), ~r/\A[0-9a-f]{64}\z/)
    }
  end

  defp hash(value, pattern) when is_binary(value) do
    if Regex.match?(pattern, value), do: value, else: "UNKNOWN"
  end

  defp hash(_value, _pattern), do: "UNKNOWN"
end
