defmodule SymphonyControl.Auth.Config do
  @moduledoc "Immutable operator bindings. Task1 never activates production authentication."
  @fields ~w(generation issuer discovery_url jwks_url authorization_url token_url end_session_url client_id client_auth_method allowed_algorithms public_https_origin callback_uri post_logout_uri backchannel_uri application_id provider_id resource_id client_secret_ref session_key_ref eligible_mechanism live_evidence)a
  @urls ~w(issuer discovery_url jwks_url authorization_url token_url end_session_url public_https_origin callback_uri post_logout_uri backchannel_uri)a
  @strings ~w(generation client_id application_id provider_id resource_id)a
  defstruct @fields ++ [tls_cacerts: nil]

  @type t :: %__MODULE__{}
  @type reason :: :invalid_request | :forbidden | :dependency_unavailable | :unknown_outcome | :rate_limited

  @spec load(term()) :: {:ok, t()} | {:error, :invalid_config}
  def load(input) when is_map(input) do
    valid =
      Map.keys(input) -- @fields == [] and
        Enum.all?(@urls, &https?(Map.get(input, &1))) and
        Enum.all?(@strings, &nonempty?(Map.get(input, &1))) and
        Enum.all?([:client_secret_ref, :session_key_ref], &absolute_ref?(Map.get(input, &1))) and
        input[:client_auth_method] in ["client_secret_basic", "client_secret_post"] and
        valid_algorithms?(input[:allowed_algorithms]) and
        Enum.all?([:callback_uri, :post_logout_uri, :backchannel_uri], &(origin(input[&1]) == input[:public_https_origin]))

    if valid, do: {:ok, struct!(__MODULE__, input)}, else: {:error, :invalid_config}
  end

  def load(_), do: {:error, :invalid_config}

  @spec activation_allowed?(t()) :: boolean()
  def activation_allowed?(%__MODULE__{}), do: false

  defp nonempty?(value), do: is_binary(value) and byte_size(value) in 1..4096
  defp absolute_ref?(value), do: nonempty?(value) and Path.type(value) == :absolute
  defp valid_algorithms?(algs), do: is_list(algs) and algs != [] and Enum.all?(algs, &(&1 in ["RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "PS256", "PS384", "PS512"]))

  defp https?(value) when is_binary(value) do
    if String.valid?(value) do
      case URI.new(value) do
        {:ok, uri} -> valid_https_uri?(uri, value)
        _ -> false
      end
    else
      false
    end
  end

  defp https?(_), do: false

  defp valid_https_uri?(uri, value) do
    uri.scheme == "https" and nonempty?(uri.host) and uri.port in 1..65_535 and
      uri.userinfo == nil and uri.query == nil and uri.fragment == nil and
      not String.match?(value, ~r/[\s\x00-\x1F]/u)
  end

  defp origin(url), do: url |> URI.parse() |> Map.merge(%{path: nil, query: nil, fragment: nil}) |> URI.to_string()
end
