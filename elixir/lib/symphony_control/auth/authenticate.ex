defmodule SymphonyControl.Auth.Authenticate do
  @moduledoc "Only a cookie and server confirmation can assign the current actor."
  @behaviour Plug
  import Plug.Conn
  alias SymphonyControl.Auth.{Access, Clock, Config, HttpBody, RequestContext}

  @impl true
  @spec init(keyword()) :: keyword()
  def init(opts), do: opts

  @impl true
  @spec call(Plug.Conn.t(), keyword()) :: Plug.Conn.t()
  def call(conn, _opts) do
    conn = assign(conn, :current_actor, nil)

    if protected?(conn) do
      authenticate(conn, conn.private[:control_auth], RequestContext.deadline())
    else
      conn
    end
  end

  defp authenticate(conn, cfg, deadline) do
    case HttpBody.read(conn, deadline) do
      {:ok, latest} ->
        confirm(fetch_cookies(latest), cfg, deadline)

      {:error, reason, latest} ->
        status = if reason == :invalid_request, do: 400, else: 503
        code = if status == 400, do: "invalid_request", else: "dependency_unavailable"
        latest |> put_resp_header("cache-control", "no-store") |> put_status(status) |> Phoenix.Controller.json(%{error: code}) |> halt()
    end
  end

  defp confirm(conn, %Config{} = cfg, deadline) do
    case Access.authenticate(cfg, conn.req_cookies["__Host-symphony-control"], Clock.now(RequestContext.remaining(deadline)), deadline) do
      {:ok, actor} -> assign(conn, :current_actor, actor)
      {:error, :dependency_unavailable} -> conn |> put_resp_header("cache-control", "no-store") |> put_status(503) |> Phoenix.Controller.json(%{error: "dependency_unavailable"}) |> halt()
      _ -> conn
    end
  catch
    _, _ -> conn
  end

  defp confirm(conn, _cfg, _deadline), do: conn

  defp protected?(%{method: "GET", path_info: ["api", "v1", "projects", _]}), do: true
  defp protected?(%{method: "GET", path_info: ["api", "v1", "control", "identity"]}), do: true
  defp protected?(_), do: false
end
