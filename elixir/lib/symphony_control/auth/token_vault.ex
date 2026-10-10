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
  catch
    _, _ -> {:error, :dependency_unavailable}
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
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  def open(_cfg, _cipher, _aad), do: {:error, :invalid_request}

  defp decrypt(key, nonce, cipher, aad, tag) do
    :crypto.crypto_one_time_aead(:aes_256_gcm, key, nonce, cipher, aad, tag, false)
  end

  defp key(path) when is_binary(path) do
    with {:ok, %File.Stat{type: :regular}} <- File.lstat(path),
         {:ok, file} <- :file.open(path, [:read, :binary, :raw]) do
      # Raw descriptors belong to the guarded caller, not a background IO
      # server. Check the opened resource as well as the path. A trusted key
      # path must not be concurrently replaced; lstat alone is not a TOCTOU
      # guarantee and no arbitrary kernel IO realtime guarantee is claimed.
      try do
        with {:ok, info} <- :file.read_file_info(file),
             true <- elem(info, 2) == :regular,
             {:ok, value} when byte_size(value) == 32 <- :file.read(file, 33) do
          {:ok, value}
        else
          _ -> {:error, :dependency_unavailable}
        end
      after
        :file.close(file)
      end
    else
      _ -> {:error, :dependency_unavailable}
    end
  end

  defp key(_path), do: {:error, :dependency_unavailable}
end
