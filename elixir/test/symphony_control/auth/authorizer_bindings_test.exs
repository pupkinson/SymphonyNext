defmodule SymphonyControl.Auth.AuthorizerBindingsTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, AuthorizerBindings, RequestContext}
  alias SymphonyControl.{AuthDbFixture, Projects, Repo, RuntimeIdentity}
  @keys [:project_authorizer, :runtime_identity_authorizer]

  setup do
    saved = for key <- @keys, do: {key, Application.fetch_env(:symphony_elixir, key)}
    on_exit(fn -> Enum.each(saved, fn {key, previous} -> restore(key, previous) end) end)
    :ok
  end

  test "managed owner installs idempotently fences stale release and preserves later foreign change" do
    owner = self()
    start_supervised!({AuthorizerBindings, owner: owner})
    Application.delete_env(:symphony_elixir, :project_authorizer)
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, nil)
    assert {:ok, generation} = AuthorizerBindings.install(owner)
    assert {:ok, ^generation} = AuthorizerBindings.install(owner)
    assert :ok = AuthorizerBindings.release(make_ref())
    assert Application.fetch_env(:symphony_elixir, :project_authorizer) == :error
    assert AuthorizerBindings.resolve(:project_authorizer) == {:ok, Authorizer}
    foreign = spawn(fn -> receive do: (:stop -> :ok) end)
    assert {:error, :binding_owner_conflict} = AuthorizerBindings.install(foreign)
    send(foreign, :stop)
    send(AuthorizerBindings, {:EXIT, self(), :normal})
    Application.put_env(:symphony_elixir, :project_authorizer, __MODULE__)
    assert :ok = AuthorizerBindings.release(generation)
    assert Application.fetch_env(:symphony_elixir, :project_authorizer) == {:ok, __MODULE__}
    assert Application.fetch_env(:symphony_elixir, :runtime_identity_authorizer) == {:ok, nil}
    assert Process.whereis(AuthorizerBindings)
    assert {:ok, _next} = AuthorizerBindings.install(owner)
    stop_supervised!(AuthorizerBindings)
    assert Application.fetch_env(:symphony_elixir, :project_authorizer) == {:ok, __MODULE__}
    assert Application.fetch_env(:symphony_elixir, :runtime_identity_authorizer) == {:ok, nil}
    assert :ok = AuthorizerBindings.release(make_ref())
  end

  test "automatic owner survives writer disappearance and restores when its supervisor owner dies" do
    owner = spawn(fn -> receive do: (:stop -> :ok) end)
    Application.delete_env(:symphony_elixir, :project_authorizer)
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, __MODULE__)
    assert {:ok, _generation} = AuthorizerBindings.install(owner)
    helper = Process.whereis(AuthorizerBindings)
    assert helper != owner
    Process.exit(owner, :kill)
    AuthDbFixture.await!(fn -> not Process.alive?(helper) end)
    assert Application.fetch_env(:symphony_elixir, :project_authorizer) == :error
    assert Application.fetch_env(:symphony_elixir, :runtime_identity_authorizer) == {:ok, __MODULE__}
  end

  test "invalid lifecycle owner is rejected before installing global bindings" do
    before = Enum.map(@keys, &Application.fetch_env(:symphony_elixir, &1))
    assert {:error, _} = AuthorizerBindings.install(nil)
    assert Enum.map(@keys, &Application.fetch_env(:symphony_elixir, &1)) == before
  end

  @tag :n1_causal_green
  test "direct base writes survive real release in both orders and held teardown without helper writes" do
    owner = self()

    originals = [:error, {:ok, nil}, {:ok, __MODULE__}]
    mutations = [:foreign, :delete, nil, :authorizer, :original, :aba]

    for key <- @keys, original <- originals, mutation <- mutations, timing <- [:before, :during, :after] do
      restore(key, original)
      helper = start_supervised!({AuthorizerBindings, owner: owner})
      trace_base_writes!(helper)
      {writer, generation} = installing_writer(owner)
      assert Application.fetch_env(:symphony_elixir, key) == original
      assert AuthorizerBindings.resolve(key) == {:ok, Authorizer}

      if timing == :during do
        :ok = :sys.suspend(helper)
        send(writer.pid, {:release, generation})
        await_call!(helper, :release)
      end

      if timing != :after, do: write_base!(key, mutation, original)
      if timing == :during, do: :ok = :sys.resume(helper)
      if timing != :during, do: send(writer.pid, {:release, generation})
      assert Task.await(writer, 1000) == :ok
      if timing == :after, do: write_base!(key, mutation, original)

      expected = expected(mutation, original)
      assert Application.fetch_env(:symphony_elixir, key) == expected
      assert AuthorizerBindings.resolve(key) == {:ok, effective(expected)}
      assert_no_base_writes!(helper)
      stop_supervised!(AuthorizerBindings)
      assert Application.fetch_env(:symphony_elixir, key) == expected
    end
  end

  @tag :n1_causal_green
  test "fresh install preserves direct writes queued before its linearization and refuses a foreign owner" do
    owner = self()

    for key <- @keys, original <- [:error, {:ok, nil}, {:ok, __MODULE__}] do
      restore(key, original)
      helper = start_supervised!({AuthorizerBindings, owner: owner})
      :ok = :sys.suspend(helper)
      parent = self()

      writer =
        Task.async(fn ->
          {:ok, generation} = AuthorizerBindings.install(owner)
          send(parent, {:installed_writer, self(), generation})
          receive do: ({:release, ^generation} -> AuthorizerBindings.release(generation))
        end)

      await_call!(helper, :install)
      write_base!(key, :foreign, original)
      :ok = :sys.resume(helper)
      assert_receive {:installed_writer, pid, generation}, 1000
      assert pid == writer.pid
      assert Application.fetch_env(:symphony_elixir, key) == {:ok, ForeignModule}
      assert AuthorizerBindings.resolve(key) == {:ok, Authorizer}
      foreign = spawn(fn -> receive do: (:stop -> :ok) end)
      assert {:error, :binding_owner_conflict} = AuthorizerBindings.install(foreign)
      send(foreign, :stop)
      send(writer.pid, {:release, generation})
      assert Task.await(writer, 1000) == :ok
      stop_supervised!(AuthorizerBindings)
      assert Application.fetch_env(:symphony_elixir, key) == {:ok, ForeignModule}
    end
  end

  @tag :n1_causal_green
  test "old writer and generation cannot release the current writer binding" do
    owner = self()
    helper = start_supervised!({AuthorizerBindings, owner: owner})
    {old, generation} = installing_writer(owner)
    {current, same_generation} = installing_writer(owner)
    assert generation == same_generation
    send(old.pid, {:release, generation})
    assert Task.await(old, 1000) == :ok
    assert AuthorizerBindings.resolve(:project_authorizer) == {:ok, Authorizer}
    assert :sys.get_state(helper).writer == current.pid
    send(current.pid, {:stale, make_ref()})
    assert_receive {:stale_released, pid}, 1000
    assert pid == current.pid
    assert AuthorizerBindings.resolve(:project_authorizer) == {:ok, Authorizer}
    send(current.pid, {:release, generation})
    assert Task.await(current, 1000) == :ok

    assert AuthorizerBindings.resolve(:project_authorizer) ==
             {:ok, Application.get_env(:symphony_elixir, :project_authorizer)}
  end

  defmodule LegacyAuthorizer do
    def authorize(:operator, :runtime_identity_read), do: :ok
    def authorize(_, _), do: :deny
    def authorize(:operator, :project_read, _), do: :ok
    def authorize(_, _, _), do: :deny
  end

  @tag :n1_causal_green
  @tag capture_log: true
  test "unexpected binding component death and pending restart cannot fall back to a permissive base" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)
    Application.put_env(:symphony_elixir, :project_authorizer, LegacyAuthorizer)
    owner = self()
    helper = start_supervised!({AuthorizerBindings, owner: owner})
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
    assert {:ok, old_generation} = AuthorizerBindings.install(owner)
    Process.exit(helper, :kill)
    AuthDbFixture.await!(fn -> is_pid(Process.whereis(AuthorizerBindings)) and Process.whereis(AuthorizerBindings) != helper end)
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
    assert {:error, :forbidden} = SymphonyControl.RuntimeIdentity.read(:operator)
    assert {:error, %{code: :forbidden}} = SymphonyControl.Projects.get_project(:operator, Ecto.UUID.generate())
    assert :ok = AuthorizerBindings.release(old_generation)
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:project_authorizer)
    assert {:ok, new_generation} = AuthorizerBindings.install(owner)
    refute new_generation == old_generation
    assert AuthorizerBindings.resolve(:project_authorizer) == {:ok, Authorizer}
    stop_supervised!(AuthorizerBindings)
    assert AuthorizerBindings.resolve(:runtime_identity_authorizer) == {:ok, LegacyAuthorizer}
    assert {:ok, _} = SymphonyControl.RuntimeIdentity.read(:operator)
  end

  @tag :n1_causal_green
  @tag capture_log: true
  test "abnormal stop retains a closed lifecycle until explicit fresh startup" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)
    helper = start_supervised!({AuthorizerBindings, owner: self()}, restart: :temporary)
    assert {:ok, _} = AuthorizerBindings.install(self())
    assert :ok = GenServer.stop(helper, :owned_unexpected_failure)
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
    start_supervised!({AuthorizerBindings, managed: false})
    assert AuthorizerBindings.resolve(:runtime_identity_authorizer) == {:ok, LegacyAuthorizer}
  end

  @tag :n1_causal_green
  test "resolver is bounded by the original request and never falls back on a stalled lookup" do
    helper = start_supervised!({AuthorizerBindings, owner: self()})
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)
    assert {:ok, _} = AuthorizerBindings.install(self())
    :ok = :sys.suspend(helper)
    started = System.monotonic_time(:millisecond)

    try do
      assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
      assert System.monotonic_time(:millisecond) - started < 750
    after
      :ok = :sys.resume(helper)
    end

    Process.put({Authorizer, :deadline}, System.monotonic_time() - 1)
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
    Process.put({Authorizer, :deadline}, "invalid")
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
    Process.put({Authorizer, :deadline}, RequestContext.deadline())
    assert AuthorizerBindings.resolve(:runtime_identity_authorizer) == {:ok, Authorizer}
    Process.delete({Authorizer, :deadline})
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:unsupported)
    assert {:error, :forbidden} = AuthorizerBindings.resolve(nil)
    assert {:error, :forbidden} = GenServer.call(helper, {:resolve, make_ref()})
  end

  @tag :n1_causal_green
  test "explicit legacy context retains latest raw defaults without creating managed authority" do
    start_supervised!({AuthorizerBindings, managed: false})

    for key <- @keys do
      Application.delete_env(:symphony_elixir, key)
      assert AuthorizerBindings.resolve(key) == {:ok, nil}
      Application.put_env(:symphony_elixir, key, nil)
      assert AuthorizerBindings.resolve(key) == {:ok, nil}
      Application.put_env(:symphony_elixir, key, LegacyAuthorizer)
      assert AuthorizerBindings.resolve(key) == {:ok, LegacyAuthorizer}
    end

    assert {:error, :forbidden} = SymphonyControl.RuntimeIdentity.read(:invalid)
    assert {:ok, _} = SymphonyControl.RuntimeIdentity.read(:operator)
  end

  @tag :n1_causal_green
  test "unknown lifecycle metadata and unknown startup mode deny until explicit new lifecycle" do
    context = {AuthorizerBindings, :lifecycle}
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)

    for invalid <- [:absent, :malformed] do
      start_supervised!({AuthorizerBindings, owner: self()})
      assert {:ok, _} = AuthorizerBindings.install(self())
      if invalid == :absent, do: :persistent_term.erase(context), else: :persistent_term.put(context, invalid)
      assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
      stop_supervised!(AuthorizerBindings)
      start_supervised!({AuthorizerBindings, managed: false})
      assert AuthorizerBindings.resolve(:runtime_identity_authorizer) == {:ok, LegacyAuthorizer}
      stop_supervised!(AuthorizerBindings)
    end

    start_supervised!({AuthorizerBindings, managed: nil})
    assert {:error, :forbidden} = AuthorizerBindings.resolve(:runtime_identity_authorizer)
  end

  @tag :n1_causal_green
  test "a queued successful lookup from an ended incarnation cannot select its old grant" do
    owner = self()
    helper = start_supervised!({AuthorizerBindings, owner: owner})
    assert {:ok, _} = AuthorizerBindings.install(owner)
    :ok = :sys.suspend(helper)
    caller = Task.async(fn -> AuthorizerBindings.resolve(:project_authorizer) end)
    await_call!(helper, :resolve)
    :erlang.suspend_process(caller.pid)
    :ok = :sys.resume(helper)

    AuthDbFixture.await!(fn ->
      {:messages, messages} = Process.info(caller.pid, :messages)
      Enum.any?(messages, &match?({_, {:ok, :managed, {^helper, _, _, :active, _, _, _}}}, &1))
    end)

    stop_supervised!(AuthorizerBindings)
    start_supervised!({AuthorizerBindings, owner: owner})
    assert {:ok, _} = AuthorizerBindings.install(owner)
    :erlang.resume_process(caller.pid)
    assert Task.await(caller, 1000) == {:error, :forbidden}
  end

  @tag :n1_causal_green
  test "a dead supervisor owner cannot select an active binding ahead of its DOWN message" do
    owner = spawn(fn -> receive do: (:stop -> :ok) end)
    helper = start_supervised!({AuthorizerBindings, owner: owner}, restart: :temporary)
    assert {:ok, _} = AuthorizerBindings.install(owner)
    :ok = :sys.suspend(helper)
    caller = Task.async(fn -> AuthorizerBindings.resolve(:project_authorizer) end)
    await_call!(helper, :resolve)
    monitor = Process.monitor(owner)
    send(owner, :stop)
    assert_receive {:DOWN, ^monitor, :process, ^owner, :normal}, 1000
    :ok = :sys.resume(helper)
    assert Task.await(caller, 1000) == {:error, :forbidden}
    AuthDbFixture.await!(fn -> not Process.alive?(helper) end)
  end

  @tag :n1_causal_green
  test "normal owner shutdown preserves independent base updates inside and around teardown" do
    originals = [:error, {:ok, nil}, {:ok, __MODULE__}]
    mutations = [:foreign, :delete, nil, :authorizer, :original, :aba]

    for key <- @keys, original <- originals, mutation <- mutations, timing <- [:before, :during, :after] do
      restore(key, original)
      owner = spawn(fn -> receive do: (:stop -> :ok) end)
      assert {:ok, _} = AuthorizerBindings.install(owner)
      helper = Process.whereis(AuthorizerBindings)
      if timing == :during, do: :ok = :sys.suspend(helper)
      if timing == :before, do: write_base!(key, mutation, original)
      monitor = Process.monitor(owner)
      send(owner, :stop)
      assert_receive {:DOWN, ^monitor, :process, ^owner, :normal}, 1000

      if timing == :during do
        write_base!(key, mutation, original)
        :ok = :sys.resume(helper)
      end

      AuthDbFixture.await!(fn -> not Process.alive?(helper) end)
      if timing == :after, do: write_base!(key, mutation, original)
      result = expected(mutation, original)
      assert Application.fetch_env(:symphony_elixir, key) == result
      assert AuthorizerBindings.resolve(key) == {:ok, effective(result)}
    end
  end

  for key <- @keys, transition <- [:install, :inactive_aba] do
    @key key
    @transition transition
    @tag :n2
    test "N2 #{@key} queued inactive reply rejects #{@transition} in the same helper" do
      Application.put_env(:symphony_elixir, @key, LegacyAuthorizer)
      owner = self()
      helper = start_supervised!({AuthorizerBindings, owner: owner})
      assert {:ok, old_generation} = AuthorizerBindings.install(owner)
      assert :ok = AuthorizerBindings.release(old_generation)
      inactive = :sys.get_state(helper)
      {caller, started, deadline} = queued_selection!(helper, :base, fn -> consume(@key, :operator) end)

      try do
        assert {:ok, generation} = AuthorizerBindings.install(owner)
        active = :sys.get_state(helper)
        assert active.phase == :active
        refute generation == old_generation
        assert active.incarnation == inactive.incarnation
        refute active.revision == inactive.revision
        if @transition == :inactive_aba, do: assert(:ok == AuthorizerBindings.release(generation))
        current = :sys.get_state(helper)
        assert Process.whereis(AuthorizerBindings) == helper
        refute current.revision == inactive.revision
        :erlang.resume_process(caller.pid)
        assert_denied(consume_result(caller))
        assert System.monotonic_time(:millisecond) - started < 250
        assert RequestContext.timely?(deadline)
      after
        resume_if_alive(caller.pid)
      end
    end
  end

  for key <- @keys do
    @key key
    @tag :n2
    test "N2 #{@key} active release/install and writer handoff never reuse a decision" do
      owner = self()
      helper = start_supervised!({AuthorizerBindings, owner: owner})
      assert {:ok, generation} = AuthorizerBindings.install(owner)
      first = :sys.get_state(helper)
      assert {:ok, ^generation} = AuthorizerBindings.install(owner)
      assert :sys.get_state(helper).revision == first.revision
      assert AuthorizerBindings.resolve(@key) == {:ok, Authorizer}
      assert :sys.get_state(helper).revision == first.revision
      {caller, _, _} = queued_selection!(helper, :managed, fn -> AuthorizerBindings.resolve(@key) end)

      try do
        {writer, same_generation} = installing_writer(owner)
        assert same_generation == generation
        current = :sys.get_state(helper)
        assert current.writer == writer.pid
        refute current.revision == first.revision
        assert :ok = AuthorizerBindings.release(generation)
        assert :sys.get_state(helper).revision == current.revision
        :erlang.resume_process(caller.pid)
        assert consume_result(caller) == {:error, :forbidden}
        send(writer.pid, {:release, generation})
        assert Task.await(writer, 1000) == :ok
        assert {:ok, next_generation} = AuthorizerBindings.install(owner)
        refute next_generation == generation
        {caller2, _, _} = queued_selection!(helper, :managed, fn -> AuthorizerBindings.resolve(@key) end)

        try do
          assert :ok = AuthorizerBindings.release(next_generation)
          assert {:ok, final_generation} = AuthorizerBindings.install(owner)
          refute final_generation == next_generation
          :erlang.resume_process(caller2.pid)
          assert consume_result(caller2) == {:error, :forbidden}
        after
          resume_if_alive(caller2.pid)
        end
      after
        resume_if_alive(caller.pid)
      end
    end
  end

  @tag :n2
  test "N2 queued active reply rejects a dead writer before another install" do
    helper = start_supervised!({AuthorizerBindings, owner: self()})
    {writer, _generation} = installing_writer(self())
    operation = fn -> AuthorizerBindings.resolve(:runtime_identity_authorizer) end
    {caller, _, _} = queued_selection!(helper, :managed, operation)

    try do
      Task.shutdown(writer, :brutal_kill)
      refute Process.alive?(writer.pid)
      :erlang.resume_process(caller.pid)
      assert consume_result(caller) == {:error, :forbidden}
    after
      resume_if_alive(caller.pid)
    end
  end

  @tag :n2
  test "N2 delivered lookup result still expires at lookup250 before caller acceptance" do
    helper = start_supervised!({AuthorizerBindings, managed: false})
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)
    {caller, started, deadline} = queued_selection!(helper, :base, fn -> RuntimeIdentity.read(:operator) end)

    try do
      receive do: (:never_sent -> flunk("unexpected message")), after: (270 -> :ok)
      assert System.monotonic_time(:millisecond) - started >= 250
      assert RequestContext.timely?(deadline)
      :erlang.resume_process(caller.pid)
      assert consume_result(caller) == {:error, :forbidden}
    after
      resume_if_alive(caller.pid)
    end
  end

  defmodule HeldLegacy do
    def authorize(actor, :runtime_identity_read), do: hold(actor)
    def authorize(actor, _action, _scope), do: hold(actor)

    defp hold({owner, ref}) do
      send(owner, {:legacy_callback_started, ref, self()})
      receive do: ({:release_callback, ^ref} -> :ok), after: (1500 -> :deny)
    end
  end

  for key <- @keys, context <- [:inactive, :retired] do
    @key key
    @context context
    @tag :n2
    test "N2 #{@key} delayed legacy callback is fenced through #{@context} managed startup" do
      helper = start_supervised!({AuthorizerBindings, managed: false, owner: self()})
      if @context == :retired, do: stop_supervised!(AuthorizerBindings)
      Application.put_env(:symphony_elixir, @key, HeldLegacy)
      parent = self()
      ref = make_ref()
      caller = Task.async(fn -> consume(@key, {parent, ref}) end)
      assert_receive {:legacy_callback_started, ^ref, callback}, 250
      assert callback == caller.pid
      if @context == :retired, do: start_supervised!({AuthorizerBindings, owner: self()})
      assert {:ok, _} = AuthorizerBindings.install(self())
      if @context == :inactive, do: assert(Process.whereis(AuthorizerBindings) == helper)
      send(callback, {:release_callback, ref})
      assert_denied(consume_result(caller))
    end
  end

  @tag :n2
  test "N2 stable legacy callback retains its budget beyond lookup250 but not original HTTP deadline" do
    start_supervised!({AuthorizerBindings, managed: false})
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, HeldLegacy)
    parent = self()

    for expired <- [false, true] do
      ref = make_ref()
      lifetime = System.convert_time_unit(100, :millisecond, :native)
      deadline = if expired, do: System.monotonic_time() + lifetime, else: RequestContext.deadline()

      caller =
        Task.async(fn ->
          Process.put({Authorizer, :deadline}, deadline)
          RuntimeIdentity.read({parent, ref})
        end)

      assert_receive {:legacy_callback_started, ^ref, callback}, 250
      receive do: (:never_sent -> flunk("unexpected message")), after: (300 -> :ok)
      send(callback, {:release_callback, ref})
      result = consume_result(caller)
      if expired, do: assert(result == {:error, :forbidden}), else: assert(match?({:ok, %{schema_version: 1}}, result))
    end
  end

  for key <- @keys, context <- [:inactive, :retired] do
    @key key
    @context context
    @tag :n2
    test "N2 #{@key} raw candidate read precedes final guarded #{@context} selection" do
      helper = start_supervised!({AuthorizerBindings, managed: false, owner: self()})
      if @context == :retired, do: stop_supervised!(AuthorizerBindings)
      Application.put_env(:symphony_elixir, @key, LegacyAuthorizer)
      parent = self()
      ref = make_ref()
      started = System.monotonic_time(:millisecond)

      caller =
        Task.async(fn ->
          Process.put({Authorizer, :deadline}, RequestContext.deadline())
          {:ok, selection} = AuthorizerBindings.prepare(@key)
          {candidate, _, _, _} = selection
          send(parent, {:raw_candidate_read, ref, candidate})

          receive do
            {:accept_candidate, ^ref} ->
              AuthorizerBindings.authorize_selected(selection, consumer_arguments(@key, :operator))
          after
            200 -> :deny
          end
        end)

      assert_receive {:raw_candidate_read, ^ref, LegacyAuthorizer}, 200
      if @context == :retired, do: start_supervised!({AuthorizerBindings, owner: self()})
      assert {:ok, _} = AuthorizerBindings.install(self())
      if @context == :inactive, do: assert(Process.whereis(AuthorizerBindings) == helper)
      send(caller.pid, {:accept_candidate, ref})
      assert consume_result(caller) == :deny
      assert System.monotonic_time(:millisecond) - started < 250
    end
  end

  @tag :n2
  test "N2 unaccepted unknown or pending proof cannot authorize a legacy callback" do
    start_supervised!({AuthorizerBindings, owner: self(), managed: false})
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, LegacyAuthorizer)
    assert {:ok, selection} = AuthorizerBindings.prepare(:runtime_identity_authorizer)
    {module, decision, limit, deadline} = selection
    arguments = [:operator, :runtime_identity_read]
    assert :ok = AuthorizerBindings.authorize_selected(selection, arguments)

    for invalid <- [:unknown, put_elem(decision, 3, :pending), put_elem(decision, 2, make_ref())] do
      assert :deny = AuthorizerBindings.authorize_selected({module, invalid, limit, deadline}, arguments)
    end
  end

  @tag :n2
  test "N2 stale legacy callback cannot commit a project domain effect" do
    AuthDbFixture.start!()
    start_supervised!({AuthorizerBindings, owner: self(), managed: false})
    Application.put_env(:symphony_elixir, :project_authorizer, HeldLegacy)
    parent = self()
    ref = make_ref()

    caller =
      Task.async(fn ->
        Process.put({Authorizer, :deadline}, RequestContext.deadline())
        Projects.create_project({parent, ref}, %{key: "N2", name: "Must remain absent"})
      end)

    assert_receive {:legacy_callback_started, ^ref, callback}, 250
    assert {:ok, _} = AuthorizerBindings.install(self())
    send(callback, {:release_callback, ref})
    assert_denied(consume_result(caller))
    assert Repo.query!("SELECT count(*) FROM projects", [], log: false).rows == [[0]]
  end

  @tag :n2
  test "N2 fresh VM absent selection cannot survive a complete managed lifecycle" do
    script = ~S"""
    alias SymphonyControl.Auth.AuthorizerBindings
    alias SymphonyControl.RuntimeIdentity
    defmodule FreshVmLegacy do
      def authorize(:operator, :runtime_identity_read), do: :ok
      def authorize({parent, ref}, :runtime_identity_read) do
        send(parent, {:callback, self(), ref})
        receive do: ({:release, ^ref} -> :ok), after: (200 -> :deny)
      end
    end
    :absent = :persistent_term.get({AuthorizerBindings, :lifecycle}, :absent)
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, FreshVmLegacy)
    {:ok, %{schema_version: 1}} = RuntimeIdentity.read(:operator)
    parent = self()
    ref = make_ref()
    caller = Task.async(fn -> RuntimeIdentity.read({parent, ref}) end)
    receive do
      {:callback, callback, ^ref} ->
        {:ok, supervisor} = Supervisor.start_link([{AuthorizerBindings, owner: self()}], strategy: :one_for_one)
        {:ok, generation} = AuthorizerBindings.install(self())
        :ok = AuthorizerBindings.release(generation)
        :ok = Supervisor.stop(supervisor)
        {:legacy, revision} = :persistent_term.get({AuthorizerBindings, :lifecycle})
        true = is_reference(revision)
        send(callback, {:release, ref})
    after
      200 -> raise "fresh VM callback barrier was not reached"
    end
    {:error, :forbidden} = Task.await(caller, 1000)
    IO.puts("N2_FRESH_VM_ABSENT_GUARDED")
    """

    ebin = Application.app_dir(:symphony_elixir, "ebin")
    {output, exit} = System.cmd(System.find_executable("elixir"), ["-pa", ebin, "-e", script], stderr_to_stdout: true)
    assert exit == 0
    assert String.trim(output) == "N2_FRESH_VM_ABSENT_GUARDED"
  end

  defp consumer_arguments(:runtime_identity_authorizer, actor), do: [actor, :runtime_identity_read]
  defp consumer_arguments(:project_authorizer, actor), do: [actor, :project_read, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"]

  defp consume(:runtime_identity_authorizer, actor), do: RuntimeIdentity.read(actor)
  defp consume(:project_authorizer, actor), do: Projects.get_project(actor, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
  defp consume_result(caller), do: Task.await(caller, 1000)
  defp assert_denied({:error, :forbidden}), do: :ok
  defp assert_denied({:error, %{code: :forbidden}}), do: :ok
  defp assert_denied(_result), do: flunk("stale binding authorization escaped the consumer guard")

  defp queued_selection!(helper, mode, operation) do
    :ok = :sys.suspend(helper)
    deadline = RequestContext.deadline()
    started = System.monotonic_time(:millisecond)

    caller =
      Task.async(fn ->
        Process.put({Authorizer, :deadline}, deadline)
        operation.()
      end)

    await_call!(helper, :resolve)
    :erlang.suspend_process(caller.pid)
    :ok = :sys.resume(helper)

    AuthDbFixture.await!(
      fn ->
        {:messages, messages} = Process.info(caller.pid, :messages)
        Enum.any?(messages, &match?({_, {:ok, ^mode, {^helper, _, revision, _, _, _, _}}} when is_reference(revision), &1))
      end,
      100
    )

    {caller, started, deadline}
  end

  defp resume_if_alive(pid) do
    if Process.alive?(pid) do
      try do
        :erlang.resume_process(pid)
      rescue
        ArgumentError -> :ok
      end
    end
  end

  defp installing_writer(owner) do
    parent = self()

    task =
      Task.async(fn ->
        {:ok, generation} = AuthorizerBindings.install(owner)
        send(parent, {:installed_writer, self(), generation})
        writer_release(generation, parent)
      end)

    assert_receive {:installed_writer, pid, generation}, 1000
    assert pid == task.pid
    {task, generation}
  end

  defp writer_release(generation, parent) do
    receive do
      {:release, ^generation} ->
        AuthorizerBindings.release(generation)

      {:stale, stale} ->
        :ok = AuthorizerBindings.release(stale)
        send(parent, {:stale_released, self()})
        writer_release(generation, parent)
    after
      2000 -> raise "owned binding writer was not released"
    end
  end

  defp await_call!(helper, operation) do
    AuthDbFixture.await!(fn ->
      {:messages, messages} = Process.info(helper, :messages)

      Enum.any?(messages, fn
        {:"$gen_call", _, {^operation, _}} -> true
        _ -> false
      end)
    end)
  end

  defp write_base!(key, mutation, original) do
    task =
      Task.async(fn ->
        case mutation do
          :foreign ->
            Application.put_env(:symphony_elixir, key, ForeignModule)

          :delete ->
            Application.delete_env(:symphony_elixir, key)

          nil ->
            Application.put_env(:symphony_elixir, key, nil)

          :authorizer ->
            Application.put_env(:symphony_elixir, key, Authorizer)

          :original ->
            restore(key, original)

          :aba ->
            Application.put_env(:symphony_elixir, key, ForeignModule)
            Application.put_env(:symphony_elixir, key, Authorizer)
            Application.put_env(:symphony_elixir, key, ForeignModule)
        end
      end)

    assert Task.await(task, 1000) == :ok
  end

  defp expected(:foreign, _), do: {:ok, ForeignModule}
  defp expected(:delete, _), do: :error
  defp expected(nil, _), do: {:ok, nil}
  defp expected(:authorizer, _), do: {:ok, Authorizer}
  defp expected(:original, original), do: original
  defp expected(:aba, _), do: {:ok, ForeignModule}
  defp effective(:error), do: nil
  defp effective({:ok, value}), do: value

  defp trace_base_writes!(helper) do
    for function <- [:put_env, :delete_env, :put_all_env] do
      :erlang.trace_pattern({Application, function, :_}, true, [:local])
    end

    :erlang.trace(helper, true, [:call])
  end

  defp assert_no_base_writes!(helper) do
    marker = :erlang.trace_delivered(helper)
    assert_receive {:trace_delivered, ^helper, ^marker}, 1000
    calls = collect_calls(helper, [])

    refute Enum.any?(calls, fn
             {Application, _, [:symphony_elixir, key | _]} -> key in @keys
             {Application, :put_all_env, _} -> true
             _ -> false
           end),
           "binding lifecycle wrote operator defaults"

    :erlang.trace(helper, false, [:call])

    for function <- [:put_env, :delete_env, :put_all_env] do
      :erlang.trace_pattern({Application, function, :_}, false, [:local])
    end
  end

  defp collect_calls(helper, calls) do
    receive do
      {:trace, ^helper, :call, call} -> collect_calls(helper, [call | calls])
    after
      0 -> calls
    end
  end

  defp restore(key, :error), do: Application.delete_env(:symphony_elixir, key)
  defp restore(key, {:ok, value}), do: Application.put_env(:symphony_elixir, key, value)

  defmodule TimeBoundaryLegacy do
    def authorize(:operator, :runtime_identity_read), do: :ok
    def authorize(:operator, :project_create, :platform), do: :ok
  end

  for key <- @keys, context <- [:request, :absent] do
    @time_key key
    @time_context context
    @tag :r6_time
    test "R6-TIME #{@time_key} native closing samples follow complete state checks with #{@time_context} context" do
      if @time_key == :project_authorizer, do: AuthDbFixture.start!()
      start_supervised!({AuthorizerBindings, owner: self(), managed: false})
      Application.put_env(:symphony_elixir, @time_key, TimeBoundaryLegacy)
      descriptor = :persistent_term.get({AuthorizerBindings, :lifecycle})
      deadline = if @time_context == :request, do: RequestContext.deadline(), else: nil
      owner = self()
      ref = make_ref()
      started = System.monotonic_time()

      caller =
        Task.async(fn ->
          if deadline, do: Process.put({Authorizer, :deadline}, deadline)
          receive do: ({:time_run, ^ref} -> :ok)
          result = time_consume(@time_key)
          send(owner, {:time_result, ref, match?({:ok, _}, result)})
          receive do: ({:time_finish, ^ref} -> :ok), after: (1000 -> :ok)
        end)

      time_trace(caller.pid, true)
      send(caller.pid, {:time_run, ref})

      try do
        assert_receive {:time_result, ^ref, true}, 1000
        events = time_events(caller.pid)
        state_calls = time_indices(events, :state_call)
        state_returns = time_indices(events, :state_return)
        assert length(state_calls) == 2 and length(state_returns) == 2
        [{:time_call, lookup_limit, _} | _] = Enum.filter(events, &match?({:time_call, _, _}, &1))
        callback = hd(time_indices(events, :callback_return))
        time_assert_closing(events, hd(state_calls), hd(state_returns), callback, lookup_limit)

        if deadline do
          refute deadline == lookup_limit
          time_assert_closing(events, List.last(state_calls), List.last(state_returns), length(events), deadline)
        else
          refute Enum.any?(Enum.drop(events, List.last(state_calls)), &match?({:time_call, _, _}, &1))
        end

        assert :persistent_term.get({AuthorizerBindings, :lifecycle}) == descriptor
        elapsed = System.convert_time_unit(System.monotonic_time() - started, :native, :microsecond) / 1000
        IO.puts("R6_TIME_NATIVE key=#{@time_key} context=#{@time_context} elapsed_ms=#{elapsed} state_checks=2 closing_order=verified")
        send(caller.pid, {:time_finish, ref})
        assert Task.await(caller, 1000) == :ok
      after
        time_trace(caller.pid, false)
        if Process.alive?(caller.pid), do: Task.shutdown(caller, :brutal_kill)
      end
    end
  end

  for key <- @keys do
    @time_key key
    @tag :r6_time
    test "R6-TIME #{@time_key} request at or after its exact native bound denies before callback" do
      if @time_key == :project_authorizer, do: AuthDbFixture.start!()
      start_supervised!({AuthorizerBindings, owner: self(), managed: false})
      Application.put_env(:symphony_elixir, @time_key, TimeBoundaryLegacy)
      bound = System.monotonic_time()
      Process.put({Authorizer, :deadline}, bound)

      try do
        assert System.monotonic_time() >= bound
        assert_denied(time_consume(@time_key))
        if @time_key == :project_authorizer, do: assert(Repo.query!("SELECT count(*) FROM projects", [], log: false).rows == [[0]])
      after
        Process.delete({Authorizer, :deadline})
      end
    end
  end

  defp time_consume(:runtime_identity_authorizer), do: RuntimeIdentity.read(:operator)
  defp time_consume(:project_authorizer), do: Projects.create_project(:operator, %{key: "TIME", name: "Native time control"})

  defp time_trace(pid, enabled) do
    match = if enabled, do: [{:_, [], [{:return_trace}]}], else: false
    :erlang.trace_pattern({RequestContext, :timely?, 1}, match, [:local])
    :erlang.trace_pattern({AuthorizerBindings, :current?, 1}, match, [:local])
    :erlang.trace_pattern({TimeBoundaryLegacy, :authorize, :_}, match, [:local])
    if enabled, do: :erlang.trace(pid, true, [:call, :monotonic_timestamp, {:tracer, self()}])
  end

  defp time_events(pid) do
    ref = :erlang.trace_delivered(pid)
    time_collect(ref, [])
  end

  defp time_collect(ref, events) do
    receive do
      {:trace_delivered, _, ^ref} ->
        Enum.reverse(events)

      {:trace_ts, _, :call, {RequestContext, :timely?, [bound]}, at} ->
        time_collect(ref, [{:time_call, bound, at} | events])

      {:trace_ts, _, :return_from, {RequestContext, :timely?, 1}, true, at} ->
        time_collect(ref, [{:time_return, true, at} | events])

      {:trace_ts, _, :call, {AuthorizerBindings, :current?, _}, at} ->
        time_collect(ref, [{:state_call, true, at} | events])

      {:trace_ts, _, :return_from, {AuthorizerBindings, :current?, 1}, true, at} ->
        time_collect(ref, [{:state_return, true, at} | events])

      {:trace_ts, _, :return_from, {TimeBoundaryLegacy, :authorize, _}, :ok, at} ->
        time_collect(ref, [{:callback_return, true, at} | events])

      {:trace_ts, _, _, _, _} ->
        time_collect(ref, events)
    after
      1000 -> flunk("native time trace delivery not confirmed")
    end
  end

  defp time_indices(events, kind) do
    for {{tag, _, _}, index} <- Enum.with_index(events), tag == kind, do: index
  end

  defp time_assert_closing(events, call, returned, endpoint, bound) do
    preceding = Enum.take(events, call) |> Enum.filter(&match?({:time_call, _, _}, &1)) |> List.last()
    assert {:time_call, ^bound, _} = preceding
    closing = Enum.slice(events, returned + 1, max(endpoint - returned - 1, 0))
    assert [{:time_call, ^bound, sample}, {:time_return, true, _}] = closing
    {_, _, state_completed} = Enum.at(events, returned)
    assert state_completed <= sample
  end
end
