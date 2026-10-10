defmodule SymphonyControl.Auth.VaultTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Config, TokenVault}

  setup do
    path = Path.join(System.fetch_env!("SN005_TEST_KEY_ROOT"), "vault-" <> Ecto.UUID.generate())
    File.write!(path, :crypto.strong_rand_bytes(32))
    File.chmod!(path, 0o600)
    on_exit(fn -> File.rm(path) end)
    %{cfg: %Config{generation: "g1", session_key_ref: path}}
  end

  test "authenticated versioned envelope uses fresh nonce and no plaintext", %{cfg: cfg} do
    plain = "synthetic-vault-canary"
    assert {:ok, a} = TokenVault.seal(cfg, plain, "flow-id:g1")
    assert {:ok, b} = TokenVault.seal(cfg, plain, "flow-id:g1")
    refute a == b
    refute :binary.match(a, plain) != :nomatch
    assert <<1, _nonce::binary-size(12), _tag::binary-size(16), _cipher::binary>> = a
    assert {:ok, ^plain} = TokenVault.open(cfg, a, "flow-id:g1")
  end

  test "wrong AAD/key/tamper/missing/malformed key fail closed", %{cfg: cfg} do
    assert {:ok, envelope} = TokenVault.seal(cfg, "private", "session:g1")
    assert {:error, :forbidden} = TokenVault.open(cfg, envelope, "session:g2")
    <<head, rest::binary>> = envelope

    for bad <- [<<0, rest::binary>>, <<head, rest::binary, 1>>, <<>>, "invalid"] do
      assert {:error, :forbidden} = TokenVault.open(cfg, bad, "session:g1")
    end

    File.write!(cfg.session_key_ref, :crypto.strong_rand_bytes(32))
    assert {:error, :forbidden} = TokenVault.open(cfg, envelope, "session:g1")
    File.write!(cfg.session_key_ref, "short")
    assert {:error, :dependency_unavailable} = TokenVault.open(cfg, envelope, "session:g1")
    File.rm!(cfg.session_key_ref)
    assert {:error, :dependency_unavailable} = TokenVault.seal(cfg, "private", "session:g1")
    assert {:error, :dependency_unavailable} = TokenVault.open(cfg, envelope, "session:g1")
    assert {:error, :invalid_request} = TokenVault.seal(nil, nil, nil)
    assert {:error, :invalid_request} = TokenVault.open(nil, nil, nil)
    assert {:error, :dependency_unavailable} = TokenVault.seal(%Config{}, "private", "AAD")
  end

  @tag :repair_regression
  test "F5 public Vault sanitizes an actual unavailable crypto module exception", %{cfg: cfg} do
    assert {:ok, cipher} = TokenVault.seal(cfg, "synthetic-exception-canary", "AAD")
    crypto_dir = :code.which(:crypto) |> List.to_string() |> Path.dirname() |> String.to_charlist()

    log =
      ExUnit.CaptureLog.capture_log(fn ->
        # Only this owned VM's load path changes, for the duration of two calls.
        # The installed module/binary is never changed or replaced by a mock.
        true = :code.del_path(crypto_dir)
        true = :code.delete(:crypto)
        :code.purge(:crypto)

        try do
          assert projected(fn -> TokenVault.seal(cfg, "synthetic-exception-canary", "AAD") end) == {:error, :dependency_unavailable}
          assert projected(fn -> TokenVault.open(cfg, cipher, "AAD") end) == {:error, :dependency_unavailable}
        after
          true = :code.add_patha(crypto_dir)
          {:module, :crypto} = :code.load_file(:crypto)
        end
      end)

    refute String.contains?(log, "synthetic-exception-canary")
    assert {:ok, _} = TokenVault.open(cfg, cipher, "AAD")
  end

  defp projected(operation) do
    operation.()
  rescue
    _ -> :escaped_exception
  catch
    _, _ -> :escaped_exit
  end
end
