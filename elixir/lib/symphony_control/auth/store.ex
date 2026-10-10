defmodule SymphonyControl.Auth.Store do
  @moduledoc """
  Durable local state for trusted control callers. No registration or IdP eligibility authority.
  Each operation owns its transaction and never retries an unknown outcome. Plaintext flows
  and new handles are released only after a confirmed commit. Do not nest these calls in transactions.
  Selectors are internal authority-bearing tuples, never accepted from HTTP parameters.
  """
  alias SymphonyControl.Auth.{Actor, Clock, Config, TokenVault}
  alias SymphonyControl.Repo
  @db_options [queue: false, log: false]
  @deadline_ms 750
  @human_roles ~w(viewer contributor operator approver project_admin)
  @type result(value) :: {:ok, value} | {:error, Config.reason()}
  @type uuid :: Ecto.UUID.t()
  @type selector :: {:session, uuid()} | {:sid, binary(), binary(), binary() | nil} | {:subject, binary(), binary()}

  @spec put_login(Config.t(), binary(), map(), Clock.t()) :: result(Ecto.UUID.t())
  def put_login(cfg, browser, flow, clock) do
    deadline = deadline()

    database(:write, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- login_input(browser, flow, clock),
           # Check trusted time before accessing the key.
           {:ok, _fresh} <- operational_clock(clock),
           {:ok, id, cipher} <- seal_login(cfg, flow) do
        checked(insert_login(cfg, browser, flow, clock, id, cipher), lifetime(clock, clock.utc_ms + 300_000))
      end
    end)
  end

  @spec consume_login(Config.t(), binary(), binary(), Clock.t()) :: result(map())
  def consume_login(cfg, state, browser, clock) do
    deadline = deadline()

    database(:write, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- nonempty_inputs([state, browser], 256),
           # The supplied snapshot and a fresh trusted sample must be usable.
           {:ok, _fresh} <- operational_clock(clock) do
        consume_flow(cfg, state, browser, clock)
      end
    end)
  end

  @spec open_session(Config.t(), map(), binary() | nil, Clock.t()) :: result(binary())
  def open_session(cfg, identity, old_handle, clock) do
    deadline = deadline()

    database(:write, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- identity_input(cfg, identity, clock),
           :ok <- old_handle_input(old_handle),
           {:ok, fresh} <- operational_clock(clock),
           :ok <- identity_input(cfg, identity, fresh),
           {:ok, id, cipher} <- seal_session(cfg, identity) do
        handle = Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
        expiry = min(clock.utc_ms + 3_600_000, identity.credential_expires_at_ms)
        result = insert_session(cfg, identity, old_handle, clock, {id, handle, cipher})
        validity = lifetime(clock, expiry, identity.credential_expires_at_ms)
        checked(result, validity)
      end
    end)
  end

  defp seal_login(cfg, flow) do
    id = Ecto.UUID.generate()
    plain = Jason.encode!(Map.take(flow, [:nonce, :verifier]))
    with {:ok, cipher} <- TokenVault.seal(cfg, plain, aad(:flow, id, cfg)), do: {:ok, id, cipher}
  end

  defp seal_session(cfg, identity) do
    id = Ecto.UUID.generate()

    with {:ok, cipher} <- TokenVault.seal(cfg, :erlang.term_to_binary(identity.tokens), aad(:session, id, cfg)),
         do: {:ok, id, cipher}
  end

  defp insert_login(cfg, browser, flow, clock, id, cipher) do
    query!(
      """
      INSERT INTO control_auth_pending_logins(id,state_hash,browser_hash,flow_ciphertext,
        config_generation,boot_epoch,issued_at_ms,monotonic_issued_ms,expires_at_ms)
      VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9)
      """,
      [uuid(id), hash(flow.state), hash(browser), cipher, cfg.generation, clock.epoch, clock.utc_ms, clock.monotonic_ms, clock.utc_ms + 300_000]
    )

    {:ok, id}
  end

  defp consume_flow(cfg, state, browser, clock) do
    result = transaction(fn -> claim_flow(cfg, state, browser, clock) end)

    with {:ok, {id, cipher, validity}} <- result,
         {:ok, plain} <- TokenVault.open(cfg, cipher, aad(:flow, id, cfg)),
         {:ok, %{"nonce" => nonce, "verifier" => verifier}} <- Jason.decode(plain) do
      checked({:ok, %{state: state, nonce: nonce, verifier: verifier, issued_ms: validity.issued}}, validity)
    else
      {:error, reason} when is_atom(reason) -> {:error, reason}
      _ -> {:error, :forbidden}
    end
  end

  defp claim_flow(cfg, state, browser, clock) do
    rows =
      query!(
        """
        UPDATE control_auth_pending_logins SET consumed_at_ms=$1
        WHERE state_hash=$2 AND browser_hash=$3 AND config_generation=$4 AND boot_epoch=$5
          AND consumed_at_ms IS NULL AND issued_at_ms <= $1 AND expires_at_ms > $1
          AND $6 >= monotonic_issued_ms AND $6 - monotonic_issued_ms < expires_at_ms - issued_at_ms
        RETURNING id,flow_ciphertext,issued_at_ms,monotonic_issued_ms,expires_at_ms
        """,
        [clock.utc_ms, hash(state), hash(browser), cfg.generation, clock.epoch, clock.monotonic_ms]
      ).rows

    case rows do
      [[id, cipher, issued, mono, expiry]] -> {Ecto.UUID.load!(id), cipher, %{issued: issued, mono: mono, expiry: expiry, credential_expiry: expiry, epoch: clock.epoch}}
      [] -> Repo.rollback(:forbidden)
    end
  end

  defp insert_session(cfg, identity, old_handle, clock, {id, handle, cipher}) do
    transaction(fn ->
      user = local_user!(cfg.issuer, identity.subject)
      generation = rotate!(cfg, old_handle, clock)

      query!(
        """
        INSERT INTO control_auth_sessions(id,user_id,issuer,subject,sid,handle_hash,tokens_ciphertext,
          config_generation,session_generation,boot_epoch,issued_at_ms,monotonic_issued_ms,expires_at_ms,credential_expires_at_ms)
        VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)
        """,
        [
          uuid(id),
          user,
          cfg.issuer,
          identity.subject,
          identity.sid,
          hash(handle),
          cipher,
          cfg.generation,
          generation,
          clock.epoch,
          clock.utc_ms,
          clock.monotonic_ms,
          min(clock.utc_ms + 3_600_000, identity.credential_expires_at_ms),
          identity.credential_expires_at_ms
        ]
      )

      handle
    end)
  end

  @spec local_actor(Config.t(), binary(), Clock.t()) :: result(Actor.t())
  def local_actor(cfg, handle, clock) do
    deadline = deadline()

    database(:read, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- nonempty_inputs([handle], 256),
           # Read acceptance also requires a fresh trusted sample.
           {:ok, _fresh} <- operational_clock(clock) do
        candidate(cfg, :handle, hash(handle), clock) |> actor_result()
      end
    end)
  end

  @spec actor_current?(Config.t(), term(), Clock.t()) :: boolean()
  def actor_current?(cfg, actor, clock) do
    deadline = deadline()
    match?({:ok, _}, current(cfg, actor, clock, deadline))
  end

  @spec permissions(Config.t(), term(), Ecto.UUID.t() | :platform, Clock.t()) :: result(MapSet.t())
  def permissions(cfg, actor, scope, clock) do
    deadline = deadline()

    database(:read, deadline, fn ->
      with :ok <- context(cfg, clock),
           {:ok, target} <- scope_id(scope),
           :ok <- actor_input(actor),
           # The SQL statement owns the coherent session/grant decision.
           {:ok, _fresh} <- operational_clock(clock) do
        current_permissions(cfg, actor, target, clock)
      end
    end)
  end

  @spec revoke(Config.t(), selector(), Clock.t()) :: :ok | {:error, Config.reason()}
  def revoke(cfg, selector, clock) do
    deadline = deadline()

    database(:write, deadline, fn ->
      with :ok <- context(cfg, clock),
           {:ok, where, params} <- selector_sql(cfg, selector),
           # Revocation uses the current trusted event time.
           {:ok, fresh} <- operational_clock(clock) do
        revoke_transaction(where, params, fresh)
      end
    end)
    |> committed_ok()
  end

  @spec accept_logout(Config.t(), binary(), selector(), integer(), Clock.t()) :: :ok | {:error, Config.reason()}
  def accept_logout(cfg, jti, selector, retain_until_ms, clock) do
    deadline = deadline()

    database(:write, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- nonempty_inputs([jti], 4096),
           :ok <- retention(retain_until_ms, clock),
           {:ok, where, params} <- selector_sql(cfg, selector),
           {:ok, _fresh} <- operational_clock(clock),
           do: logout_transaction(cfg, jti, retain_until_ms, where, params, clock)
    end)
    |> committed_ok()
  end

  defp current_permissions(cfg, actor, target, clock) do
    with {:guarded, {:ok, {actual, rights}}, validity} <- candidate(cfg, :id, uuid(actor.session_id), clock, target),
         true <- actual == actor do
      {:guarded, {:ok, rights}, validity}
    else
      {:error, _} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  defp revoke_transaction(where, params, clock) do
    transaction(fn ->
      revoke_rows(where, params, clock)
      :ok
    end)
  end

  defp logout_transaction(cfg, jti, retain_until_ms, where, params, clock) do
    transaction(fn ->
      result =
        query!(
          """
          INSERT INTO control_auth_logout_jtis(id,issuer,jti,issued_at_ms,retain_until_ms)
          VALUES($1,$2,$3,$4,$5) ON CONFLICT(issuer,jti) DO NOTHING RETURNING id
          """,
          [Ecto.UUID.bingenerate(), cfg.issuer, jti, clock.utc_ms, retain_until_ms]
        )

      if result.num_rows == 0, do: Repo.rollback(:forbidden)
      revoke_rows(where, params, clock)
      :ok
    end)
  end

  defp committed_ok({:ok, :ok}), do: :ok
  defp committed_ok(error), do: error

  defp current(cfg, actor, clock, deadline) do
    database(:read, deadline, fn ->
      with :ok <- context(cfg, clock),
           :ok <- actor_input(actor),
           # A forged binding cannot bypass the current stored candidate.
           {:ok, _fresh} <- operational_clock(clock) do
        current_candidate(cfg, actor, clock)
      end
    end)
  end

  defp current_candidate(cfg, actor, clock) do
    result = candidate(cfg, :id, uuid(actor.session_id), clock)

    with {:guarded, {:ok, {actual, _rights}}, validity} <- result, true <- actual == actor do
      {:guarded, {:ok, actual}, validity}
    else
      {:error, _} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  defp candidate(cfg, field, value, clock, target \\ :actor) do
    column = if field == :handle, do: "s.handle_hash", else: "s.id"
    {join, grant_column, grant_params} = grant_sql(target)

    rows =
      query!(
        """
        SELECT s.id,s.user_id,s.issuer,s.subject,s.tokens_ciphertext,
          s.issued_at_ms,s.monotonic_issued_ms,s.expires_at_ms,s.credential_expires_at_ms,#{grant_column}
        FROM control_auth_sessions s JOIN control_auth_users u ON u.id=s.user_id
          JOIN control_auth_identities i ON i.issuer=s.issuer AND i.subject=s.subject AND i.user_id=s.user_id
          #{join}
        WHERE #{column}=$1 AND s.issuer=$2 AND s.config_generation=$3 AND s.boot_epoch=$4
          AND u.active AND s.revoked_at_ms IS NULL AND s.issued_at_ms <= $5 AND s.expires_at_ms > $5
          AND s.credential_expires_at_ms > $5 AND $6 >= s.monotonic_issued_ms
          AND $6-s.monotonic_issued_ms < s.expires_at_ms-s.issued_at_ms
        """,
        [value, cfg.issuer, cfg.generation, clock.epoch, clock.utc_ms, clock.monotonic_ms] ++ grant_params
      ).rows

    case rows do
      [[id, user, issuer, subject, cipher, issued, mono, expiry, credential_expiry, grant]] ->
        session = Ecto.UUID.load!(id)

        with {:ok, _plain} <- TokenVault.open(cfg, cipher, aad(:session, session, cfg)) do
          actor = %Actor{session_id: session, local_user_id: Ecto.UUID.load!(user), issuer: issuer, subject: subject, config_generation: cfg.generation, boot_epoch: clock.epoch}
          checked({:ok, {actor, permissions_for(target, grant)}}, %{issued: issued, mono: mono, expiry: expiry, credential_expiry: credential_expiry, epoch: clock.epoch})
        end

      [] ->
        {:error, :forbidden}
    end
  end

  defp local_user!(issuer, subject) do
    case query!(
           """
           SELECT u.id FROM control_auth_identities i JOIN control_auth_users u ON u.id=i.user_id
           WHERE i.issuer=$1 AND i.subject=$2 AND u.active FOR SHARE OF u,i
           """,
           [issuer, subject]
         ).rows do
      [[user]] -> user
      [] -> Repo.rollback(:forbidden)
    end
  end

  defp rotate!(_cfg, nil, _clock), do: 1

  defp rotate!(cfg, handle, clock) do
    case query!(
           """
           UPDATE control_auth_sessions SET revoked_at_ms=GREATEST(issued_at_ms,$1)
           WHERE handle_hash=$2 AND issuer=$3 AND revoked_at_ms IS NULL
           RETURNING session_generation
           """,
           [clock.utc_ms, hash(handle), cfg.issuer]
         ).rows do
      [[revision]] when revision < 2_147_483_647 -> revision + 1
      _ -> Repo.rollback(:forbidden)
    end
  end

  defp grant_sql(:actor), do: {"", "NULL::text", []}
  defp grant_sql(:platform), do: {"LEFT JOIN control_auth_platform_grants g ON g.user_id=s.user_id AND g.revoked_at_ms IS NULL AND g.revision>0", "g.permission", []}
  defp grant_sql(project), do: {"LEFT JOIN control_auth_memberships g ON g.user_id=s.user_id AND g.project_id=$7 AND g.revoked_at_ms IS NULL AND g.revision>0", "g.roles", [project]}
  defp permissions_for(:platform, "runtime_identity_read"), do: MapSet.new([:runtime_identity_read])
  defp permissions_for(project, roles) when is_binary(project) and is_list(roles) and roles != [], do: project_read_permissions(roles)
  defp permissions_for(_target, _grant), do: MapSet.new()

  defp actor_result({:guarded, {:ok, {actor, _rights}}, validity}), do: {:guarded, {:ok, actor}, validity}
  defp actor_result(error), do: error

  defp project_read_permissions(roles) do
    if Enum.all?(roles, &(&1 in @human_roles)), do: MapSet.new([:project_read]), else: MapSet.new()
  end

  defp selector_sql(%Config{issuer: issuer}, {:session, id}) do
    case Ecto.UUID.dump(id) do
      {:ok, binary} -> {:ok, "id=$2 AND issuer=$3", [binary, issuer]}
      _ -> {:error, :invalid_request}
    end
  end

  defp selector_sql(%Config{issuer: issuer}, {:subject, issuer, subject}) when is_binary(subject) and byte_size(subject) > 0,
    do: {:ok, "issuer=$2 AND subject=$3", [issuer, subject]}

  defp selector_sql(%Config{issuer: issuer}, {:sid, issuer, sid, nil}) when is_binary(sid) and byte_size(sid) > 0,
    do: {:ok, "issuer=$2 AND sid=$3", [issuer, sid]}

  defp selector_sql(%Config{issuer: issuer}, {:sid, issuer, sid, subject}) when is_binary(sid) and byte_size(sid) > 0 and is_binary(subject) and byte_size(subject) > 0,
    do: {:ok, "issuer=$2 AND sid=$3 AND subject=$4", [issuer, sid, subject]}

  defp selector_sql(_cfg, _selector), do: {:error, :invalid_request}
  defp revoke_rows(where, params, clock), do: query!("UPDATE control_auth_sessions SET revoked_at_ms=GREATEST(issued_at_ms,$1) WHERE #{where} AND revoked_at_ms IS NULL", [clock.utc_ms | params])

  defp context(%Config{issuer: issuer, generation: generation}, %{utc_ms: utc, monotonic_ms: mono, epoch: epoch})
       when is_binary(issuer) and byte_size(issuer) > 0 and is_binary(generation) and byte_size(generation) > 0 and
              is_integer(utc) and is_integer(mono) and is_binary(epoch) and byte_size(epoch) > 0,
       do: :ok

  defp context(_cfg, _clock), do: {:error, :invalid_request}

  defp login_input(browser, %{state: state, nonce: nonce, verifier: verifier, issued_ms: issued}, clock) do
    with :ok <- nonempty_inputs([browser, state], 256), :ok <- nonempty_inputs([nonce, verifier], 4096), true <- String.valid?(nonce) and String.valid?(verifier), true <- issued == clock.utc_ms do
      :ok
    else
      _ -> {:error, :invalid_request}
    end
  end

  defp login_input(_browser, _flow, _clock), do: {:error, :invalid_request}

  defp identity_input(cfg, %{issuer: issuer, subject: subject, sid: sid, credential_expires_at_ms: expiry, tokens: tokens}, clock)
       when is_binary(subject) and byte_size(subject) > 0 and is_integer(expiry) and is_map(tokens) do
    if issuer == cfg.issuer and expiry > clock.utc_ms and (is_nil(sid) or (is_binary(sid) and byte_size(sid) > 0)), do: :ok, else: {:error, :forbidden}
  end

  defp identity_input(_cfg, _identity, _clock), do: {:error, :forbidden}
  defp old_handle_input(nil), do: :ok
  defp old_handle_input(value), do: nonempty_inputs([value], 256)

  defp actor_input(%Actor{session_id: id, local_user_id: user, issuer: issuer, subject: subject, config_generation: generation, boot_epoch: epoch}) do
    if match?({:ok, _}, Ecto.UUID.dump(id)) and match?({:ok, _}, Ecto.UUID.dump(user)) and
         Enum.all?([issuer, subject, generation, epoch], &(is_binary(&1) and byte_size(&1) > 0)), do: :ok, else: {:error, :forbidden}
  end

  defp actor_input(_actor), do: {:error, :forbidden}

  defp scope_id(:platform), do: {:ok, :platform}

  defp scope_id(value) do
    case Ecto.UUID.dump(value) do
      {:ok, id} -> {:ok, id}
      _ -> {:error, :invalid_request}
    end
  end

  defp retention(value, clock) do
    if is_integer(value) and value >= clock.utc_ms + 3_600_000, do: :ok, else: {:error, :invalid_request}
  end

  defp nonempty_inputs(values, max) do
    if Enum.all?(values, &(is_binary(&1) and byte_size(&1) in 1..max)), do: :ok, else: {:error, :invalid_request}
  end

  defp aad(kind, id, cfg), do: :erlang.term_to_binary({1, kind, id, cfg.generation})
  defp hash(value), do: :crypto.hash(:sha256, value)
  defp uuid(value), do: Ecto.UUID.dump!(value)
  defp query!(sql, params), do: Repo.query!(sql, params, db_options())
  defp transaction(operation), do: Repo.transaction(operation, db_options())

  defp db_options do
    remaining = remaining(Process.get({__MODULE__, :deadline}))
    if remaining == 0, do: throw(:operation_deadline)
    [timeout: min(500, remaining)] ++ @db_options
  end

  defp deadline, do: System.monotonic_time() + System.convert_time_unit(@deadline_ms, :millisecond, :native)
  defp remaining(deadline), do: max(System.convert_time_unit(deadline - System.monotonic_time(), :native, :millisecond), 0)

  defp operational_clock(snapshot) do
    if Process.whereis(Repo) do
      with {:ok, fresh} <- fresh_clock(Process.get({__MODULE__, :deadline})),
           true <-
             supported?(snapshot) and supported?(fresh) and snapshot.epoch == fresh.epoch and
               snapshot.utc_ms <= fresh.utc_ms and snapshot.monotonic_ms <= fresh.monotonic_ms do
        {:ok, fresh}
      else
        {:error, _} = error -> error
        _ -> {:error, :forbidden}
      end
    else
      {:error, :dependency_unavailable}
    end
  end

  defp fresh_clock(deadline) do
    case remaining(deadline) do
      0 -> {:error, :dependency_unavailable}
      budget -> {:ok, Clock.now(budget)}
    end
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  defp supported?(%{sample_valid: true, utc_ms: utc, monotonic_ms: mono, epoch: epoch})
       when is_integer(utc) and is_integer(mono) and is_binary(epoch) and byte_size(epoch) > 0, do: true

  defp supported?(_clock), do: false

  defp lifetime(clock, expiry, credential_expiry \\ nil),
    do: %{issued: clock.utc_ms, mono: clock.monotonic_ms, epoch: clock.epoch, expiry: expiry, credential_expiry: credential_expiry || expiry}

  defp valid_at?(validity, clock) do
    supported?(clock) and clock.epoch == validity.epoch and
      clock.utc_ms >= validity.issued and clock.utc_ms < validity.expiry and clock.utc_ms < validity.credential_expiry and
      clock.monotonic_ms >= validity.mono and clock.monotonic_ms - validity.mono < min(validity.expiry, validity.credential_expiry) - validity.issued
  end

  defp checked({:ok, _} = result, validity) do
    with {:ok, fresh} <- fresh_clock(Process.get({__MODULE__, :deadline})), true <- valid_at?(validity, fresh) do
      {:guarded, result, validity}
    else
      {:error, _} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  defp checked(error, _validity), do: error

  defp database(mode, deadline, operation) do
    unavailable = {:error, if(mode == :write, do: :unknown_outcome, else: :dependency_unavailable)}

    task =
      Task.async(fn ->
        Process.put({__MODULE__, :deadline}, deadline)
        safe_operation(operation, unavailable)
      end)

    case Task.yield(task, remaining(deadline)) do
      {:ok, result} ->
        safe_operation(fn -> accept(result, deadline, unavailable) end, unavailable)

      _ ->
        # Cleanup can observe a real late reply. It never establishes timeliness.
        Task.shutdown(task, :brutal_kill)
        unavailable
    end
  end

  defp accept(result, deadline, unavailable) do
    # Acceptance belongs to the caller, including queued on-time worker replies.
    accepted = accept_fresh(result, deadline)
    if remaining(deadline) > 0, do: accepted, else: unavailable
  end

  defp accept_fresh({:guarded, result, validity}, deadline) do
    with {:ok, fresh} <- fresh_clock(deadline), true <- valid_at?(validity, fresh) do
      result
    else
      {:error, _} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  defp accept_fresh({:ok, _} = result, deadline) do
    with {:ok, fresh} <- fresh_clock(deadline), true <- supported?(fresh) do
      result
    else
      {:error, _} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  defp accept_fresh(error, _deadline), do: error

  defp safe_operation(operation, unavailable) do
    operation.()
  rescue
    _ -> unavailable
  catch
    _kind, _reason -> unavailable
  end
end
