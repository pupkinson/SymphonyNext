defmodule SymphonyControl.Auth.Validity do
  @moduledoc "Ephemeral server-private validity carried from a checked read to its consumer decision."
  alias SymphonyControl.Auth.{Clock, Config, Oidc, RequestContext}
  defstruct [:kind, :config, :binding, :deadline, :clock, :bounds, :key_id]
  @type t :: %__MODULE__{}

  @spec key_id(Config.t()) :: binary() | nil
  def key_id(%Config{session_key_ref: path}) do
    with {:ok, link_info} <- :file.read_link_info(path, [:raw]),
         true <- elem(link_info, 2) == :regular,
         {:ok, file} <- :file.open(path, [:read, :binary, :raw]) do
      # Non-following metadata and descriptor checks retain the trusted-path
      # contract. Raw metadata avoids an unrelated VM file-server queue.
      # No background IO server owns a stalled descriptor. Path replacement
      # during open and arbitrary kernel IO realtime remain outside that contract.
      try do
        with {:ok, info} <- :file.read_file_info(file),
             true <- elem(info, 2) == :regular,
             {:ok, key} when byte_size(key) == 32 <- :file.read(file, 33) do
          :crypto.hash(:sha256, key)
        else
          _ -> nil
        end
      after
        :file.close(file)
      end
    else
      _ -> nil
    end
  end

  @spec local(map(), Clock.t(), Config.t(), term(), integer(), binary() | nil) :: t()
  def local(bounds, clock, cfg, actor, deadline, key_id) do
    %__MODULE__{
      kind: :local,
      config: cfg,
      binding: actor,
      deadline: deadline,
      clock: clock,
      bounds: bounds,
      key_id: key_id
    }
  end

  @spec signed(map(), Clock.t(), Config.t(), term(), integer()) :: t()
  def signed(claims, clock, cfg, selector, deadline),
    do: %__MODULE__{kind: :signed, config: cfg, binding: {claims.jti, selector}, deadline: deadline, clock: clock, bounds: claims}

  @spec current?(term(), Config.t(), term(), integer()) :: boolean()
  def current?(witness, cfg, binding, deadline), do: current?(witness, cfg, binding, deadline, nil)

  @spec current?(term(), Config.t(), term(), integer(), Clock.t() | nil) :: boolean()
  def current?(%__MODULE__{config: cfg, binding: binding, deadline: deadline} = witness, cfg, binding, deadline, fresh) do
    clock = fresh || witness.clock
    # Key I/O precedes the last native decision. Neither it nor a queued Clock
    # reply is allowed to renew the measured sample or original request.
    key_valid = key_current?(witness, cfg)
    now = System.monotonic_time()

    key_valid and request_current?(deadline) and clocks_current?(witness.clock, clock, now) and
      within?(witness.kind, witness.bounds, witness.clock, now) and within?(witness.kind, witness.bounds, clock, now)
  rescue
    _ -> false
  end

  def current?(_, _, _, _, _), do: false

  defp key_current?(%{kind: :local, key_id: key}, cfg), do: is_binary(key) and key_id(cfg) == key
  defp key_current?(_, _), do: true
  defp request_current?(deadline), do: is_integer(deadline) and RequestContext.timely?(deadline)

  defp clocks_current?(original, fresh, now) do
    clock?(original, now) and clock?(fresh, now) and fresh.epoch == original.epoch and
      fresh.native_clock == original.native_clock and fresh.utc_ms >= original.utc_ms and
      fresh.monotonic_ms >= original.monotonic_ms
  end

  defp within?(:local, bounds, clock, now) do
    expiry = min(bounds.expiry, bounds.credential_expiry)
    life = min(expiry - clock.utc_ms, expiry - bounds.issued - (clock.monotonic_ms - bounds.mono))

    clock.epoch == bounds.epoch and clock.utc_ms >= bounds.issued and clock.monotonic_ms >= bounds.mono and
      now < clock.native_anchor + native(life)
  end

  defp within?(:signed, claims, clock, now) do
    elapsed = now - clock.native_anchor
    # Compare native deltas to exact millisecond claim bounds. No floor of
    # current UTC, equality tolerance, or extension for delivery latency.
    Oidc.logout_current?(claims, clock.utc_ms) and
      elapsed < native(claims.expires_ms - clock.utc_ms) and
      elapsed <= native(claims.issued_ms + 300_000 - clock.utc_ms)
  end

  defp clock?(%{sample_valid: true, utc_ms: utc, monotonic_ms: mono, epoch: epoch, native_anchor: anchor, native_unit: unit, native_clock: producer}, now) do
    is_integer(utc) and is_integer(mono) and is_binary(epoch) and is_integer(anchor) and anchor <= now and
      unit == System.convert_time_unit(1, :second, :native) and is_pid(producer) and producer == Process.whereis(Clock)
  end

  defp clock?(_, _), do: false
  defp native(ms), do: System.convert_time_unit(ms, :millisecond, :native)
end
