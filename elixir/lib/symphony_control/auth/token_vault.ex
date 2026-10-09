defmodule SymphonyControl.Auth.TokenVault do
  @moduledoc "OTP AES-256-GCM envelope v1: version(1), nonce(12), tag(16), ciphertext. No plaintext fallback."
  alias SymphonyControl.Auth.Config
  @type result :: {:ok, binary()} | {:error, Config.reason()}

  @spec seal(Config.t(), binary(), binary()) :: result()
  def seal(%Config{} = cfg, plaintext, aad) when is_binary(plaintext) and is_binary(aad) do
    with {:ok, key} <- key(cfg.session_key_ref) do
      nonce = :crypto.strong_rand_bytes(12)
      {cipher, tag} = :crypto.crypto_one_time_aead(:aes_256_gcm, key, nonce, plaintext, aad, 16, true)
      {:ok, <<1, nonce::binary, tag::binary, cipher::binary>>}
    end
  end

  def seal(_cfg, _plain, _aad), do: {:error, :invalid_request}

  @spec open(Config.t(), binary(), binary()) :: result()
  def open(%Config{} = cfg, envelope, aad) when is_binary(envelope) and is_binary(aad) do
    with {:ok, key} <- key(cfg.session_key_ref),
         <<1, nonce::binary-size(12), tag::binary-size(16), cipher::binary>> <- envelope,
         plaintext when is_binary(plaintext) <- decrypt(key, nonce, cipher, aad, tag) do
      {:ok, plaintext}
    else
      {:error, :dependency_unavailable} = error -> error
      _ -> {:error, :forbidden}
    end
  end

  def open(_cfg, _cipher, _aad), do: {:error, :invalid_request}

  defp decrypt(key, nonce, cipher, aad, tag) do
    :crypto.crypto_one_time_aead(:aes_256_gcm, key, nonce, cipher, aad, tag, false)
  end

  defp key(path) when is_binary(path) do
    case File.open(path, [:read, :binary]) do
      {:ok, file} ->
        try do
          case IO.binread(file, 33) do
            value when is_binary(value) and byte_size(value) == 32 -> {:ok, value}
            _ -> {:error, :dependency_unavailable}
          end
        after
          File.close(file)
        end

      _ ->
        {:error, :dependency_unavailable}
    end
  end

  defp key(_path), do: {:error, :dependency_unavailable}
end
