defmodule SymphonyControl.Auth.AuthorizerBindingsTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authorizer, AuthorizerBindings}
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
    assert Application.get_env(:symphony_elixir, :project_authorizer) == Authorizer
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

  defp restore(key, :error), do: Application.delete_env(:symphony_elixir, key)
  defp restore(key, {:ok, value}), do: Application.put_env(:symphony_elixir, key, value)
end
