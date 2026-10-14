defmodule SymphonyControl.Auth.AuthorizerBindingsTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, AuthorizerBindings, RequestContext}
  alias SymphonyControl.AuthDbFixture
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

    for key <- @keys, original <- [:error, {:ok, nil}, {:ok, __MODULE__}], mutation <- [:foreign, :delete, nil, :authorizer, :original, :aba], timing <- [:before, :during, :after] do
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
    assert AuthorizerBindings.resolve(:project_authorizer) == {:ok, Application.get_env(:symphony_elixir, :project_authorizer)}
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
      Enum.any?(messages, &match?({_, {:ok, :managed}}, &1))
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
    for key <- @keys, original <- [:error, {:ok, nil}, {:ok, __MODULE__}], mutation <- [:foreign, :delete, nil, :authorizer, :original, :aba], timing <- [:before, :during, :after] do
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
    for function <- [:put_env, :delete_env, :put_all_env], do: :erlang.trace_pattern({Application, function, :_}, true, [:local])
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
    for function <- [:put_env, :delete_env, :put_all_env], do: :erlang.trace_pattern({Application, function, :_}, false, [:local])
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
end
