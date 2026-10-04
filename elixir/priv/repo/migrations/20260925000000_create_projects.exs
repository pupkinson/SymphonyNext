defmodule SymphonyControl.Repo.Migrations.CreateProjects do
  use Ecto.Migration

  @spec change() :: term()
  def change do
    create table(:projects, primary_key: false) do
      add :id, :binary_id, primary_key: true
      add :key, :text, null: false
      add :name, :text, null: false
      add :lock_version, :integer, default: 1, null: false
      timestamps(type: :utc_datetime_usec)
    end

    create unique_index(:projects, [:key])
    create constraint(:projects, :projects_key_not_blank, check: "length(btrim(key)) > 0")
    create constraint(:projects, :projects_name_not_blank, check: "length(btrim(name)) > 0")
    create constraint(:projects, :projects_lock_version_positive, check: "lock_version > 0")
  end
end
