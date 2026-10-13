defmodule SymphonyControl.Auth.Controller do
  @moduledoc "Bounded browser login, session-bound CSRF and confirmed logout responses."
  import Plug.Conn
  alias SymphonyControl.Auth.{Access, Clock, Config, Csrf, HttpBody, Login, Logout, RateLimiter, RequestContext, Store}
  @browser "__Host-symphony-browser"
  @session "__Host-symphony-control"
  @csrf "__Host-symphony-csrf"
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
        {:ok, handle} -> finish_callback(latest, handle, deadline)
        failure -> failure
      end
    end)
  end

  @spec logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def logout(conn, _params) do
    run(conn, :callback, fn latest, deadline ->
      cfg = latest.private.control_auth

      with [origin] <- get_req_header(latest, "origin"),
           true <- origin == cfg.public_https_origin,
           [token] <- get_req_header(latest, "x-csrf-token"),
           true <- RequestContext.remaining(deadline) >= 1_000,
           clock = Clock.now(250),
           true <- RequestContext.remaining(deadline) >= 750,
           {:ok, actor} <- Store.local_actor(cfg, latest.req_cookies[@session], clock),
           :ok <- Csrf.verify(cfg, actor, token, deadline) do
        local_result(clear_auth_cookies(latest), cfg, actor, clock, deadline)
      else
        {:error, :dependency_unavailable} = error -> error
        _ -> {:error, :forbidden}
      end
    end)
  end

  defp local_result(response, cfg, actor, clock, deadline) do
    case Logout.local(cfg, actor, clock, deadline) do
      :ok -> {:ok, response, Logout.location(cfg)}
      {:error, reason} -> {:error, reason, response}
    end
  end

  @spec backchannel_logout(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def backchannel_logout(conn, _params) do
    run(conn, :backchannel, fn latest, deadline ->
      with {:ok, jwt} <- logout_form(latest),
           :ok <- Logout.backchannel(latest.private.control_auth, jwt, Clock.now(RequestContext.remaining(deadline)), deadline) do
        {:ok, latest}
      else
        {:error, reason} -> {:error, reason}
      end
    end)
  end

  defp finish_callback(latest, handle, deadline) do
    cfg = latest.private.control_auth
    response = put_resp_cookie(latest, @session, handle, @cookie)

    if Access.task4?(cfg, deadline) do
      with true <- RequestContext.remaining(deadline) >= 1_000,
           clock = Clock.now(250),
           true <- RequestContext.remaining(deadline) >= 750,
           {:ok, actor} <- Store.local_actor(cfg, handle, clock),
           {:ok, token} <- Csrf.issue(cfg, actor, deadline) do
        response = put_resp_cookie(response, @csrf, token, secure: true, http_only: false, same_site: "Strict", path: "/")
        {:ok, response, "/"}
      else
        _ -> {:error, :dependency_unavailable}
      end
    else
      {:ok, response, "/"}
    end
  end

  defp clear_auth_cookies(conn), do: conn |> delete_resp_cookie(@session, @cookie) |> delete_resp_cookie(@csrf, secure: true, same_site: "Strict", path: "/")

  defp logout_form(conn) do
    with [content_type] <- get_req_header(conn, "content-type"),
         true <- content_type |> String.split(";", parts: 2) |> hd() |> String.trim() |> String.downcase() == "application/x-www-form-urlencoded",
         body = conn.private.control_auth_body,
         true <- String.valid?(body),
         tokens = for({"logout_token", value} <- URI.query_decoder(body), do: value),
         [jwt] <- tokens,
         true <- byte_size(jwt) in 1..16_384 do
      {:ok, jwt}
    else
      _ -> {:error, :forbidden}
    end
  end

  defp run(conn, kind, operation) do
    deadline = conn.private[:control_deadline] || RequestContext.deadline()

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
  defp respond(_latest, _deadline, {:error, reason, response}), do: error(response, reason)

  defp respond(latest, deadline, {:ok, response}) do
    if RequestContext.timely?(deadline), do: response |> put_resp_header("cache-control", "no-store") |> send_resp(200, ""), else: error(latest, :dependency_unavailable)
  end

  defp prepare(%{scheme: :https, private: %{control_auth: %Config{}}} = conn, kind, deadline) do
    case HttpBody.read_payload(conn, deadline) do
      {:ok, body, latest} -> charge(latest |> put_private(:control_auth_body, body) |> fetch_cookies(), kind, deadline)
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
