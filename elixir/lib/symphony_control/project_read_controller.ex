defmodule SymphonyControl.ProjectReadController do
  @moduledoc """
  Read-only project representation for trusted server-assigned actors.

  This component does not authenticate requests. Missing actors are denied
  before domain access; project authorization remains owned by Projects.
  """

  import Phoenix.Controller, only: [json: 2]
  import Plug.Conn, only: [put_resp_header: 3, put_status: 2]

  alias SymphonyControl.{Error, Projects}

  @read_statuses %{
    invalid_input: :bad_request,
    forbidden: :forbidden,
    not_found: :not_found,
    dependency_unavailable: :service_unavailable
  }

  @spec show(Plug.Conn.t(), map()) :: Plug.Conn.t()
  def show(conn, %{"id" => id}) do
    conn = put_resp_header(conn, "cache-control", "no-store")

    case Map.get(conn.assigns, :current_actor) do
      nil -> error(conn, :forbidden)
      actor -> read(conn, actor, id)
    end
  end

  defp read(conn, actor, id) do
    case Projects.get_project(actor, id) do
      {:ok, project} ->
        json(conn, %{
          schema_version: 1,
          project: %{
            id: project.id,
            key: project.key,
            name: project.name,
            lock_version: project.lock_version,
            inserted_at: DateTime.to_iso8601(project.inserted_at),
            updated_at: DateTime.to_iso8601(project.updated_at)
          }
        })

      {:error, %Error{code: code}} ->
        error(conn, code)
    end
  end

  defp error(conn, code) do
    conn |> put_status(Map.fetch!(@read_statuses, code)) |> json(%{error: Atom.to_string(code)})
  end
end
