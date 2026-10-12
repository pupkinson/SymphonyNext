defmodule SymphonyControl.Auth.Controller do
  @moduledoc "Bounded fixed auth responses; logout remains denied until Task4."
  import Plug.Conn
  alias SymphonyControl.Auth.{Clock, Config, HttpBody, Login, RateLimiter, RequestContext}
  @browser "__Host-symphony-browser"
  @session "__Host-symphony-control"
  @cookie [secure: true, http_only: true, same_site: "Lax", path: "/"]

  @spec login(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def login(conn, _params) do
    run(conn, :login, fn latest, deadline ->
      case Login.begin(latest.private.control_auth, latest.private.control_browser, Clock.now(RequestContext.remaining(deadline)), deadline) do
        {:ok, result} -> {:ok, put_resp_cookie(latest, @browser, result.browser_handle, @cookie), result.location}
        failure -> failure
      end
    end)
  end

  @spec callback(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def callback(conn, _params) do
    run(conn, :callback, fn latest, deadline ->
      latest = fetch_query_params(latest)

      case Login.finish(
             latest.private.control_auth,
             latest.query_params["code"],
             latest.query_params["state"],
             latest.req_cookies[@browser],
             latest.req_cookies[@session],
             Clock.now(RequestContext.remaining(deadline)),
             deadline
           ) do
        {:ok, handle} -> {:ok, put_resp_cookie(latest, @session, handle, @cookie), "/"}
        failure -> failure
      end
    end)
  end

  @spec logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def logout(conn, _params), do: deny(conn, :callback)

  @spec backchannel_logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def backchannel_logout(conn, _params), do: deny(conn, :backchannel)

  defp deny(conn, kind) do
    run(conn, kind, fn _, _ -> {:error, :forbidden} end)
  end

  defp run(conn, kind, operation) do
    deadline = RequestContext.deadline()

    case prepare(conn, kind, deadline) do
      {:ok, latest} ->
        respond(latest, deadline, safely(fn -> operation.(latest, deadline) end))

      {:error, reason, latest} ->
        error(latest, reason)
    end
  end

  defp respond(latest, deadline, {:ok, response, location}) do
    if RequestContext.timely?(deadline), do: redirect(response, location), else: error(latest, :dependency_unavailable)
  end

  defp respond(latest, _deadline, {:error, reason}), do: error(latest, reason)

  defp prepare(%{scheme: :https, private: %{control_auth: %Config{}}} = conn, kind, deadline) do
    case HttpBody.read(conn, deadline) do
      {:ok, latest} -> charge(fetch_cookies(latest), kind, deadline)
      failure -> failure
    end
  end

  defp prepare(conn, _kind, _deadline), do: {:error, :forbidden, HttpBody.close(conn)}

  defp charge(latest, kind, deadline) do
    with {:ok, browser} <- browser_binding(kind, latest.req_cookies[@browser]),
         :ok <- RateLimiter.check(kind, browser, deadline) do
      {:ok, put_private(latest, :control_browser, browser)}
    else
      {:error, reason} -> {:error, reason, latest}
    end
  end

  defp browser_binding(:login, value), do: Login.browser_binding(value)
  defp browser_binding(_, value), do: {:ok, value}

  defp safely(operation) do
    operation.()
  catch
    _, _ -> {:error, :dependency_unavailable}
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
