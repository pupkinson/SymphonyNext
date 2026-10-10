defmodule SymphonyControl.Auth.Actor do
  @moduledoc "Local session candidate. This value carries no permissions or IdP freshness authority."
  @enforce_keys [:session_id, :local_user_id, :issuer, :subject, :config_generation, :boot_epoch]
  defstruct @enforce_keys

  @type t :: %__MODULE__{
          # These bindings must be rechecked against current local state.
          session_id: Ecto.UUID.t(),
          local_user_id: Ecto.UUID.t(),
          issuer: binary(),
          subject: binary(),
          config_generation: binary(),
          boot_epoch: binary()
        }
end
