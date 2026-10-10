# Mix prunes optional OTP paths. Use the existing prepared debugger only in this
# ExUnit VM so the real timeout/cleanup boundary can be held without a Task mock.
[debugger_ebin] = Path.wildcard(Path.join([List.to_string(:code.root_dir()), "lib", "debugger-*", "ebin"]))
true = :code.add_pathz(String.to_charlist(debugger_ebin))
Code.ensure_loaded!(:int)

defmodule SymphonyControl.AuthDbFixture do
  @moduledoc false
  alias SymphonyControl.Auth.Config
  alias SymphonyControl.Repo
  alias SymphonyControl.Repo.Migrations.{CreateControlAuth, CreateProjects}

  # The fresh-clock source belongs to this fixture/VM, never to runtime config.
  defmodule SnapshotClock do
    use GenServer
    def start_link(agent), do: GenServer.start_link(__MODULE__, agent, name: SymphonyControl.Auth.Clock)
    @impl true
    def init(agent), do: {:ok, %{agent: agent, hold: nil, sample_patch: %{}}}
    @impl true
    def handle_call({:hold, target, owner, ref}, _from, state), do: {:reply, :ok, %{state | hold: {target, owner, ref}}}

    def handle_call({:sample_patch, patch}, _from, state), do: {:reply, :ok, %{state | sample_patch: patch}}

    def handle_call(:now, {caller, _tag} = from, state) do
      # Freeze the actual measured response BEFORE either delivery barrier.
      sample = state.agent |> SymphonyControl.AuthDbFixture.sample_clock() |> Map.put(:native_clock, self()) |> Map.merge(state.sample_patch)
      measured = System.monotonic_time()

      case state.hold do
        {^caller, owner, ref} ->
          send(owner, {:clock_reply_held, ref, from, self()})
          send(owner, {:clock_sample_measured, ref, from, self(), sample, measured})

          receive do
            {:release_clock, ^ref} -> :ok
          after
            1800 -> :ok
          end

        _ ->
          :ok
      end

      {:reply, sample, state}
    end
  end

  def start!(opts \\ []) do
    {:ok, _} = Application.ensure_all_started(:ecto_sql)
    schema = "sn005_" <> Base.encode16(:crypto.strong_rand_bytes(8), case: :lower)

    repo = [
      socket_dir: System.fetch_env!("SN005_TEST_PG_SOCKET"),
      port: String.to_integer(System.fetch_env!("SN005_TEST_PG_PORT")),
      username: System.fetch_env!("SN005_TEST_PG_USER"),
      database: System.fetch_env!("SN005_TEST_PG_DB"),
      pool_size: 4,
      parameters: [search_path: schema],
      log: false
    ]

    ExUnit.Callbacks.start_supervised!({SymphonyControl.Application, enabled: true, repo: repo})
    Repo.query!("CREATE SCHEMA #{schema}", [], log: false)
    key = Path.join(System.fetch_env!("SN005_TEST_KEY_ROOT"), schema)
    File.write!(key, :crypto.strong_rand_bytes(32))
    File.chmod!(key, 0o600)
    ExUnit.Callbacks.on_exit(fn -> File.rm(key) end)
    cfg = %Config{issuer: "https://fixture.example.invalid/issuer", generation: "generation-1", session_key_ref: key}
    epoch = :crypto.strong_rand_bytes(32)
    initial_clock = %{utc_ms: 1_800_000_000_000, monotonic_ms: 1000, epoch: epoch, sample_valid: true}
    {:ok, agent} = Agent.start_link(fn -> initial_clock end)
    ExUnit.Callbacks.start_supervised!({SnapshotClock, agent})
    f = %{config: cfg, schema: schema, repo: repo, clock_agent: agent}
    if Keyword.get(opts, :migrate, true), do: migrate!(f)
    f
  end

  def migrate!(f) do
    paths = Application.app_dir(:symphony_elixir, "priv/repo/migrations")
    modules = [{20_260_925_000_000, CreateProjects}, {20_261_004_000_000, CreateControlAuth}]

    for {_version, module} <- modules do
      file = migration_file(module)
      Code.require_file(Path.join(paths, file))
    end

    Ecto.Migrator.run(Repo, modules, :up, all: true, prefix: f.schema, log: false)
  end

  def migrate_legacy!(f) do
    paths = Application.app_dir(:symphony_elixir, "priv/repo/migrations")
    Code.require_file(Path.join(paths, migration_file(CreateProjects)))
    Ecto.Migrator.run(Repo, [{20_260_925_000_000, CreateProjects}], :up, all: true, prefix: f.schema, log: false)
  end

  defp migration_file(CreateProjects), do: "20260925000000_create_projects.exs"
  defp migration_file(CreateControlAuth), do: "20261004000000_create_control_auth.exs"

  def clock(f), do: sample_clock(f.clock_agent)

  # Static legacy clocks use a logical ms axis anchored at each measurement;
  # the new delay controls use an explicit 1:1 native -> logical ms mapping.
  # No arbitrary logical monotonic epoch is compared to the VM native axis.
  def sample_clock(agent) do
    Agent.get(agent, fn model ->
      native = System.monotonic_time()
      unit = System.convert_time_unit(1, :second, :native)

      case model do
        {:ticking, base, origin} ->
          elapsed = System.convert_time_unit(native - origin, :native, :millisecond)
          anchor = origin + System.convert_time_unit(elapsed, :millisecond, :native)

          Map.merge(base, %{
            utc_ms: base.utc_ms + elapsed,
            monotonic_ms: base.monotonic_ms + elapsed,
            native_anchor: anchor,
            native_unit: unit,
            native_clock: Process.whereis(SymphonyControl.Auth.Clock)
          })

        clock ->
          Map.merge(clock, %{native_anchor: native, native_unit: unit, native_clock: Process.whereis(SymphonyControl.Auth.Clock)})
      end
    end)
  end

  def ticking_clock!(f) do
    base = clock(f)
    origin = System.monotonic_time()
    Agent.update(f.clock_agent, fn _ -> {:ticking, base, origin} end)
    {base, origin}
  end

  def patch_clock_sample!(patch), do: GenServer.call(SymphonyControl.Auth.Clock, {:sample_patch, patch})
  def set_clock!(f, clock), do: Agent.update(f.clock_agent, fn _ -> clock end)

  def hold_clock_reply!(target) do
    ref = make_ref()
    :ok = GenServer.call(SymphonyControl.Auth.Clock, {:hold, target, self(), ref})
    ref
  end

  def advance!(f, ms), do: Agent.update(f.clock_agent, &%{&1 | utc_ms: &1.utc_ms + ms, monotonic_ms: &1.monotonic_ms + ms})

  def restart_control!(f) do
    ExUnit.Callbacks.stop_supervised!(SymphonyControl.Application)
    ExUnit.Callbacks.start_supervised!({SymphonyControl.Application, enabled: true, repo: f.repo})
    Repo.query!("SELECT 1", [], timeout: 1_000, log: false)
    Agent.update(f.clock_agent, &%{&1 | epoch: :crypto.strong_rand_bytes(32), monotonic_ms: 0})
  end

  def seed_user!(f, opts \\ []) do
    id = Ecto.UUID.generate()
    Repo.query!("INSERT INTO control_auth_users(id,active) VALUES($1,$2)", [uuid(id), Keyword.get(opts, :active, true)], log: false)

    Repo.query!(
      "INSERT INTO control_auth_identities(id,user_id,issuer,subject) VALUES($1,$2,$3,$4)",
      [Ecto.UUID.bingenerate(), uuid(id), Keyword.get(opts, :issuer, f.config.issuer), Keyword.get(opts, :subject, "known")],
      log: false
    )

    id
  end

  def seed_project! do
    id = Ecto.UUID.generate()

    Repo.query!(
      "INSERT INTO projects(id,key,name,inserted_at,updated_at) VALUES($1,$2,'Fixture',now(),now())",
      [uuid(id), id],
      log: false
    )

    id
  end

  def seed_membership!(_f, user, project, roles) do
    Repo.query!(
      "INSERT INTO control_auth_memberships(id,user_id,project_id,roles,revision) VALUES($1,$2,$3,$4,1)",
      [Ecto.UUID.bingenerate(), uuid(user), uuid(project), Enum.map(roles, &Atom.to_string/1)],
      log: false
    )

    :ok
  end

  def identity(f, opts \\ []) do
    Map.merge(
      %{issuer: f.config.issuer, subject: "known", sid: "sid-1", credential_expires_at_ms: clock(f).utc_ms + 3_600_000, tokens: %{"access_token" => "synthetic-token"}},
      Map.new(opts)
    )
  end

  def flow(f, opts \\ []) do
    state = Base.url_encode64(:crypto.strong_rand_bytes(32), padding: false)
    Map.merge(%{state: state, nonce: "synthetic-nonce", verifier: "synthetic-verifier", issued_ms: clock(f).utc_ms}, Map.new(opts))
  end

  def uuid(id), do: Ecto.UUID.dump!(id)

  # Ecto telemetry is synchronous after the actual query/COMMIT result. No SQL
  # parameters or secret payloads enter the coordination messages.
  def barrier!(needle) do
    ref = make_ref()
    id = {:auth_query_barrier, ref}
    :ok = :telemetry.attach(id, [:symphony_control, :repo, :query], &__MODULE__.query_barrier/4, {self(), ref, needle})
    ExUnit.Callbacks.on_exit(fn -> :telemetry.detach(id) end)
    ref
  end

  def query_barrier(_event, _measurements, metadata, {owner, ref, needle}) do
    if String.contains?(String.upcase(metadata.query), String.upcase(needle)) and not Process.get(ref, false) do
      Process.put(ref, true)
      monitor = Process.monitor(owner)
      send(owner, {:query_result_held, ref, self()})

      receive do
        {:release_query, ^ref} -> :ok
        {:DOWN, ^monitor, :process, ^owner, _} -> :ok
      after
        1800 -> send(owner, {:barrier_abandoned, ref})
      end

      Process.demonitor(monitor, [:flush])
    end
  end

  def await!(condition, timeout \\ 1200) do
    await_until!(condition, System.monotonic_time(:millisecond) + timeout)
  end

  def hold_task_shutdown!(f) do
    # OTP's interpreter executes the existing Task bytecode's abstract forms;
    # this is a VM-local breakpoint, not a replacement Task implementation.
    {:ok, {Task, [abstract_code: {:raw_abstract_v1, forms}]}} = :beam_lib.chunks(:code.which(Task), [:abstract_code])
    [debugger_ebin] = Path.wildcard(Path.join([List.to_string(:code.root_dir()), "lib", "debugger-*", "ebin"]))
    true = :code.add_pathz(String.to_charlist(debugger_ebin))
    path = Path.join(System.fetch_env!("SN005_TEST_KEY_ROOT"), f.schema <> "-Elixir.Task.erl")
    File.write!(path, ["%% coding: latin-1\n", Enum.map(forms, &:erl_pp.form/1)])
    {:module, Task} = :int.i(String.to_charlist(path))
    ref = make_ref()
    :ok = :int.auto_attach([:break], {__MODULE__, :shutdown_break, [self(), ref]})
    :ok = :int.break_in(Task, :shutdown, 2)

    ExUnit.Callbacks.on_exit(fn ->
      :int.no_break(Task)
      :int.auto_attach(false)
      :int.n(Task)
      :code.del_path(String.to_charlist(debugger_ebin))
      File.rm(path)
    end)

    ref
  end

  def shutdown_break(pid, owner, ref) do
    send(owner, {:shutdown_held, ref, pid, self()})

    receive do
      {:continue_shutdown, ^ref} -> :int.continue(pid)
    after
      1800 -> :int.continue(pid)
    end
  end

  defp await_until!(condition, deadline) do
    cond do
      condition.() ->
        :ok

      System.monotonic_time(:millisecond) >= deadline ->
        raise "owned fixture barrier timed out"

      true ->
        Process.sleep(2)
        await_until!(condition, deadline)
    end
  end
end
