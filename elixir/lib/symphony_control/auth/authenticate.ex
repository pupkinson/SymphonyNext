defmodule SymphonyControl.Auth.Authenticate do
  @moduledoc "Only a cookie and server confirmation can assign the current actor."
  @behaviour Plug
  import Plug.Conn
  alias SymphonyControl.Auth.{Access, Clock, Config}

  @impl true
  @spec init(keyword()) :: keyword()
  def init(opts), do: opts

  @impl true
  @spec call(Plug.Conn.t(), keyword()) :: Plug.Conn.t()
  def call(conn, _opts) do
    conn = conn |> assign(:current_actor, nil) |> fetch_cookies()

    if protected?(conn) do
      authenticate(conn, conn.private[:control_auth])
    else
      conn
    end
  end

  defp authenticate(conn, %Config{} = cfg) do
    case Access.authenticate(cfg, conn.req_cookies["__Host-symphony-control"], Clock.now()) do
      {:ok, actor} -> assign(conn, :current_actor, actor)
      {:error, :dependency_unavailable} -> conn |> put_resp_header("cache-control", "no-store") |> put_status(503) |> Phoenix.Controller.json(%{error: "dependency_unavailable"}) |> halt()
      _ -> conn
    end
  catch
    _, _ -> conn
  end

  defp authenticate(conn, _), do: conn
  defp protected?(%{method: "GET", path_info: ["api", "v1", "projects", _]}), do: true
  defp protected?(%{method: "GET", path_info: ["api", "v1", "control", "identity"]}), do: true
  defp protected?(_), do: false
end
