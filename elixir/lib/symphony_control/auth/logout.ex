defmodule SymphonyControl.Auth.Logout do
  @moduledoc "Confirmed local and signed back-channel effects; RP logout is a user-agent handoff."
  alias SymphonyControl.Auth.{Actor, Clock, Config, Eligibility, Oidc, RequestContext, Store}

  @spec local(Config.t(), Actor.t(), Clock.t()) :: :ok | {:error, Config.reason()}
  def local(cfg, actor, clock), do: local(cfg, actor, clock, RequestContext.deadline())

  @spec local(Config.t(), Actor.t(), Clock.t(), integer()) :: :ok | {:error, Config.reason()}
  def local(cfg, actor, clock, deadline) do
    with true <- RequestContext.remaining(deadline) >= 750,
         {:ok, %{actor: ^actor}} <- Store.session_material(cfg, actor, clock),
         true <- RequestContext.remaining(deadline) >= 1_000,
         fresh = Clock.now(250),
         true <- RequestContext.remaining(deadline) >= 750,
         :ok <- Store.revoke(cfg, {:session, actor.session_id}, fresh),
         :ok <- Eligibility.invalidate(cfg, {:session, actor.session_id}, RequestContext.milliseconds(deadline)),
         true <- RequestContext.timely?(deadline) do
      :ok
    else
      {:error, reason} -> {:error, reason}
      _ -> {:error, :dependency_unavailable}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @spec backchannel(Config.t(), binary(), Clock.t()) :: :ok | {:error, Config.reason()}
  def backchannel(cfg, jwt, clock), do: backchannel(cfg, jwt, clock, RequestContext.deadline())

  @spec backchannel(Config.t(), binary(), Clock.t(), integer()) :: :ok | {:error, Config.reason()}
  def backchannel(cfg, jwt, _clock, deadline) do
    with {:ok, verified} <- Oidc.verify_logout(cfg, jwt, RequestContext.milliseconds(deadline)),
         true <- RequestContext.remaining(deadline) >= 1_000,
         fresh = Clock.now(250),
         true <- Oidc.logout_current?(verified, fresh.utc_ms),
         selector = selector(cfg, verified),
         true <- RequestContext.remaining(deadline) >= 750,
         :ok <- Store.accept_logout(cfg, verified.jti, selector, fresh.utc_ms + 3_605_000, fresh),
         :ok <- Eligibility.invalidate(cfg, selector, RequestContext.milliseconds(deadline)),
         true <- Oidc.logout_current?(verified, System.system_time(:millisecond)) and RequestContext.timely?(deadline) do
      :ok
    else
      {:error, reason} -> {:error, reason}
      _ -> {:error, :forbidden}
    end
  rescue
    _ -> {:error, :forbidden}
  catch
    _, _ -> {:error, :dependency_unavailable}
  end

  @spec location(Config.t()) :: binary()
  def location(%Config{} = cfg),
    do: cfg.end_session_url <> "?" <> URI.encode_query(%{"client_id" => cfg.client_id, "post_logout_redirect_uri" => cfg.post_logout_uri})

  defp selector(cfg, %{sid: nil, sub: sub}), do: {:subject, cfg.issuer, sub}
  defp selector(cfg, %{sid: sid, sub: sub}), do: {:sid, cfg.issuer, sid, sub}
end
