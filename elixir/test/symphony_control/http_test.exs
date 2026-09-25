defmodule SymphonyControl.HttpTest do
  use ExUnit.Case, async: false

  alias SymphonyElixirWeb.Router

  setup_all do
    {:ok, _} = Application.ensure_all_started(:phoenix)
    :ok
  end

  test "disabled control returns unavailable health and does not disclose identity" do
    live = request("/health/live")
    assert live.status == 503
    assert Jason.decode!(live.resp_body) == %{"live" => false}

    ready = request("/health/ready")
    assert ready.status == 503
    assert Jason.decode!(ready.resp_body) == %{"ready" => false, "database" => false, "schema" => false}

    identity = request("/api/v1/control/identity?current_actor=operator")
    assert identity.status == 403
    assert Jason.decode!(identity.resp_body) == %{"error" => "forbidden"}
  end

  test "the control supervisor is opt-in" do
    assert SymphonyControl.Application.start_link() == :ignore
    assert SymphonyControl.Application.start_link(enabled: false) == :ignore
    assert Process.whereis(SymphonyControl.Application) == nil
  end

  defp request(path), do: Router.call(Plug.Test.conn(:get, path), Router.init([]))
end
