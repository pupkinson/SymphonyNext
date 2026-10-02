defmodule SymphonyControl.Auth.Principal do
  @moduledoc """
  A validated identity value, NOT an authenticated actor or authorisation grant.

  External equality is kind + exact issuer + exact subject, never email or roles.
  User principals additionally require both local principal and local user UUIDs.
  Service/agent principals cannot acquire user links through these constructors.

  Issuer spelling and subject case/spacing are preserved. UUIDs are normalized.
  All kinds currently require an HTTPS issuer and printable ASCII subject of at
  most 255 bytes. This is a project input contract, not signature, discovery,
  issuer allowlist, audience, session freshness or revocation verification.

  Tokens, sessions, roles, groups and `verified` flags are deliberately absent.
  A future trusted authentication boundary must verify its input before using
  this value; neither a constructor result nor a forged struct confers trust.
  """

  @enforce_keys [:kind, :issuer, :subject, :principal_id]
  @derive {Inspect, only: [:kind]}
  defstruct [:kind, :issuer, :subject, :principal_id, :user_id]

  @type kind :: :user | :service | :agent
  @opaque t :: %__MODULE__{
            kind: kind(),
            issuer: String.t(),
            subject: String.t(),
            principal_id: String.t(),
            user_id: String.t() | nil
          }
  @type identity_key :: {kind(), String.t(), String.t()}
  @type result :: {:ok, t()} | {:error, :invalid_principal}

  @uuid ~r/\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z/
  @printable ~r/\A[\x20-\x7E]+\z/
  @uri_text ~r/\A[\x21-\x7E]+\z/

  @spec user(term(), term(), term(), term()) :: result()
  def user(issuer, subject, principal_id, user_id) do
    case uuid(user_id) do
      {:ok, user_id} -> build(:user, issuer, subject, principal_id, user_id)
      :error -> {:error, :invalid_principal}
    end
  end

  @spec service(term(), term(), term()) :: result()
  def service(issuer, subject, principal_id),
    do: build(:service, issuer, subject, principal_id, nil)

  @spec agent(term(), term(), term()) :: result()
  def agent(issuer, subject, principal_id), do: build(:agent, issuer, subject, principal_id, nil)

  @spec key(t()) :: identity_key()
  def key(%__MODULE__{kind: kind, issuer: issuer, subject: subject}), do: {kind, issuer, subject}

  defp build(kind, issuer, subject, principal_id, user_id) do
    with true <- https_issuer?(issuer),
         true <- subject?(subject),
         {:ok, principal_id} <- uuid(principal_id) do
      {:ok,
       %__MODULE__{
         kind: kind,
         issuer: issuer,
         subject: subject,
         principal_id: principal_id,
         user_id: user_id
       }}
    else
      _invalid -> {:error, :invalid_principal}
    end
  end

  defp https_issuer?(value) when is_binary(value) and byte_size(value) in 1..2048 do
    with true <- Regex.match?(@uri_text, value),
         {:ok,
          %URI{scheme: "https", host: host, port: port, userinfo: nil, query: nil, fragment: nil}} <-
           URI.new(value) do
      is_binary(host) and host != "" and is_integer(port) and port in 1..65_535
    else
      _invalid -> false
    end
  end

  defp https_issuer?(_value), do: false

  defp subject?(value) when is_binary(value) and byte_size(value) in 1..255 do
    Regex.match?(@printable, value)
  end

  defp subject?(_value), do: false

  defp uuid(value) when is_binary(value) and byte_size(value) == 36 do
    if Regex.match?(@uuid, value), do: {:ok, String.downcase(value)}, else: :error
  end

  defp uuid(_value), do: :error
end
