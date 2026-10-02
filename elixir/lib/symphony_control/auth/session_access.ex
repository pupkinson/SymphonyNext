defmodule SymphonyControl.Auth.SessionAccess do
  @moduledoc """
  Fail-closed read authorization over TRUSTED SERVER snapshots, not request maps.

  The caller resolves the local principal, session and permissions using an
  authenticated server-side source; this function never verifies OIDC or reads a
  cookie. Supplying well-shaped data is not proof that it came from that source.
  Never expose these arguments as a public API or install a fixture authorizer.

  Both snapshots must be active, match the principal and be younger than 60s.
  checked_at_ms, expires_at_ms and now_ms share one trusted monotonic clock domain.
  checked_at_ms means source freshness, NOT when an old cache was read. Persisted
  timestamps from another clock/process epoch must be discarded and refreshed.
  Latest unavailable/revoked state must not be replaced with an older success.

  Only explicit platform runtime_identity_read or resource-project task_read is
  implemented. Project roles never imply platform access and vice versa. The
  project ID in an action must come from the resolved resource, not a URL claim.
  No default production authorizer or HTTP integration is enabled here.
  """
  alias SymphonyControl.Auth.Principal

  @max_age_ms 60_000
  @project_uuid ~r/\A[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\z/
  @type action :: :runtime_identity_read | {:project, String.t(), :task_read}

  @spec authorize(term(), term(), term(), term(), term()) :: :ok | {:error, :forbidden}
  def authorize(%Principal{kind: :user} = principal, session, permissions, action, now_ms)
      when is_map(session) and is_map(permissions) and is_integer(now_ms) do
    with {:ok, ^principal} <-
           Principal.user(
             principal.issuer,
             principal.subject,
             principal.principal_id,
             principal.user_id
           ),
         true <- session_matches?(session, principal),
         true <- Map.get(permissions, :principal_id) === principal.principal_id,
         true <- fresh?(session, now_ms) and fresh?(permissions, now_ms),
         {:ok, grant} <- required_grant(action),
         grants when is_list(grants) <- Map.get(permissions, :grants),
         true <- Enum.member?(grants, grant) do
      :ok
    else
      _denied -> {:error, :forbidden}
    end
  end

  def authorize(_principal, _session, _permissions, _action, _now), do: {:error, :forbidden}

  defp session_matches?(%{principal_id: id, user_id: user, issuer: issuer, subject: subject}, p) do
    id === p.principal_id and user === p.user_id and issuer === p.issuer and subject === p.subject
  end

  defp session_matches?(_session, _principal), do: false

  defp fresh?(%{state: :active, checked_at_ms: checked, expires_at_ms: expires}, now)
       when is_integer(checked) and is_integer(expires) do
    checked <= now and now - checked < @max_age_ms and now < expires
  end

  defp fresh?(_snapshot, _now), do: false

  defp required_grant(:runtime_identity_read), do: {:ok, {:platform, :runtime_identity_read}}

  defp required_grant({:project, project_id, :task_read})
       when is_binary(project_id) and byte_size(project_id) == 36 do
    if Regex.match?(@project_uuid, project_id),
      do: {:ok, {:project, project_id, :task_read}},
      else: :error
  end

  defp required_grant(_action), do: :error
end
