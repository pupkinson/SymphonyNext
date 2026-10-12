defmodule SymphonyControl.Auth.Controller do
  @moduledoc "Bounded fixed auth responses; logout remains denied until Task4."
  import Plug.Conn
  alias SymphonyControl.Auth.{Clock, Config, Login, RateLimiter}
  @browser "__Host-symphony-browser"
  @session "__Host-symphony-control"
  @cookie [secure: true, http_only: true, same_site: "Lax", path: "/"]

  @spec login(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def login(conn, _params) do
    with {:ok, conn} <- prepare(conn, :login),
         {:ok, result} <- Login.begin(conn.private.control_auth, conn.req_cookies[@browser], Clock.now()) do
      conn |> put_resp_cookie(@browser, result.browser_handle, @cookie) |> redirect(result.location)
    else
      {:error, reason} -> error(conn, reason)
    end
  catch
    _, _ -> error(conn, :dependency_unavailable)
  end

  @spec callback(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def callback(conn, _params) do
    with {:ok, conn} <- prepare(conn, :callback),
         conn = fetch_query_params(conn),
         {:ok, handle} <- Login.finish(conn.private.control_auth, conn.query_params["code"], conn.query_params["state"], conn.req_cookies[@browser], conn.req_cookies[@session], Clock.now()) do
      conn |> put_resp_cookie(@session, handle, @cookie) |> redirect("/")
    else
      {:error, reason} -> error(conn, reason)
    end
  catch
    _, _ -> error(conn, :dependency_unavailable)
  end

  @spec logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def logout(conn, _params), do: deny(conn, :callback)

  @spec backchannel_logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def backchannel_logout(conn, _params), do: deny(conn, :backchannel)

  defp deny(conn, kind) do
    case prepare(conn, kind) do
      {:ok, conn} -> error(conn, :forbidden)
      {:error, reason} -> error(conn, reason)
    end
  catch
    _, _ -> error(conn, :dependency_unavailable)
  end

  defp prepare(conn, kind) do
    with %Config{} <- conn.private[:control_auth],
         true <- conn.scheme == :https,
         {:ok, _body, conn} <- read_body(conn, length: 32_768, read_length: 32_769, read_timeout: 500),
         conn = fetch_cookies(conn),
         :ok <- RateLimiter.check(kind, conn.req_cookies[@browser]) do
      {:ok, conn}
    else
      {:more, _, _} -> {:error, :invalid_request}
      {:error, reason} -> {:error, reason}
      _ -> {:error, :forbidden}
    end
  end

  defp redirect(conn, location), do: conn |> put_resp_header("cache-control", "no-store") |> put_resp_header("location", location) |> send_resp(303, "")

  defp error(conn, reason) do
    {status, code} =
      case reason do
        :invalid_request -> {400, "invalid_request"}
        :rate_limited -> {429, "rate_limited"}
        reason when reason in [:dependency_unavailable, :unknown_outcome] -> {503, "dependency_unavailable"}
        _ -> {403, "forbidden"}
      end

    conn |> put_resp_header("cache-control", "no-store") |> put_status(status) |> Phoenix.Controller.json(%{error: code})
  end
end
