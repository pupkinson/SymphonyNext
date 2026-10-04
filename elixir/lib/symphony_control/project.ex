defmodule SymphonyControl.Project do
  @moduledoc """
  Persisted project identity root from the existing initial migration.

  The domain owns UUID, revision and timestamps. Memberships and execution
  bindings are separate work, not fields admitted through this schema.
  """

  use Ecto.Schema

  @primary_key {:id, :binary_id, autogenerate: false}

  schema "projects" do
    field(:key, :string)
    field(:name, :string)
    field(:lock_version, :integer, default: 1)
    timestamps(type: :utc_datetime_usec)
  end

  @type t :: %__MODULE__{
          id: Ecto.UUID.t(),
          key: String.t(),
          name: String.t(),
          lock_version: pos_integer(),
          inserted_at: DateTime.t(),
          updated_at: DateTime.t()
        }
end
