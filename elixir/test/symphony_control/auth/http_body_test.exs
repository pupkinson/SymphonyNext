defmodule SymphonyControl.Auth.HttpBodyTest do
  use ExUnit.Case, async: false
  alias SymphonyControl.Auth.{Authenticate, HttpBody, RequestContext}
  alias SymphonyControl.{AuthHttpFixture, Repo}

  defmodule FramingFailure do
    alias Plug.Adapters.Test.Conn, as: TestAdapter
    def get_http_protocol(_), do: :"HTTP/1.1"
    def read_req_body(%{mode: :payload} = state, _), do: {:more, "ab", %{state | phase: :read, mode: :last}}
    def read_req_body(%{mode: :last} = state, _), do: {:ok, "cd", %{state | phase: :complete}}
    def read_req_body(%{mode: :more_empty} = state, _), do: {:more, "", %{state | phase: :read}}
    def read_req_body(%{mode: :oversized} = state, _), do: {:ok, "xx", %{state | phase: :read}}
    def read_req_body(%{mode: :error}, _), do: {:error, :closed}
    def read_req_body(%{mode: :throw}, _), do: throw(:owned_transport_fault)
    def read_req_body(%{mode: :partial} = state, _), do: {:more, "x", %{state | phase: :read, mode: :throw}}

    def send_resp(state, status, headers, body) do
      {:ok, sent, base} = TestAdapter.send_resp(state.base, status, headers, body)
      {:ok, sent, %{state | base: base}}
    end
  end

  defmodule CandidateAuthorizer do
    def authorize(%SymphonyControl.Auth.Actor{}, :runtime_identity_read), do: :ok
    def authorize(_, _), do: :deny
  end

  @tag repair_r1: true
  test "R1 rejects single and multiple chunked bodies before login work" do
    f = AuthHttpFixture.start!()

    for chunks <- [[32_768], [32_769], [16_384, 16_385]] do
      socket = connect(f)
      payload = Enum.map(chunks, fn n -> [Integer.to_string(n, 16), "\r\n", String.duplicate("x", n), "\r\n"] end)
      :ok = :ssl.send(socket, [request("GET", "/auth/login", "transfer-encoding: chunked\r\n"), payload, "0\r\n\r\n"])
      reply = response(socket)
      assert reply.status == 400
      assert not Map.has_key?(reply.headers, "set-cookie")
      assert not Map.has_key?(reply.headers, "location")
      assert {:error, :closed} = :ssl.recv(socket, 0, 1000)
    end

    assert pending() == 0
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  @tag repair_r1: true
  test "R1 unfinished chunked upload closes without reading its terminating chunk" do
    f = AuthHttpFixture.start!()
    socket = connect(f)
    started = System.monotonic_time(:millisecond)
    :ok = :ssl.send(socket, [request("GET", "/auth/login", "transfer-encoding: chunked\r\n"), "1\r\nx\r\n"])
    reply = response(socket, 1200)
    assert reply.status == 400
    assert System.monotonic_time(:millisecond) - started < 1200
    assert {:error, :closed} = :ssl.recv(socket, 0, 1000)
    assert pending() == 0
  end

  @tag repair_r1: true
  test "R1 exact content length boundary passes and oversized length closes before Store" do
    f = AuthHttpFixture.start!()
    socket = connect(f)
    :ok = :ssl.send(socket, [request("GET", "/auth/login", "content-length: 32768\r\n"), String.duplicate("x", 32_768)])
    assert response(socket).status == 303
    assert pending() == 1
    :ssl.close(socket)
    socket = connect(f)
    :ok = :ssl.send(socket, request("GET", "/auth/login", "content-length: 32769\r\n"))
    assert response(socket).status == 400
    assert {:error, :closed} = :ssl.recv(socket, 0, 1000)
    assert pending() == 1
  end

  @tag repair_r6: true
  test "R6 fully consumed split bodies preserve serial and pipelined health requests on refusals" do
    f = AuthHttpFixture.start!()
    probe = probe()

    for {method, path, status} <- [{"GET", "/auth/callback", 400}, {"POST", "/auth/logout", 403}, {"POST", "/auth/backchannel-logout", 400}],
        pipelined <- [false, true] do
      socket = connect(f)
      :ok = :ssl.send(socket, request(method, path, "content-length: 4\r\n"))
      assert_receive {:request_entry, ^probe, _pid, ^path, _at}, 1000
      second = request("GET", "/health/live", "")
      :ok = :ssl.send(socket, ["body", if(pipelined, do: second, else: "")])
      assert response(socket).status == status
      if not pipelined, do: :ok = :ssl.send(socket, second)
      assert response(socket).status == 200
      :ssl.close(socket)
      assert_receive {:request_entry, ^probe, _pid, "/health/live", _at}, 1000
    end

    saturated = %{callback: {System.monotonic_time(:millisecond) + 60_000, 120}}
    :sys.replace_state(SymphonyControl.Auth.RateLimiter, fn _ -> saturated end)
    socket = connect(f)
    :ok = :ssl.send(socket, request("GET", "/auth/callback", "content-length: 4\r\n"))
    assert_receive {:request_entry, ^probe, _pid, "/auth/callback", _at}, 1000
    :ok = :ssl.send(socket, ["body", request("GET", "/health/live", "")])
    assert response(socket).status == 429
    assert response(socket).status == 200
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  @tag repair_r3: true
  test "R3 initial Clock wait and provider share the handler entry deadline" do
    f = AuthHttpFixture.start!()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :delay_ms, 400)})
    probe = probe()
    clock = Process.whereis(SymphonyControl.Auth.Clock)
    :ok = :sys.suspend(clock)
    on_exit(fn -> if Process.alive?(clock), do: :sys.resume(clock) end)
    task = Task.async(fn -> AuthHttpFixture.callback(f, flow: flow) end)
    assert_receive {:request_entry, ^probe, _pid, "/auth/callback", entered}, 1000
    Process.sleep(4500)
    :ok = :sys.resume(clock)
    reply = Task.await(task, 2500)
    elapsed = System.monotonic_time(:millisecond) - entered
    assert reply.status == 503
    assert elapsed >= 4500 and elapsed < 5500
    assert is_nil(AuthHttpFixture.cookie(reply, "__Host-symphony-control"))
    assert AuthHttpFixture.counts(f).sessions == 0
    # There is no room for the frozen750ms Store contract after initial4500ms.
    assert Repo.query!("SELECT count(*) FROM control_auth_pending_logins WHERE consumed_at_ms IS NOT NULL", [], log: false).rows == [[0]]
    assert AuthHttpFixture.counts(f).exchanges == 0
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.delete(&1.opts, :delay_ms)})
    assert AuthHttpFixture.callback(f, flow: flow).status == 303
    assert AuthHttpFixture.callback(f, flow: flow).status == 403
    assert AuthHttpFixture.counts(f).exchanges == 1
  end

  test "positive real HTTPS login callback cookie and Authenticate survive body refusal repairs" do
    f = AuthHttpFixture.start!(runtime_identity_authorizer: CandidateAuthorizer)
    session = AuthHttpFixture.login!(f, body: "supported-body")
    assert AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie).status == 200
    assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
  end

  @tag repair_r1: true
  test "R1 slow partial CL and ambiguous framing close with no login work" do
    f = AuthHttpFixture.start!()
    probe = probe()
    socket = connect(f)
    :ok = :ssl.send(socket, request("GET", "/auth/login", "content-length: 32768\r\n"))
    assert_receive {:request_entry, ^probe, _pid, "/auth/login", entered}, 1000
    :ok = :ssl.send(socket, "x")
    assert response(socket, 1500).status in [400, 503]
    assert System.monotonic_time(:millisecond) - entered < 1500
    assert {:error, :closed} = :ssl.recv(socket, 0, 1000)

    for fields <- ["content-length: 1\r\ncontent-length: 1\r\n", "content-length: 1, 1\r\n", "content-length: 1\r\ntransfer-encoding: chunked\r\n", "transfer-encoding: gzip\r\n"] do
      socket = connect(f)
      :ok = :ssl.send(socket, [request("GET", "/auth/login", fields), "x"])
      assert response(socket).status == 400
      assert {:error, :closed} = :ssl.recv(socket, 0, 1000)
    end

    assert pending() == 0
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
  end

  @tag repair_r1: true
  test "R1 HTTP2 auth stream resets before body and health stays independent" do
    f = AuthHttpFixture.start!()

    {:ok, socket} =
      :ssl.connect(
        ~c"localhost",
        URI.parse(f.origin).port,
        [:binary, active: false, verify: :verify_peer, cacerts: [f.provider.ca], server_name_indication: ~c"localhost", alpn_advertised_protocols: ["h2"]],
        1000
      )

    on_exit(fn -> :ssl.close(socket) end)
    assert {:ok, "h2"} = :ssl.negotiated_protocol(socket)
    :ok = :ssl.send(socket, ["PRI * HTTP/2.0\r\n\r\nSM\r\n\r\n", frame(4, 0, 0, <<>>)])
    {encoded, _table} = HPAX.encode(:store, [{":method", "GET"}, {":scheme", "https"}, {":authority", "localhost"}, {":path", "/auth/login"}], HPAX.new(4096))
    :ok = :ssl.send(socket, frame(1, 4, 1, IO.iodata_to_binary(encoded)))
    assert reset_code(socket, 1) == 7
    assert pending() == 0
    assert AuthHttpFixture.counts(f) == %{exchanges: 0, sessions: 0}
    assert AuthHttpFixture.get(f, "/health/live").status == 200
  end

  @tag repair_r3: true
  test "R3 initial Clock and real eligibility share protected request deadline" do
    f = AuthHttpFixture.start!(runtime_identity_authorizer: CandidateAuthorizer)
    session = AuthHttpFixture.login!(f)
    Agent.update(f.provider.state, &%{&1 | opts: Keyword.put(&1.opts, :delay_ms, 1000)})
    probe = probe()
    clock = Process.whereis(SymphonyControl.Auth.Clock)
    :ok = :sys.suspend(clock)
    on_exit(fn -> if Process.alive?(clock), do: :sys.resume(clock) end)
    task = Task.async(fn -> AuthHttpFixture.get(f, "/api/v1/control/identity", cookie: session.cookie) end)
    assert_receive {:request_entry, ^probe, _pid, "/api/v1/control/identity", entered}, 1000
    Process.sleep(4500)
    :ok = :sys.resume(clock)
    reply = Task.await(task, 2500)
    assert reply.status in [403, 503]
    assert System.monotonic_time(:millisecond) - entered < 5500
  end

  @tag repair_r6: true
  test "R6 Login refusal and Clock loss keep a fully consumed Conn" do
    f = AuthHttpFixture.start!()
    probe = probe()
    flow = AuthHttpFixture.login!(f, phase: :begin)
    assert_receive {:request_entry, ^probe, _pid, "/auth/login", _at}, 1000

    for unavailable <- [false, true] do
      if unavailable, do: stop_supervised!(SymphonyControl.AuthDbFixture.SnapshotClock)
      socket = connect(f)
      fields = ["content-length: 4\r\ncookie: ", flow.cookie, "\r\n"]
      :ok = :ssl.send(socket, request("GET", "/auth/callback?code=x&state=x", fields))
      assert_receive {:request_entry, ^probe, _pid, "/auth/callback", _at}, 1000
      :ok = :ssl.send(socket, ["body", request("GET", "/health/live", "")])
      assert response(socket).status == if(unavailable, do: 503, else: 403)
      assert response(socket).status == 200
      assert_receive {:request_entry, ^probe, _pid, "/health/live", _at}, 1000
      :ssl.close(socket)
    end
  end

  test "bounded reader retains latest transport on empty more oversized and failed partial reads" do
    cases = [
      {:more_empty, "1", :invalid_request},
      {:oversized, "1", :invalid_request},
      {:error, "1", :dependency_unavailable},
      {:partial, "3", :dependency_unavailable}
    ]

    for {mode, length, reason} <- cases do
      conn = failure_conn(mode, length)
      assert {:error, ^reason, latest} = HttpBody.read(conn, RequestContext.deadline())
      assert Plug.Conn.get_resp_header(latest, "connection") == ["close"]
      if mode in [:more_empty, :oversized, :partial], do: assert(elem(latest.adapter, 1).phase == :read)
    end
  end

  test "payload seam retains exactly bounded bytes and the final transport without rereading" do
    conn = failure_conn(:payload, "4")
    assert {:ok, "abcd", latest} = HttpBody.read_payload(conn, RequestContext.deadline())
    assert elem(latest.adapter, 1).phase == :complete
    oversized = failure_conn(:oversized, "1")
    assert {:error, :invalid_request, closed} = HttpBody.read_payload(oversized, RequestContext.deadline())
    assert Plug.Conn.get_resp_header(closed, "connection") == ["close"]
  end

  test "expired body deadline closes without reading and protected refusals clear forged actor" do
    conn = failure_conn(:oversized, "1")
    past = System.monotonic_time() - System.convert_time_unit(1, :millisecond, :native)
    assert {:error, :dependency_unavailable, latest} = HttpBody.read(conn, past)
    assert elem(latest.adapter, 1).phase == :unread

    for {mode, status} <- [{:oversized, 400}, {:error, 503}, {:partial, 503}] do
      length = if mode == :partial, do: "3", else: "1"
      conn = failure_conn(mode, length) |> Plug.Conn.assign(:current_actor, :forged)
      reply = Authenticate.call(conn, [])
      assert reply.status == status
      assert reply.halted
      assert reply.assigns.current_actor == nil
      assert Plug.Conn.get_resp_header(reply, "connection") == ["close"]
    end
  end

  defp failure_conn(mode, length) do
    conn = Plug.Test.conn(:get, "/api/v1/control/identity") |> Plug.Conn.put_req_header("content-length", length)
    {_, base} = conn.adapter
    %{conn | adapter: {FramingFailure, %{base: base, mode: mode, phase: :unread}}}
  end

  defp frame(type, flags, stream, payload), do: <<byte_size(payload)::24, type::8, flags::8, 0::1, stream::31, payload::binary>>

  defp reset_code(socket, stream) do
    case :ssl.recv(socket, 9, 1500) do
      {:ok, <<length::24, type::8, _flags::8, _::1, id::31>>} ->
        payload = if length == 0, do: <<>>, else: elem(:ssl.recv(socket, length, 1500), 1)
        if type == 3 and id == stream, do: :binary.decode_unsigned(payload), else: reset_code(socket, stream)

      {:error, reason} ->
        reason
    end
  end

  defp pending, do: Repo.query!("SELECT count(*) FROM control_auth_pending_logins", [], log: false).rows |> hd() |> hd()

  defp connect(f) do
    {:ok, socket} =
      :ssl.connect(
        ~c"localhost",
        URI.parse(f.origin).port,
        [:binary, active: false, verify: :verify_peer, cacerts: [f.provider.ca], server_name_indication: ~c"localhost", alpn_advertised_protocols: ["http/1.1"]],
        1000
      )

    on_exit(fn -> :ssl.close(socket) end)
    socket
  end

  defp request(method, path, headers), do: [method, " ", path, " HTTP/1.1\r\nhost: localhost\r\n", headers, "\r\n"]

  defp response(socket, timeout \\ 2000) do
    # One-byte header reads avoid consuming the next pipelined response.
    case header(socket, "", timeout) do
      {:ok, bytes} ->
        [line | fields] = String.split(bytes, "\r\n", trim: true)

        headers =
          Map.new(fields, fn field ->
            [key, value] = String.split(field, ":", parts: 2)
            {String.downcase(key), String.trim(value)}
          end)

        length = String.to_integer(Map.get(headers, "content-length", "0"))
        if length > 0, do: {:ok, _body} = :ssl.recv(socket, length, timeout)
        %{status: line |> String.split() |> Enum.at(1) |> String.to_integer(), headers: headers}

      {:error, reason} ->
        %{status: reason, headers: %{}}
    end
  end

  defp header(socket, bytes, timeout) do
    if String.ends_with?(bytes, "\r\n\r\n") do
      {:ok, bytes}
    else
      case :ssl.recv(socket, 1, timeout) do
        {:ok, byte} -> header(socket, bytes <> byte, timeout)
        error -> error
      end
    end
  end

  defp probe do
    ref = make_ref()
    id = {__MODULE__, ref}
    owner = self()
    :ok = :telemetry.attach(id, [:bandit, :request, :start], fn _, _, meta, _ -> send(owner, {:request_entry, ref, self(), meta.conn.request_path, System.monotonic_time(:millisecond)}) end, nil)
    on_exit(fn -> :telemetry.detach(id) end)
    ref
  end
end
