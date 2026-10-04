defmodule SymphonyControl.Router do
  @moduledoc """
  Read-only control component routes, independent of the agent dashboard.

  No authentication middleware or client-supplied actor is installed here.
  Identity and project reads use server authorization boundaries and default to deny.
  """

  use Plug.Router

  alias SymphonyControl.ProjectReadController
  alias SymphonyElixirWeb.ControlHealthController

  @known_paths [["health", "live"], ["health", "ready"], ["api", "v1", "control", "identity"]]

  plug(:match)
  plug(:dispatch)

  get "/health/live" do
    ControlHealthController.live(conn, %{})
  end

  get "/health/ready" do
    ControlHealthController.ready(conn, %{})
  end

  get "/api/v1/control/identity" do
    ControlHealthController.identity(conn, %{})
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
      |> put_status(:method_not_allowed)
      |> Phoenix.Controller.json(%{error: "method_not_allowed"})
    else
      conn |> put_status(:not_found) |> Phoenix.Controller.json(%{error: "not_found"})
    end
  end
end
