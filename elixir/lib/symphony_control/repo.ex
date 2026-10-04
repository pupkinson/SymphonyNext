defmodule SymphonyControl.Repo do
  @moduledoc """
  PostgreSQL repository for the native control and tracker domains.

  The repository receives dedicated connection settings from its supervisor.
  It never creates databases or migrates automatically.
  """

  use Ecto.Repo,
    otp_app: :symphony_elixir,
    adapter: Ecto.Adapters.Postgres
end
