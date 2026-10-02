defmodule SymphonyControl.Tracker.TaskRef do
  @moduledoc """
  Stable local task reference with a versioned tracker attachment.

  Rebinding preserves id, project and source object. Generation is a strictly
  increasing project attachment epoch, including replacement of binding_id.
  These are pure candidate values: persistence, authoritative scope, admission,
  transactional compare-and-swap and global active-owner exclusion are external.
  A successful rebind does not grant permission or prove drain/commit occurred.
  """
  alias SymphonyControl.Tracker.ObjectIdentity

  @enforce_keys [:id, :project_id, :object, :binding_id, :generation]
  @derive {Inspect, only: [:generation]}
  defstruct [:id, :project_id, :object, :binding_id, :generation]

  @opaque t :: %__MODULE__{
            id: String.t(),
            project_id: String.t(),
            object: ObjectIdentity.t(),
            binding_id: String.t(),
            generation: pos_integer()
          }
  @type result :: {:ok, t()} | {:error, :invalid_task_ref | :conflict}
  @uuid ~r/\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\z/

  @spec new(term(), term(), term(), term(), term()) :: result()
  def new(id, project_id, object, binding_id, generation)
      when is_integer(generation) and generation > 0 do
    with {:ok, id} <- uuid(id),
         {:ok, project_id} <- uuid(project_id),
         {:ok, object} <- canonical_object(object),
         {:ok, binding_id} <- uuid(binding_id) do
      {:ok,
       %__MODULE__{
         id: id,
         project_id: project_id,
         object: object,
         binding_id: binding_id,
         generation: generation
       }}
    else
      _invalid -> {:error, :invalid_task_ref}
    end
  end

  def new(_id, _project, _object, _binding, _generation), do: {:error, :invalid_task_ref}

  @spec rebind(term(), term(), term(), term()) :: result()
  def rebind(%__MODULE__{} = current, expected_generation, binding_id, next_generation)
      when is_integer(expected_generation) and expected_generation > 0 and
             is_integer(next_generation) and next_generation > 0 do
    with {:ok, ^current} <-
           new(
             current.id,
             current.project_id,
             current.object,
             current.binding_id,
             current.generation
           ),
         {:ok, binding_id} <- uuid(binding_id) do
      if current.generation == expected_generation and next_generation > expected_generation do
        {:ok, %{current | binding_id: binding_id, generation: next_generation}}
      else
        {:error, :conflict}
      end
    else
      _invalid -> {:error, :invalid_task_ref}
    end
  end

  def rebind(_current, _expected, _binding, _next), do: {:error, :invalid_task_ref}

  @spec key(t()) :: {String.t(), ObjectIdentity.identity_key()}
  def key(%__MODULE__{project_id: project_id, object: object}) do
    {project_id, ObjectIdentity.key(object)}
  end

  @spec ownership_key(t()) :: ObjectIdentity.identity_key()
  def ownership_key(%__MODULE__{object: object}), do: ObjectIdentity.key(object)

  @spec snapshot(t()) :: map()
  def snapshot(%__MODULE__{} = ref) do
    %{
      task_ref_id: ref.id,
      project_id: ref.project_id,
      object_key: ownership_key(ref),
      binding_id: ref.binding_id,
      generation: ref.generation
    }
  end

  @spec current?(term(), term()) :: boolean()
  def current?(%__MODULE__{} = ref, pin) when is_map(pin) do
    with {:ok, ^ref} <- new(ref.id, ref.project_id, ref.object, ref.binding_id, ref.generation) do
      snapshot(ref) === pin
    else
      _invalid -> false
    end
  end

  def current?(_ref, _pin), do: false

  defp canonical_object(%ObjectIdentity{provider: :native, namespace: ns, object_id: id}) do
    ObjectIdentity.native(ns, id)
  end

  defp canonical_object(%ObjectIdentity{provider: :linear, namespace: ns, object_id: id}) do
    ObjectIdentity.linear(ns, id)
  end

  defp canonical_object(%ObjectIdentity{
         provider: :github,
         namespace: "github.com",
         object_id: id
       }) do
    ObjectIdentity.github(id)
  end

  defp canonical_object(_object), do: :error

  defp uuid(value) when is_binary(value) and byte_size(value) == 36 do
    if Regex.match?(@uuid, value), do: {:ok, String.downcase(value)}, else: :error
  end

  defp uuid(_value), do: :error
end
