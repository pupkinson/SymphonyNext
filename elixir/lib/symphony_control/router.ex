defmodule SymphonyControl.Router do
  @moduledoc """
  Read-only control component routes, independent of the agent dashboard.

  Authentication clears client assignments and uses only a server-confirmed cookie.
  Identity and project reads retain their separate authorization boundaries and default to deny.
  """

  use Plug.Router

  alias SymphonyControl.Auth.{Authenticate, Config, Controller}
  alias SymphonyControl.ProjectReadController
  alias SymphonyElixirWeb.ControlHealthController

  @known_paths [["health", "live"], ["health", "ready"], ["api", "v1", "control", "identity"]]

  @impl true
  def call(conn, opts) do
    cfg = trusted_config(Keyword.get(opts, :auth))
    conn = conn |> put_resp_header("cache-control", "no-store") |> put_private(:control_auth, cfg) |> Authenticate.call(Authenticate.init([]))
    route = Map.get(auth_paths(cfg), conn.request_path)

    cond do
      conn.halted -> conn
      is_nil(route) -> super(conn, opts)
      true -> auth_route(conn, route)
    end
  end

  defp trusted_config(%Config{} = cfg) do
    case cfg |> Map.from_struct() |> Map.delete(:tls_cacerts) |> Config.load() do
      {:ok, _} -> cfg
      _ -> nil
    end
  end

  defp trusted_config(_), do: nil

  defp auth_paths(cfg) do
    callback = if match?(%Config{}, cfg), do: URI.parse(cfg.callback_uri).path, else: "/auth/callback"
    backchannel = if match?(%Config{}, cfg), do: URI.parse(cfg.backchannel_uri).path, else: "/auth/backchannel-logout"
    %{"/auth/login" => {"GET", :login}, callback => {"GET", :callback}, "/auth/logout" => {"POST", :logout}, backchannel => {"POST", :backchannel_logout}}
  end

  defp auth_route(conn, {method, handler}) do
    if conn.method == method do
      apply(Controller, handler, [conn, %{}])
    else
      conn |> put_resp_header("allow", method) |> put_resp_header("cache-control", "no-store") |> put_status(:method_not_allowed) |> Phoenix.Controller.json(%{error: "method_not_allowed"})
    end
  end

  plug(:match)
  plug(:dispatch)

  get "/health/live" do
    ControlHealthController.live(conn, %{})
  end

  get "/health/ready" do
    ControlHealthController.ready(conn, %{})
  end

  get "/api/v1/control/identity" do
    if is_nil(conn.assigns[:current_actor]) do
      conn |> put_status(:forbidden) |> Phoenix.Controller.json(%{error: "forbidden"})
    else
      ControlHealthController.identity(conn, %{})
    end
  end

  get "/api/v1/projects/:id" do
    ProjectReadController.show(conn, %{"id" => id})
  end

  match "/api/v1/projects/:id" do
    conn
    |> put_resp_header("allow", "GET")
    |> put_resp_header("cache-control", "no-store")
    |> put_status(:method_not_allowed)
    |> Phoenix.Controller.json(%{error: "method_not_allowed"})
  end

  match _ do
    if conn.path_info in @known_paths do
      conn
      |> put_resp_header("allow", "GET")
      |> put_resp_header("cache-control", "no-store")
      |> put_status(:method_not_allowed)
      |> Phoenix.Controller.json(%{error: "method_not_allowed"})
    else
      conn |> put_resp_header("cache-control", "no-store") |> put_status(:not_found) |> Phoenix.Controller.json(%{error: "not_found"})
    end
  end
end
