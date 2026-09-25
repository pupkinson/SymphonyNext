defmodule SymphonyControl.IdentityTest do
  use ExUnit.Case, async: false

  alias SymphonyControl.RuntimeIdentity

  defmodule TestAuthorizer do
    def authorize(:operator, :runtime_identity_read), do: :ok
    def authorize(:broken, :runtime_identity_read), do: raise("private detail")
    def authorize(:throwing, :runtime_identity_read), do: throw(:private_detail)
    def authorize(_, _), do: {:error, :forbidden}
  end

  setup do
    identity = Application.get_env(:symphony_elixir, :runtime_identity)
    authorizer = Application.get_env(:symphony_elixir, :runtime_identity_authorizer)
    Application.delete_env(:symphony_elixir, :runtime_identity)
    Application.delete_env(:symphony_elixir, :runtime_identity_authorizer)

    on_exit(fn ->
      restore(:runtime_identity, identity)
      restore(:runtime_identity_authorizer, authorizer)
    end)

    :ok
  end

  test "identity is denied by default, even for an actor claiming to be operator" do
    assert RuntimeIdentity.read(:operator) == {:error, :forbidden}
  end

  test "only the configured server authorization boundary can permit disclosure" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, TestAuthorizer)
    assert RuntimeIdentity.read(:visitor) == {:error, :forbidden}
    assert RuntimeIdentity.read(:broken) == {:error, :forbidden}
    assert RuntimeIdentity.read(:throwing) == {:error, :forbidden}

    assert {:ok, identity} = RuntimeIdentity.read(:operator)
    assert identity == %{schema_version: 1, commit_sha: "UNKNOWN", image_digest: "UNKNOWN", config_sha256: "UNKNOWN"}
  end

  test "accepted hashes are returned exactly while malformed fields remain unknown" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, TestAuthorizer)
    commit = String.duplicate("a", 40)
    image = "sha256:" <> String.duplicate("b", 64)
    config = String.duplicate("c", 64)
    hashes = [commit_sha: commit, image_digest: image, config_sha256: config]
    Application.put_env(:symphony_elixir, :runtime_identity, hashes)
    assert {:ok, %{commit_sha: ^commit, image_digest: ^image, config_sha256: ^config}} = RuntimeIdentity.read(:operator)

    invalid = [commit_sha: "main", image_digest: "latest", config_sha256: "secret"]
    Application.put_env(:symphony_elixir, :runtime_identity, invalid)
    assert {:ok, unknown} = RuntimeIdentity.read(:operator)
    expected = Map.new(invalid, fn {key, _} -> {key, "UNKNOWN"} end)
    assert Map.take(unknown, Map.keys(expected)) == expected
  end

  test "invalid authorization configuration fails closed" do
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, "module_from_request")
    assert RuntimeIdentity.read(:operator) == {:error, :forbidden}
  end

  test "HTTP disclosure uses the server actor assignment, not query parameters" do
    {:ok, _} = Application.ensure_all_started(:phoenix)
    Application.put_env(:symphony_elixir, :runtime_identity_authorizer, TestAuthorizer)
    router = SymphonyElixirWeb.Router
    denied = router.call(Plug.Test.conn(:get, "/api/v1/control/identity?current_actor=operator"), router.init([]))
    assert denied.status == 403

    conn = Plug.Test.conn(:get, "/api/v1/control/identity") |> Plug.Conn.assign(:current_actor, :operator)
    allowed = router.call(conn, router.init([]))
    assert allowed.status == 200
    assert Jason.decode!(allowed.resp_body)["commit_sha"] == "UNKNOWN"
  end

  defp restore(key, nil), do: Application.delete_env(:symphony_elixir, key)
  defp restore(key, value), do: Application.put_env(:symphony_elixir, key, value)
end
