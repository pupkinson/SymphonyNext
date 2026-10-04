defmodule SymphonyElixirWeb.ControlHealthController do
  @moduledoc """
  Minimal health responses and deny-by-default control identity readback.
  """

  use Phoenix.Controller, formats: [:json]

  alias SymphonyControl.{Health, RuntimeIdentity}

  @spec live(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def live(conn, _params) do
    live = Health.live?()
    conn |> put_status(status(live)) |> json(%{live: live})
  end

  @spec ready(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def ready(conn, _params) do
    readiness = Health.readiness()
    conn |> put_status(status(readiness.ready)) |> json(readiness)
  end

  @spec identity(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def identity(conn, _params) do
    case RuntimeIdentity.read(Map.get(conn.assigns, :current_actor)) do
      {:ok, identity} -> json(conn, identity)
      {:error, :forbidden} -> conn |> put_status(:forbidden) |> json(%{error: "forbidden"})
    end
  end

  defp status(true), do: :ok
  defp status(false), do: :service_unavailable
end
