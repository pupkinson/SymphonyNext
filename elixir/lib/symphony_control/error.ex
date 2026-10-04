defmodule SymphonyControl.Error do
  @moduledoc """
  Safe domain errors, without submitted values, SQL or driver exceptions.

  An `unknown_outcome` reference is a project UUID for state readback. It is
  neither an operation receipt nor permission to retry an unconfirmed write.
  """

  @enforce_keys [:code]
  defstruct [:code, :reference_id, fields: []]

  @type code :: :invalid_input | :forbidden | :not_found | :conflict | :dependency_unavailable | :unknown_outcome
  @type t :: %__MODULE__{code: code(), fields: [atom()], reference_id: Ecto.UUID.t() | nil}
end
