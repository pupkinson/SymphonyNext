defmodule SymphonyControl.Auth.Csrf do
  @moduledoc "A separate random anti-CSRF token signed by Plug and bound to the exact local session."
  alias Plug.Crypto.{KeyGenerator, MessageVerifier}
  alias SymphonyControl.Auth.{Access, Actor, Config, RequestContext}

  @spec issue(Config.t(), Actor.t(), integer()) :: {:ok, binary()} | {:error, Config.reason()}
  def issue(cfg, actor, deadline) do
    GenServer.call(Access, {:csrf, cfg, actor, :issue}, RequestContext.remaining(deadline))
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @spec verify(Config.t(), Actor.t(), term(), integer()) :: :ok | {:error, Config.reason()}
  def verify(cfg, actor, token, deadline) do
    GenServer.call(Access, {:csrf, cfg, actor, {:verify, token}}, RequestContext.remaining(deadline))
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @doc "Internal signing operation inside the owning Access process; no session identifier enters the token."
  @spec perform(term(), term(), binary()) :: {:ok, binary()} | :ok | {:error, Config.reason()}
  def perform(%Actor{} = actor, operation, secret) do
    if binding?(actor) do
      salt = :erlang.term_to_binary({:sn005_csrf_v1, actor})
      key = KeyGenerator.generate(secret, salt, cache: nil)
      signed(operation, key)
    else
      {:error, :forbidden}
    end
  catch
    _, _ -> {:error, :forbidden}
  end

  def perform(_, _, _), do: {:error, :forbidden}

  defp signed(:issue, key), do: {:ok, MessageVerifier.sign(:crypto.strong_rand_bytes(32), key)}

  defp signed({:verify, token}, key) when is_binary(token) and byte_size(token) <= 256 do
    case MessageVerifier.verify(token, key) do
      {:ok, nonce} when byte_size(nonce) == 32 -> :ok
      _ -> {:error, :forbidden}
    end
  end

  defp signed(_, _), do: {:error, :forbidden}

  defp binding?(actor) do
    match?({:ok, _}, Ecto.UUID.cast(actor.session_id)) and match?({:ok, _}, Ecto.UUID.cast(actor.local_user_id)) and
      Enum.all?([actor.issuer, actor.subject, actor.config_generation, actor.boot_epoch], &(is_binary(&1) and byte_size(&1) in 1..4096))
  end
end
