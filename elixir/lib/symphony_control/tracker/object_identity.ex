defmodule SymphonyControl.Tracker.ObjectIdentity do
  @moduledoc """
  Credential-independent identity of a tracker issue, not a scope or permission.

  Native uses installation UUID plus issue UUID. Linear uses workspace UUID plus
  issue UUID. GitHub.com uses the REST issue `id` (database ID), NEVER its `number`
  or a repository-local display key. Repository, team/project filters, credentials,
  binding generation and local project IDs belong to access/execution context.

  This value neither verifies that the object exists nor claims/locks it. A future
  adapter must establish the canonical ID and authorised scope by live readback;
  migrations/transfers require reconciliation, not guessed ID conversions.
  `key/1` is a candidate storage key, NOT concurrent uniqueness enforcement.
  Only constructor results satisfy the opaque type; a forged struct is not proof.
  """

  @enforce_keys [:provider, :namespace, :object_id]
  @derive {Inspect, only: [:provider]}
  defstruct [:provider, :namespace, :object_id]

  @type provider :: :native | :github | :linear
  @opaque t :: %__MODULE__{
            provider: provider(),
            namespace: String.t(),
            object_id: String.t() | pos_integer()
          }
  @type identity_key :: {provider(), String.t(), String.t() | pos_integer()}
  @type result :: {:ok, t()} | {:error, :invalid_object_identity}

  @uuid ~r/\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z/

  @spec native(term(), term()) :: result()
  def native(installation_id, issue_id), do: uuid_identity(:native, installation_id, issue_id)

  @spec github(term()) :: result()
  def github(database_id) when is_integer(database_id) and database_id > 0 do
    {:ok, %__MODULE__{provider: :github, namespace: "github.com", object_id: database_id}}
  end

  def github(_database_id), do: {:error, :invalid_object_identity}

  @spec linear(term(), term()) :: result()
  def linear(workspace_id, issue_id), do: uuid_identity(:linear, workspace_id, issue_id)

  @spec key(t()) :: identity_key()
  def key(%__MODULE__{provider: provider, namespace: namespace, object_id: object_id}) do
    {provider, namespace, object_id}
  end

  defp uuid_identity(provider, namespace, object_id) do
    with {:ok, namespace} <- uuid(namespace), {:ok, object_id} <- uuid(object_id) do
      {:ok, %__MODULE__{provider: provider, namespace: namespace, object_id: object_id}}
    else
      :error -> {:error, :invalid_object_identity}
    end
  end

  defp uuid(value) when is_binary(value) and byte_size(value) == 36 do
    if Regex.match?(@uuid, value), do: {:ok, String.downcase(value)}, else: :error
  end

  defp uuid(_value), do: :error
end
