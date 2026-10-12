defmodule SymphonyControl.Auth.HttpBody do
  @moduledoc "Narrow bounded auth framing for pinned Bandit: HTTP1 no-body or single Content-Length."
  import Plug.Conn
  alias Bandit.HTTP2.Errors
  alias Bandit.HTTP2.Errors.StreamError
  alias SymphonyControl.Auth.RequestContext
  @limit 32_768

  @spec read(Plug.Conn.t(), integer()) :: {:ok, Plug.Conn.t()} | {:error, atom(), Plug.Conn.t()}
  def read(conn, deadline) do
    # HTTP2 has a different drain/send-window contract. Bandit's existing
    # pipeline resets it without entering the body reader or response sender.
    require_http1!(conn)

    if protocol(conn) in [:"HTTP/1.0", :"HTTP/1.1"] do
      case framing(conn) do
        {:ok, length} -> read_remaining(conn, length, 0, deadline)
        :error -> {:error, :invalid_request, close(conn)}
      end
    else
      {:error, :dependency_unavailable, close(conn)}
    end
  end

  @spec require_http1!(Plug.Conn.t()) :: :ok
  def require_http1!(conn) do
    if protocol(conn) == :"HTTP/2" do
      {_, adapter} = conn.adapter

      raise StreamError,
        message: "Unsupported auth transport",
        error_code: Errors.refused_stream(),
        stream_id: adapter.transport.stream_id
    end

    :ok
  end

  defp protocol(%{adapter: {module, payload}}) do
    if function_exported?(module, :get_http_protocol, 1), do: module.get_http_protocol(payload), else: :unknown
  end

  @spec close(Plug.Conn.t()) :: Plug.Conn.t()
  def close(conn), do: put_resp_header(conn, "connection", "close")

  defp framing(conn) do
    case {get_req_header(conn, "transfer-encoding"), get_req_header(conn, "content-length")} do
      {[], []} -> {:ok, 0}
      {[], [value]} -> content_length(value)
      _ -> :error
    end
  end

  defp content_length(value) do
    if String.match?(value, ~r/\A[0-9]+\z/) do
      case Integer.parse(value) do
        {length, ""} when length <= @limit -> {:ok, length}
        _ -> :error
      end
    else
      :error
    end
  end

  defp read_remaining(conn, expected, received, deadline) do
    budget = RequestContext.remaining(deadline)

    if budget > 0 do
      # Matching length/read_length makes each CL read one bounded recv.
      size = min(max(expected - received, 1), 1024)
      read_chunk(conn, expected, received, deadline, size, min(budget, 500))
    else
      {:error, :dependency_unavailable, close(conn)}
    end
  end

  defp read_chunk(conn, expected, received, deadline, size, timeout) do
    case read_body(conn, length: size, read_length: size, read_timeout: timeout) do
      {:ok, body, latest} ->
        complete(latest, expected, received + byte_size(body), deadline)

      {:more, body, latest} ->
        total = received + byte_size(body)

        if total < expected and total <= @limit and byte_size(body) > 0 do
          read_remaining(latest, expected, total, deadline)
        else
          {:error, :invalid_request, close(latest)}
        end

      {:error, _} ->
        {:error, :dependency_unavailable, close(conn)}
    end
  catch
    _, _ -> {:error, :dependency_unavailable, close(conn)}
  end

  defp complete(latest, expected, total, deadline) do
    if total == expected and total <= @limit and RequestContext.timely?(deadline),
      do: {:ok, latest},
      else: {:error, :invalid_request, close(latest)}
  end
end
