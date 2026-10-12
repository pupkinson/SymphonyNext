defmodule SymphonyControl.Auth.Routes do
  @moduledoc "Validate exact configured auth paths before a listener or Router accepts them."
  alias SymphonyControl.Auth.Config
  @reserved ["/", "/auth/login", "/auth/logout", "/health/live", "/health/ready", "/api/v1/control/identity"]

  @spec validate(Config.t()) :: :ok | {:error, :invalid_auth_routes}
  def validate(%Config{} = cfg) do
    callback = path(cfg.callback_uri)
    backchannel = path(cfg.backchannel_uri)

    if admitted?(callback) and admitted?(backchannel) and callback != backchannel and path(cfg.post_logout_uri) == "/",
      do: :ok,
      else: {:error, :invalid_auth_routes}
  end

  defp path(uri) when is_binary(uri), do: URI.parse(uri).path
  defp path(_), do: nil

  defp admitted?("/" <> _ = path) do
    segments = String.split(path, "/", trim: true)
    canonical = "/" <> Enum.join(segments, "/")
    actual = path == canonical and URI.decode(path) == path and not Enum.any?(segments, &(&1 in [".", ".."]))
    protected = match?(["api", "v1", "projects", _], segments)
    actual and path not in @reserved and not protected
  end

  defp admitted?(_), do: false
end
