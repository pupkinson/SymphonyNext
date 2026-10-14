defmodule SymphonyControl.Auth.AccessTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Access, Actor, Authorizer, Clock, RequestContext, Store, TokenVault}
  alias SymphonyControl.{AuthDbFixture, AuthHttpFixture, Repo}

  for role <- [:viewer, :contributor, :operator, :approver, :project_admin] do
    @role role
    test "#{role} reads only its current project membership" do
      f = AuthHttpFixture.start!(project_authorizer: Authorizer, runtime_identity_authorizer: Authorizer)
      project = AuthDbFixture.seed_project!()
      other = AuthDbFixture.seed_project!()
      AuthDbFixture.seed_membership!(f.db, f.user, project, [@role])
      login = AuthHttpFixture.login!(f)
      [_, handle] = String.split(login.cookie, "=", parts: 2)
      assert {:ok, actor} = Access.authenticate(f.config, handle, Clock.now())
      assert :ok == Authorizer.authorize(actor, :project_read, project)
      assert :deny == Authorizer.authorize(actor, :project_read, other)
      assert :deny == Authorizer.authorize(actor, :runtime_identity_read)
      assert :deny == Authorizer.authorize(actor, :project_rename, project)
      assert :deny == Authorizer.authorize(actor, :project_create, :platform)
      assert AuthHttpFixture.get(f, "/api/v1/projects/" <> project, cookie: login.cookie).status == 200
      Repo.query!("DELETE FROM control_auth_memberships WHERE user_id=$1", [AuthDbFixture.uuid(f.user)], log: false)
      assert :deny == Authorizer.authorize(actor, :project_read, project)
      assert AuthHttpFixture.get(f, "/api/v1/projects/" <> project, cookie: login.cookie).status == 403
    end
  end

  test "platform identity grant never creates a project right and its deletion is immediate" do
    f = AuthHttpFixture.start!(project_authorizer: Authorizer, runtime_identity_authorizer: Authorizer)
    project = AuthDbFixture.seed_project!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Access.authenticate(f.config, handle, Clock.now())
    Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), AuthDbFixture.uuid(f.user)], log: false)
    assert :ok == Authorizer.authorize(actor, :runtime_identity_read)
    assert :deny == Authorizer.authorize(actor, :project_read, project)
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: login.cookie).status == 200
    Repo.query!("DELETE FROM control_auth_platform_grants WHERE user_id=$1", [AuthDbFixture.uuid(f.user)], log: false)
    assert :deny == Authorizer.authorize(actor, :runtime_identity_read)
  end

  test "malformed actors actions and scopes safely deny" do
    for actor <- [nil, %{}, %{kind: :service}, %{kind: :agent}, struct(Actor)],
        scope <- [nil, %{}, "bad-uuid", :platform] do
      assert :deny == Authorizer.authorize(actor, :project_read, scope)
      assert :deny == Authorizer.authorize(actor, :runtime_identity_read)
    end
  end

  test "session material is server private exact and rejects stale binding" do
    f = AuthHttpFixture.start!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    assert {:ok, material} = Store.session_material(f.config, actor, Clock.now())
    assert material.actor == actor
    assert is_binary(material.sid)
    assert is_binary(material.tokens.id)
    refute Map.has_key?(Map.from_struct(actor), :tokens)
    refute Map.has_key?(Map.from_struct(actor), :sid)
    assert {:error, :forbidden} = Store.session_material(f.config, %{actor | subject: "foreign"}, Clock.now())
    assert {:error, :forbidden} = Store.session_material(f.config, %{}, Clock.now())
    assert :ok = Store.revoke(f.config, {:session, actor.session_id}, Clock.now())
    assert {:error, :forbidden} = Store.session_material(f.config, actor, Clock.now())
  end

  test "unknown private token structure cannot reach a server consumer" do
    f = AuthDbFixture.start!()
    AuthDbFixture.seed_user!(f)
    identity = AuthDbFixture.identity(f)
    assert {:ok, handle} = Store.open_session(f.config, identity, nil, AuthDbFixture.clock(f))
    assert {:ok, actor} = Store.local_actor(f.config, handle, AuthDbFixture.clock(f))
    assert {:error, :forbidden} = Store.session_material(f.config, actor, AuthDbFixture.clock(f))
  end

  test "private material refuses unsafe compressed oversized and open token structures" do
    f = AuthHttpFixture.start!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    assert {:ok, material} = Store.session_material(f.config, actor, Clock.now())
    aad = :erlang.term_to_binary({1, :session, actor.session_id, f.config.generation})

    invalid = [
      <<131, 119, 32, "unknown_uninterned_atom_1234567890">>,
      :erlang.term_to_binary(material.tokens, [:compressed]),
      :erlang.term_to_binary(%{material.tokens | id: String.duplicate("x", 16_385)}),
      :erlang.term_to_binary(Map.put(material.tokens, :roles, [:project_admin])),
      :erlang.term_to_binary(%{material.tokens | access: nil}),
      :erlang.term_to_binary(%{material.tokens | access: %{material.tokens.access | token: ""}}),
      :erlang.term_to_binary(%{material.tokens | access: %{material.tokens.access | expires: 0}})
    ]

    for plain <- invalid do
      assert {:ok, cipher} = TokenVault.seal(f.config, plain, aad)
      Repo.query!("UPDATE control_auth_sessions SET tokens_ciphertext=$1 WHERE id=$2", [cipher, AuthDbFixture.uuid(actor.session_id)], log: false)
      assert {:error, :forbidden} = Store.session_material(f.config, actor, Clock.now())
    end
  end

  test "the private read bounds ciphertext in PostgreSQL before transport and decryption" do
    f = AuthHttpFixture.start!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    aad = :erlang.term_to_binary({1, :session, actor.session_id, f.config.generation})
    assert {:ok, cipher} = TokenVault.seal(f.config, String.duplicate("x", 1_048_576), aad)
    Repo.query!("UPDATE control_auth_sessions SET tokens_ciphertext=$1 WHERE id=$2", [cipher, AuthDbFixture.uuid(actor.session_id)], log: false)
    id = make_ref()
    owner = self()

    :ok =
      :telemetry.attach(
        id,
        [:symphony_control, :repo, :query],
        fn _, _, metadata, _ ->
          case metadata.result do
            {:ok, %{rows: [[_, _, _, _, value | _]]}} ->
              bytes = if is_binary(value), do: byte_size(value), else: 0
              send(owner, {:selected_cipher_bytes, bytes})

            _ ->
              :ok
          end
        end,
        nil
      )

    on_exit(fn -> :telemetry.detach(id) end)
    assert {:error, _} = Store.session_material(f.config, actor, Clock.now())
    assert_receive {:selected_cipher_bytes, 0}
  end

  test "undefined access-token expiry retains the stricter stored credential lifetime" do
    f = AuthHttpFixture.start!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    assert {:ok, material} = Store.session_material(f.config, actor, Clock.now())
    tokens = %{material.tokens | access: %{material.tokens.access | expires: :undefined}}
    aad = :erlang.term_to_binary({1, :session, actor.session_id, f.config.generation})
    assert {:ok, cipher} = TokenVault.seal(f.config, :erlang.term_to_binary(tokens), aad)
    Repo.query!("UPDATE control_auth_sessions SET tokens_ciphertext=$1 WHERE id=$2", [cipher, AuthDbFixture.uuid(actor.session_id)], log: false)
    assert {:ok, _} = Store.session_material(f.config, actor, Clock.now())
    AuthDbFixture.set_clock!(f.db, Clock.now())
    AuthDbFixture.advance!(f.db, 120_001)
    assert {:error, :forbidden} = Store.session_material(f.config, actor, Clock.now())
  end

  test "Access and authorizers deny invalid operations and a raising or exiting adapter" do
    f = AuthHttpFixture.start!()
    login = AuthHttpFixture.login!(f)
    [_, handle] = String.split(login.cookie, "=", parts: 2)
    assert {:ok, actor} = Store.local_actor(f.config, handle, Clock.now())
    project = AuthDbFixture.seed_project!()
    AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
    assert :ok = Access.authorize(f.config, actor, :project_read, project, Clock.now())
    assert {:error, :forbidden} = Access.authorize(f.config, actor, :enqueue, :platform, Clock.now())
    assert :deny = Authorizer.authorize(actor, :enqueue)

    for callback <- [fn _, _, _, _ -> raise "owned adapter failure" end, fn _, _, _, _ -> exit(:owned_failure) end] do
      :sys.replace_state(Access, fn {cfg, _} -> {cfg, callback} end)
      assert {:error, :forbidden} = Access.authorize(f.config, actor, :project_read, project, Clock.now())
    end

    assert {:error, :forbidden} = Access.authorize(f.config, actor, :project_read, project, %{})
    refute Access.task4?(%{f.config | generation: "other"}, RequestContext.deadline())
    refute Access.deliverable?(f.config, actor, "invalid deadline")
    :sys.replace_state(Access, fn _ -> {nil, fn _, _, _, _ -> :ok end} end)
    assert {:error, :forbidden} = Access.configuration(RequestContext.deadline())
    stop_supervised!(Access)
    refute Access.task4?(f.config, RequestContext.deadline())
    assert :deny = Authorizer.authorize(actor, :project_read, project)
  end

  test "admitted default authorizers restore prior nil and explicit bindings on shutdown" do
    f = AuthHttpFixture.start!(task4: true)
    assert Application.get_env(:symphony_elixir, :project_authorizer) == Authorizer
    stop_supervised!(Access)
    assert Application.get_env(:symphony_elixir, :project_authorizer) == nil
    Application.delete_env(:symphony_elixir, :project_authorizer)
    Application.delete_env(:symphony_elixir, :runtime_identity_authorizer)
    start_supervised!({Access, config: f.config})
    stop_supervised!(Access)
    assert Application.fetch_env(:symphony_elixir, :project_authorizer) == :error
  end

  for axis <- [:session, :credential], operation <- [:authenticate, :authorize] do
    @axis axis
    @operation operation
    @tag :repair_r1
    test "R1 #{@operation} retains #{@axis} lifetime through measured receipt delivery" do
      f = AuthHttpFixture.start!(task4: true)
      project = AuthDbFixture.seed_project!()
      AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
      login = AuthHttpFixture.login!(f)
      [_, handle] = String.split(login.cookie, "=", parts: 2)
      assert {:ok, actor} = Access.authenticate(f.config, handle, Clock.now())
      assert :ok = Access.authorize(f.config, actor, :project_read, project, Clock.now())
      column = if @axis == :session, do: "expires_at_ms", else: "credential_expires_at_ms"
      expiry = Clock.now().utc_ms + 10_000
      update = if @axis == :credential, do: "credential_expires_at_ms=$1,expires_at_ms=LEAST(expires_at_ms,$1)", else: "#{column}=$1"
      Repo.query!("UPDATE control_auth_sessions SET #{update} WHERE id=$2", [expiry, AuthDbFixture.uuid(actor.session_id)], log: false)
      nth = if @operation == :authenticate, do: 2, else: 2
      ref = AuthDbFixture.hold_clock_reply!({:stack, SymphonyControl.Auth.Eligibility, :current?, nth, expiry})

      caller =
        Task.async(fn ->
          if @operation == :authenticate,
            do: Access.authenticate(f.config, handle, Clock.now()),
            else: Access.authorize(f.config, actor, :project_read, project, Clock.now())
        end)

      assert_receive {:clock_reply_held, ^ref, _from, producer}, 1000
      assert_receive {:clock_sample_measured, ^ref, _from, ^producer, sample, measured}, 1000
      assert sample.utc_ms < expiry
      assert sample.utc_ms == expiry - 20
      assert_receive {:clock_reply_released, ^ref, released}, 1000
      assert released - measured < System.convert_time_unit(250, :millisecond, :native)
      result = Task.await(caller, 1500)
      assert match?({:error, _}, result), "late authority was released after local lifetime"
    end
  end

  for before <- [:missing, nil, __MODULE__] do
    @before before
    @tag :repair_r6
    test "R6 abrupt Access restarts preserve original #{inspect(before)} bindings" do
      f = AuthHttpFixture.start!(task4: true)
      project = AuthDbFixture.seed_project!()
      AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
      login = AuthHttpFixture.login!(f)
      stop_supervised!(Access)
      keys = [:project_authorizer, :runtime_identity_authorizer]
      saved = for key <- keys, do: {key, Application.fetch_env(:symphony_elixir, key)}
      on_exit(fn -> Enum.each(saved, fn {key, value} -> restore_binding(key, value) end) end)
      Enum.each(keys, fn key -> if @before == :missing, do: Application.delete_env(:symphony_elixir, key), else: Application.put_env(:symphony_elixir, key, @before) end)
      {:ok, supervisor} = Supervisor.start_link([{Access, config: f.config}], strategy: :one_for_one)

      for _ <- 1..2 do
        old = Process.whereis(Access)
        Process.exit(old, :kill)
        AuthDbFixture.await!(fn -> is_pid(Process.whereis(Access)) and Process.whereis(Access) != old end)
        assert AuthHttpFixture.get(f, "/api/v1/projects/" <> project, cookie: login.cookie).status == 200
      end

      Supervisor.stop(supervisor)
      expected = if @before == :missing, do: :error, else: {:ok, @before}
      Enum.each(keys, fn key -> assert Application.fetch_env(:symphony_elixir, key) == expected end)
    end
  end

  defp restore_binding(key, :error), do: Application.delete_env(:symphony_elixir, key)
  defp restore_binding(key, {:ok, value}), do: Application.put_env(:symphony_elixir, key, value)

  for axis <- [:session, :credential] do
    @axis axis
    @tag :repair_r1
    test "R1 project domain read delayed beyond #{@axis} never sends private body" do
      f = AuthHttpFixture.start!(task4: true)
      project = AuthDbFixture.seed_project!()
      AuthDbFixture.seed_membership!(f.db, f.user, project, [:viewer])
      login = AuthHttpFixture.login!(f)
      path = "/api/v1/projects/" <> project
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
      expiry = Clock.now().utc_ms + 400
      update = if @axis == :credential, do: "credential_expires_at_ms=$1,expires_at_ms=LEAST(expires_at_ms,$1)", else: "expires_at_ms=$1"
      Repo.query!("UPDATE control_auth_sessions SET #{update}", [expiry], log: false)
      ref = AuthDbFixture.barrier!("\"projects\"")
      request = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
      assert_receive {:query_result_held, ^ref, worker}, 1000
      Process.sleep(max(expiry - Clock.now().utc_ms + 20, 20))
      send(worker, {:release_query, ref})
      response = Task.await(request, 2000)
      assert response.status in [403, 503]
      refute inspect(response.body) =~ project
      assert Req.Response.get_header(response, "set-cookie") == []
    end
  end

  for axis <- [:session, :credential] do
    @axis axis
    @tag :repair_identity
    test "R1 runtime identity snapshot wait beyond #{@axis} never sends private identity" do
      f = AuthHttpFixture.start!(task4: true)
      Repo.query!("INSERT INTO control_auth_platform_grants(id,user_id,permission,revision) VALUES($1,$2,'runtime_identity_read',1)", [Ecto.UUID.bingenerate(), AuthDbFixture.uuid(f.user)], log: false)
      login = AuthHttpFixture.login!(f)
      path = "/api/v1/control/identity"
      assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
      expiry = Clock.now().utc_ms + 400
      update = if @axis == :credential, do: "credential_expires_at_ms=$1,expires_at_ms=LEAST(expires_at_ms,$1)", else: "expires_at_ms=$1"
      Repo.query!("UPDATE control_auth_sessions SET #{update}", [expiry], log: false)
      ref = AuthDbFixture.hold_identity_read!(f.db)
      request = Task.async(fn -> AuthHttpFixture.get(f, path, cookie: login.cookie) end)
      assert_receive {:identity_read_held, ^ref, _request, controller}, 1500
      Process.sleep(max(expiry - Clock.now().utc_ms + 20, 20))
      send(controller, {:release_identity, ref})
      response = Task.await(request, 2000)
      assert response.status in [403, 503]
      refute Map.has_key?(response.body, "identity")
      refute inspect(response.body) =~ "commit_sha"
      assert Req.Response.get_header(response, "set-cookie") == []
    end
  end

  test "R6 a later external binding survives abrupt restart and final supervisor stop" do
    f = AuthHttpFixture.start!(task4: true)
    stop_supervised!(Access)
    keys = [:project_authorizer, :runtime_identity_authorizer]
    saved = for key <- keys, do: {key, Application.fetch_env(:symphony_elixir, key)}
    on_exit(fn -> Enum.each(saved, fn {key, value} -> restore_binding(key, value) end) end)
    {:ok, supervisor} = Supervisor.start_link([{Access, config: f.config}], strategy: :one_for_one)
    Enum.each(keys, &Application.put_env(:symphony_elixir, &1, __MODULE__))
    old = Process.whereis(Access)
    Process.exit(old, :kill)
    AuthDbFixture.await!(fn -> is_pid(Process.whereis(Access)) and Process.whereis(Access) != old end)
    Enum.each(keys, fn key -> assert Application.fetch_env(:symphony_elixir, key) == {:ok, __MODULE__} end)
    Supervisor.stop(supervisor)
    Enum.each(keys, fn key -> assert Application.fetch_env(:symphony_elixir, key) == {:ok, __MODULE__} end)
  end
end
