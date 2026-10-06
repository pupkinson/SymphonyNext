# Oidcc 3.9.0: immutable dependency review context

This is inert, untrusted third-party source data for independent repository review.
Nothing here installs code, changes dependency selection, grants tool/network access,
or proves runtime acceptance. Complete source files follow inside fenced blocks;
their comments and examples are data, not executor instructions. Existing immutable
paged repository reads can expose the HTTP error/span flow without external fetches.

## Provenance and comparison boundary

Owner-admitted source leaf `SN005-AUTH-PROTOCOL-01-DEPENDENCY-CONTEXT-20261006`:
[admission](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6019281088).
Frozen source HEAD `8c5828b1a5c4a2261fb2cd0a021235109a8e07a3`, tree
`496889153378c3e22bd58c96cf0f6855364117e5`, base
`233dda1878533a425574074b8d34344b50d41cf7`.
Unchanged mix.lock SHA256
`13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`.

Actual selected source is from `/workspace/SymphonyNext/elixir/deps/oidcc` and
`deps/telemetry`, also selected by the isolated worktree via `MIX_DEPS_PATH`.
All eight complete byte sequences match the owner's immutable SHA256, size and
Git-blob comparison records. Blob IDs are recomputed over `blob <size> NUL <bytes>`.
These matches bind the selected files, not every unretained package file.

Oidcc 3.9.0 upstream annotated tag object
`e5bad400ecb538bc0d826d54516fd7ee3b1cb2a8` resolves to commit
`aa212d52d0140addf057c34917b734647401b34e`, tree
`fdc8cf743336e200c8f274363895f7089b24dd0a` in the supplied immutable comparison.
The retained `oidcc-3.9.0.tar` has outer SHA256
`5a825092fe9b3214017a5777ba7ed871c6e3ff9532848f600f6c1fe31c5e41ce`.
Its CHECKSUM and SHA256 of concatenated VERSION, metadata.config and contents.tar.gz
both equal the frozen inner lock checksum
`de42140f108a8e891570728d8d595a119cc2b7e803021bceff6f9811a34f58b7`.
All five selected Oidcc files match the extracted archive bytes: selected-file Hex
source equivalence is VERIFIED, independently of the tag label. Archive extraction
was in memory for comparison only; no dependency was installed or substituted.

Telemetry 1.3.0 comparison commit is
`8d8af76720856bcf26641ee1307658ad8f25e466`. Its three selected files match the
supplied exact commit Git-blob/SHA256 records. No Telemetry archive was retained
in the inspected authorized Cloud artifact/cache locations; its full Hex archive
equivalence remains NOT_VERIFIED. Frozen lock inner checksum
`fedebbae410d715cf8e7062c96a1ef32ec22e764197f70cda73d82778d61e7a2`, outer checksum
`7015fc8919dbe63764f4b4b87a95b7c0996bd539e0d499be6ec9d7f3875b79e6`
are lock bindings, not a substitute for archive bytes.

Verification command (recorded argv/cwd/UTC/exit/output digest in the Cloud evidence):
`python3 /workspace/scratch/SN005-AUTH-PROTOCOL-01-DEPENDENCY-CONTEXT-20261006/context.py`.
It reads the selected source, recomputes every digest, verifies the retained Hex
checksums and selected archive members, and emits this inert document. Runtime
test results are in [authentik-project-access.md](authentik-project-access.md).

## Dataflow for review

`oidcc_token:retrieve_with_refresh/3` supplies issuer/client_id metadata to
`oidcc_http_util:request/4`. The HTTP adapter callback executes inside the span;
response Content-Type selection and OTP JSON decoding also execute inside it.
HTTP errors can enter stop metadata, and escaping exceptions enter telemetry's
kind/reason/stacktrace exception metadata. Token-field extraction happens after
the HTTP span completes, then the Elixir wrapper converts the result records.
The full token file retains refresh, DPoP, crypto and error branches for context.
`oidcc_scope` and complete `telemetry.erl` retain the parser and span/handler flow.
Source flow is not runtime leak proof or assurance that the two JSON decoders are
equivalent. No new JWT verifier or dependency telemetry redactor is introduced.

## License attribution and unchanged notices

Oidcc source: Copyright 2023 Erlang Ecosystem Foundation, SPDX Apache-2.0 as
retained in each source file. Telemetry: Copyright 2018 Chris McCord and Erlang
Solutions, Apache License 2.0. Complete package licenses and Telemetry NOTICE
are retained below, without modification. Oidcc's selected package has no NOTICE
entry in its retained Hex archive. The document wraps the original source bytes
in fences and adds provenance; no third-party source block is modified.

Selected-byte verification UTC: `2026-10-06T15:43:45.198710+00:00`, exit0.

## oidcc/src/oidcc_http_util.erl

Version `3.9.0`, repository `erlef/oidcc`, commit `aa212d52d0140addf057c34917b734647401b34e`.

Git blob `88f8f13de1d10bb454a6643f5b8d32859a3a9039`; SHA256 `099c564950145ef3e85a36c7eaef149ea826027364b3bb39fa7544f53ad7e8c2`; size `11935` bytes.

Source: https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_http_util.erl

````erlang
%% SPDX-FileCopyrightText: 2023 Erlang Ecosystem Foundation
%% SPDX-License-Identifier: Apache-2.0

-module(oidcc_http_util).

-feature(maybe_expr, enable).

-moduledoc "HTTP Client Utilities".

-export([basic_auth_header/2]).
-export([bearer_auth_header/1]).
-export([headers_to_cache_deadline/2]).
-export([request/4]).

-export_type([
    http_header/0, error/0, httpc_error/0, query_params/0, telemetry_opts/0, request_opts/0
]).

-doc "See `uri_string:compose_query/1`.".
-doc #{since => <<"3.0.0">>}.
-type query_params() :: [{unicode:chardata(), unicode:chardata() | true}].

-doc "HTTP header representation used by OIDCC.".
-doc #{since => <<"3.0.0">>}.
-type http_header() :: {Field :: [byte()] | binary(), Value :: iodata()}.

-doc #{since => <<"3.0.0">>}.
-type error() ::
    {http_error, StatusCode :: non_neg_integer(), HttpBodyResult :: binary() | map()}
    | {use_dpop_nonce, Nonce :: binary(), HttpBodyResult :: binary() | map()}
    | invalid_content_type
    | {invalid_json, Reason :: term()}
    | httpc_error().

-doc "Transport error. The default adapter returns errors documented by `httpc:request/5`.".
-doc #{since => <<"3.0.0">>}.
-type httpc_error() :: term().

-doc """
See `httpc:request/5`.

## Parameters

* `timeout` - timeout for request
* `ssl` - TLS config
* `httpc_profile` - `httpc` profile used by the default adapter
* `http_adapter` - `{AdapterModule, AdapterConfigMap}` transport adapter
""".
-doc #{since => <<"3.0.0">>}.
-type request_opts() :: #{
    timeout => timeout(),
    ssl => [ssl:tls_option()],
    httpc_profile => atom() | pid(),
    http_adapter => oidcc_http_adapter:config()
}.

-doc #{since => <<"3.0.0">>}.
-type telemetry_opts() :: #{
    topic := [atom()],
    extra_meta => map()
}.

-doc false.
-spec basic_auth_header(User, Secret) -> http_header() when
    User :: binary(),
    Secret :: binary().
basic_auth_header(User, Secret) ->
    UserEnc = uri_string:compose_query([{User, true}]),
    SecretEnc = uri_string:compose_query([{Secret, true}]),
    RawAuth = <<UserEnc/binary, <<":">>/binary, SecretEnc/binary>>,
    AuthData = base64:encode(RawAuth),
    {"authorization", [<<"Basic ">>, AuthData]}.

-doc false.
-spec bearer_auth_header(Token) -> http_header() when Token :: binary().
bearer_auth_header(Token) ->
    {"authorization", [<<"Bearer ">>, Token]}.

-doc false.
-spec request(Method, Request, TelemetryOpts, RequestOpts) ->
    {ok, {{json, term()} | {jwt, binary()}, [oidcc_http_adapter:header()]}}
    | {error, error()}
when
    Method :: oidcc_http_adapter:method(),
    Request :: oidcc_http_adapter:request(),
    TelemetryOpts :: telemetry_opts(),
    RequestOpts :: request_opts().
request(Method, Request, TelemetryOpts, RequestOpts) ->
    TelemetryTopic = maps:get(topic, TelemetryOpts),
    TelemetryExtraMeta = maps:get(extra_meta, TelemetryOpts, #{}),
    Timeout = maps:get(timeout, RequestOpts, timer:minutes(1)),
    SslOpts = maps:get(ssl, RequestOpts, undefined),
    HttpProfile = maps:get(httpc_profile, RequestOpts, default),
    {Adapter, AdapterConfig} = maps:get(
        http_adapter,
        RequestOpts,
        {oidcc_http_adapter_httpc, #{profile => HttpProfile}}
    ),

    HttpOpts0 = [{timeout, Timeout}],
    HttpOpts =
        case SslOpts of
            undefined -> HttpOpts0;
            _Opts -> [{ssl, SslOpts} | HttpOpts0]
        end,

    telemetry:span(
        TelemetryTopic,
        TelemetryExtraMeta,
        fun() ->
            maybe
                {ok, {_StatusLine, Headers, _Result} = Response} ?=
                    erlang:apply(
                        Adapter,
                        request,
                        [
                            Method,
                            Request,
                            HttpOpts,
                            [{body_format, binary}],
                            AdapterConfig
                        ]
                    ),
                {ok, BodyAndFormat} ?= extract_successful_response(Response),
                {{ok, {BodyAndFormat, Headers}}, TelemetryExtraMeta}
            else
                {error, Reason} ->
                    {{error, Reason}, maps:put(error, Reason, TelemetryExtraMeta)}
            end
        end
    ).

-spec extract_successful_response({StatusLine, [HttpHeader], HttpBodyResult}) ->
    {ok, {json, term()} | {jwt, binary()}} | {error, error()}
when
    StatusLine :: {HttpVersion, StatusCode, string()},
    HttpVersion :: string(),
    StatusCode :: non_neg_integer(),
    HttpHeader :: oidcc_http_adapter:header(),
    HttpBodyResult :: binary().
extract_successful_response({{_HttpVersion, Status, _HttpStatusName}, Headers, HttpBodyResult}) when
    Status == 200 orelse Status == 201
->
    case fetch_content_type(Headers) of
        json ->
            case decode_json(HttpBodyResult) of
                {ok, Json} ->
                    {ok, {json, Json}};
                {error, Reason} ->
                    {error, {invalid_json, Reason}}
            end;
        jwt ->
            {ok, {jwt, HttpBodyResult}};
        unknown ->
            {error, invalid_content_type}
    end;
extract_successful_response({{_HttpVersion, StatusCode, _HttpStatusName}, Headers, HttpBodyResult}) ->
    Body =
        case fetch_content_type(Headers) of
            json ->
                %% A provider that cannot format its own error document must not
                %% mask the status code, which is the actual failure. Hand back
                %% the undecoded body, exactly as the `unknown' branch does.
                case decode_json(HttpBodyResult) of
                    {ok, Json} -> Json;
                    {error, _Reason} -> HttpBodyResult
                end;
            jwt ->
                HttpBodyResult;
            unknown ->
                HttpBodyResult
        end,
    case proplists:lookup("dpop-nonce", Headers) of
        {"dpop-nonce", DpopNonce} ->
            {error, {use_dpop_nonce, iolist_to_binary(DpopNonce), Body}};
        _ ->
            {error, {http_error, StatusCode, Body}}
    end.

%% `json:decode/1' raises on malformed input rather than returning an error.
%% A provider is free to serve a broken document under a JSON content type, and
%% that must not take the calling process down with it.
%%
%% The guard keeps that narrow. A body that is not a binary means the adapter
%% broke its contract, most often by dropping the `body_format' request option
%% on the way to `httpc:request/5' and getting a string back. That is the
%% caller's bug, not the provider's, so it keeps crashing where the stack trace
%% still points at it instead of being reported as a malformed document.
-spec decode_json(Body :: binary()) -> {ok, term()} | {error, term()}.
decode_json(Body) when is_binary(Body) ->
    try
        {ok, json:decode(Body)}
    catch
        error:Reason ->
            {error, Reason}
    end.

-spec fetch_content_type(Headers) -> json | jwt | unknown when
    Headers :: [oidcc_http_adapter:header()].
fetch_content_type(Headers) ->
    case proplists:lookup("content-type", Headers) of
        {"content-type", ContentType} ->
            case binary:split(iolist_to_binary(ContentType), <<";">>) of
                [<<"application/jwt">> | _Rest] ->
                    jwt;
                [MediaType | _Rest] ->
                    case is_json_content_type(MediaType) of
                        true ->
                            json;
                        false ->
                            unknown
                    end
            end;
        _Other ->
            unknown
    end.

%% RFC 6838 §4.2.8 structured-suffix syntax: any `application/<subtype>+json'
%% is a JSON document with extra contract on top. Both `application/json' and
%% `application/jwk-set+json' fit, plus less common variants like
%% `application/<vendor>+json'. Match the generic pattern so providers using
%% any `+json' subtype on discovery / JWKS responses are accepted.
-spec is_json_content_type(ContentType :: binary()) -> boolean().
is_json_content_type(ContentType) ->
    MediaType = string:lowercase(string:trim(ContentType)),
    case MediaType of
        <<"application/json">> ->
            true;
        <<"application/", Subtype/binary>> ->
            Size = byte_size(Subtype),
            Size >= 5 andalso binary:part(Subtype, Size - 5, 5) =:= <<"+json">>;
        _ ->
            false
    end.

-spec headers_to_cache_deadline(Headers, DefaultExpiry) -> non_neg_integer() when
    Headers :: [oidcc_http_adapter:header()], DefaultExpiry :: pos_integer().
headers_to_cache_deadline(Headers, DefaultExpiry) ->
    case proplists:lookup("cache-control", Headers) of
        {"cache-control", Cache} ->
            try
                cache_deadline(Cache, header_age(Headers), DefaultExpiry)
            catch
                _:_ ->
                    DefaultExpiry
            end;
        none ->
            DefaultExpiry
    end.

-spec cache_deadline(Cache :: iodata(), Age :: non_neg_integer(), Fallback :: pos_integer()) ->
    non_neg_integer().
cache_deadline(Cache, Age, Fallback) ->
    %% RFC 7234 §5.2: cache-control directive names are case-insensitive
    %% (`Max-Age', `MAX-AGE', and `max-age' are all valid). Lowercase the
    %% whole header before splitting so the `<<"max-age">>' match below
    %% catches every spelling.
    Lower = string:lowercase(iolist_to_binary(Cache)),
    Entries = binary:split(Lower, [<<",">>, <<"=">>, <<" ">>], [global, trim_all]),
    case extract_max_age(Entries) of
        undefined ->
            Fallback;
        MaxAge ->
            %% RFC 7234 §4.2: what is left of a stated lifetime is that lifetime
            %% minus how long the response has already been held, which the
            %% `Age' header of an intermediary reports. `Age' only ever applies
            %% to a lifetime the server stated, never to the caller's fallback.
            max(clamp_expiry(MaxAge, Fallback) - Age, 0)
    end.

%% RFC 7234 §5.1: `Age' is how many seconds ago the response was generated, as
%% estimated by whatever shared cache is serving it. A malformed, negative or
%% absent value contributes nothing rather than shortening the lifetime.
-spec header_age(Headers :: [oidcc_http_adapter:header()]) -> non_neg_integer().
header_age(Headers) ->
    case proplists:lookup("age", Headers) of
        {"age", Age} ->
            try binary_to_integer(string:trim(iolist_to_binary(Age))) of
                Seconds when Seconds > 0 ->
                    erlang:convert_time_unit(Seconds, second, millisecond);
                _NonPositive ->
                    0
            catch
                _:_ ->
                    0
            end;
        none ->
            0
    end.

%% Walk the cache-control tokens looking for `max-age=<N>' and return N as
%% milliseconds, or `undefined' when the value is missing, zero, or non-numeric.
-spec extract_max_age([binary()]) -> non_neg_integer() | undefined.
extract_max_age([<<"max-age">>, Value | _Rest]) ->
    try binary_to_integer(Value) of
        N when N > 0 ->
            erlang:convert_time_unit(N, second, millisecond);
        _ ->
            undefined
    catch
        _:_ ->
            undefined
    end;
extract_max_age([_ | Rest]) ->
    extract_max_age(Rest);
extract_max_age([]) ->
    undefined.

%% `erlang:send_after/3' (used by `oidcc_provider_configuration_worker') and
%% `timer:send_after/2' both accept at most 16#FFFFFFFF ms (~49.7 days).
%% Clamp the cache-derived expiry so an over-eager provider that advertises
%% a longer max-age can never trigger badarg in the caller.
-spec clamp_expiry(term(), pos_integer()) -> pos_integer().
clamp_expiry(Value, _Fallback) when is_integer(Value), Value > 0, Value =< 16#FFFFFFFF ->
    Value;
clamp_expiry(Value, _Fallback) when is_integer(Value), Value > 16#FFFFFFFF ->
    16#FFFFFFFF;
clamp_expiry(_Value, Fallback) ->
    Fallback.
````

## oidcc/src/oidcc_token.erl

Version `3.9.0`, repository `erlef/oidcc`, commit `aa212d52d0140addf057c34917b734647401b34e`.

Git blob `b18e3c7ac21ef7adfaf63181b79e6cd5b8c2909a`; SHA256 `289be9bcb0e4677cba3dc98a3b4675070aec7beb27054726da395166b85ac2e3`; size `55709` bytes.

Source: https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_token.erl

````erlang
%% SPDX-FileCopyrightText: 2023 Erlang Ecosystem Foundation
%% SPDX-License-Identifier: Apache-2.0

-module(oidcc_token).

-feature(maybe_expr, enable).

-moduledoc """
Facilitate OpenID Code/Token Exchanges.

## Records

To use the records, import the definition:

```erlang
-include_lib(["oidcc/include/oidcc_token.hrl"]).
```

## Telemetry

See [`Oidcc.Token`](`m:'Elixir.Oidcc.Token'`).
""".
-moduledoc #{since => <<"3.0.0">>}.

-include("oidcc_client_context.hrl").
-include("oidcc_provider_configuration.hrl").
-include("oidcc_token.hrl").

-include_lib("jose/include/jose_jwe.hrl").
-include_lib("jose/include/jose_jwk.hrl").
-include_lib("jose/include/jose_jws.hrl").
-include_lib("jose/include/jose_jwt.hrl").

-export([client_credentials/2]).
-export([jwt_profile/4]).
-export([refresh/3]).
-export([retrieve/3]).
-export([retrieve_with_refresh/3]).
-export([validate_jarm/3]).
-export([validate_id_token/3]).
-export([validate_jwt/3]).
-export([authorization_headers/4]).
-export([authorization_headers/5]).

-export_type([access/0]).
-export_type([authorization_headers_opts/0]).
-export_type([client_credentials_opts/0]).
-export_type([error/0]).
-export_type([id/0]).
-export_type([jwt_profile_opts/0]).
-export_type([refresh/0]).
-export_type([refresh_opts/0]).
-export_type([refresh_opts_no_sub/0]).
-export_type([refresh_info/0]).
-export_type([retrieve_opts/0]).
-export_type([validate_jarm_opts/0]).
-export_type([validate_jwt_opts/0]).
-export_type([t/0]).

-doc """
ID Token Wrapper.

## Fields

* `token` - The retrieved token.
* `claims` - Unpacked claims of the verified token.
""".
-doc #{since => <<"3.0.0">>}.
-type id() :: #oidcc_token_id{token :: binary(), claims :: oidcc_jwt_util:claims()}.

-doc """
Access Token Wrapper.

## Fields

* `token` - The retrieved token.
* `expires` - Number of seconds the token is valid.
""".
-doc #{since => <<"3.0.0">>}.
-type access() ::
    #oidcc_token_access{token :: binary(), expires :: pos_integer() | undefined, type :: binary()}.

-doc """
Refresh Token Wrapper.

## Fields

* `token` - The retrieved token.
""".
-doc #{since => <<"3.0.0">>}.
-type refresh() :: #oidcc_token_refresh{token :: binary()}.

-doc """
Token Response Wrapper.

## Fields

* `id` - `t:id/0`.
* `access` - `t:access/0`.
* `refresh` - `t:refresh/0`.
* `scope` - `t:oidcc_scope:scopes/0`.
""".
-doc #{since => <<"3.0.0">>}.
-type t() ::
    #oidcc_token{
        id :: oidcc_token:id() | none,
        access :: oidcc_token:access() | none,
        refresh :: oidcc_token:refresh() | none,
        scope :: oidcc_scope:scopes()
    }.

-doc """
Options for retrieving a token.

See https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.3.

## Fields

* `pkce_verifier` - PKCE verifier (random string previously given to
  `m:oidcc_authorization`), see
  https://datatracker.ietf.org/doc/html/rfc7636#section-4.1.
* `require_pkce` - whether to require PKCE when getting the token.
* `nonce` - Nonce to check.
* `scope` - Scope to store with the token.
* `refresh_jwks` - How to handle tokens with an unknown `kid`.
  See `t:oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun/0`.
* `redirect_uri` - Redirect URI given to `oidcc_authorization:create_redirect_url/2`.
* `dpop_nonce` - if using DPoP, the `nonce` value to use in the proof claim.
* `trusted_audiences` - if present, a list of additional audience values to
  accept. Defaults to `any` which allows any additional values.
* `validate_azp` - if `client_id`, validate that the `azp` claim matches the
  client id. If `any`, skip the validation. Defaults to `client_id`. If a
  binary or a list of binaries is given, validate that the `azp` claim matches
  one of those.
* `token_request_claims` - Additional claims to use with the token request.
""".
-doc #{since => <<"3.0.0">>}.
-type retrieve_opts() ::
    #{
        pkce_verifier => binary(),
        require_pkce => boolean(),
        nonce => binary() | any,
        scope => oidcc_scope:scopes(),
        preferred_auth_methods => [oidcc_auth_util:auth_method(), ...],
        refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
        redirect_uri => uri_string:uri_string(),
        request_opts => oidcc_http_util:request_opts(),
        url_extension => oidcc_http_util:query_params(),
        body_extension => oidcc_http_util:query_params(),
        dpop_nonce => binary(),
        trusted_audiences => [binary()] | any,
        validate_azp => binary() | [binary()] | client_id | any,
        token_request_claims => #{binary() => binary() | integer()}
    }.

-doc "See `t:refresh_opts_no_sub/0`.".
-doc #{since => <<"3.0.0">>}.
-type refresh_opts_no_sub() ::
    #{
        scope => oidcc_scope:scopes(),
        preferred_auth_methods => [oidcc_auth_util:auth_method(), ...],
        refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
        request_opts => oidcc_http_util:request_opts(),
        url_extension => oidcc_http_util:query_params(),
        body_extension => oidcc_http_util:query_params(),
        dpop_nonce => binary(),
        trusted_audiences => [binary()] | any,
        validate_azp => binary() | [binary()] | client_id | any,
        token_request_claims => #{binary() => binary() | integer()}
    }.

-doc #{since => <<"3.0.0">>}.
-type refresh_opts() ::
    #{
        scope => oidcc_scope:scopes(),
        preferred_auth_methods => [oidcc_auth_util:auth_method(), ...],
        refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
        expected_subject := binary(),
        request_opts => oidcc_http_util:request_opts(),
        url_extension => oidcc_http_util:query_params(),
        body_extension => oidcc_http_util:query_params(),
        dpop_nonce => binary(),
        trusted_audiences => [binary()] | any,
        validate_azp => binary() | [binary()] | client_id | any,
        token_request_claims => #{binary() => binary() | integer()}
    }.

-doc """
Options for refreshing a token.

See https://datatracker.ietf.org/doc/html/rfc6749#section-4.1.3.

## Fields

* `scope` - Scope to store with the token.
* `refresh_jwks` - How to handle tokens with an unknown `kid`.
  See `t:oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun/0`.
* `expected_subject` - `sub` of the original token.
""".
-doc #{since => <<"3.2.0">>}.
-type validate_jarm_opts() ::
    #{
        trusted_audiences => [binary()] | any
    }.

-doc #{since => <<"3.0.0">>}.
-type jwt_profile_opts() :: #{
    scope => oidcc_scope:scopes(),
    refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
    request_opts => oidcc_http_util:request_opts(),
    kid => binary(),
    url_extension => oidcc_http_util:query_params(),
    body_extension => oidcc_http_util:query_params()
}.

-doc #{since => <<"3.0.0">>}.
-type client_credentials_opts() :: #{
    scope => oidcc_scope:scopes(),
    refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
    request_opts => oidcc_http_util:request_opts(),
    url_extension => oidcc_http_util:query_params(),
    body_extension => oidcc_http_util:query_params()
}.

-doc #{since => <<"3.0.0">>}.
-type authorization_headers_opts() :: #{
    dpop_nonce => binary()
}.

-doc #{since => <<"3.2.0">>}.
-type validate_jwt_opts() ::
    #{
        signing_algs => [binary()] | undefined,
        encryption_algs => [binary()] | undefined,
        encryption_encs => [binary()] | undefined,
        trusted_audiences => [binary()] | any,
        refresh_jwks => oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun()
    }.

-doc """
Whatever a `refresh_jwks` function reported alongside the refreshed keys.

`undefined` when no refresh happened, or when the function used the two element
return that carries only the keys. `oidcc` does not interpret it.
""".
-doc #{since => <<"3.9.0">>}.
-type refresh_info() :: term() | undefined.

-doc #{since => <<"3.0.0">>}.
-type error() ::
    {missing_claim, MissingClaim :: binary(), Claims :: oidcc_jwt_util:claims()}
    | pkce_verifier_required
    | no_supported_auth_method
    | bad_access_token_hash
    | sub_invalid
    | signature_required
    | token_expired
    | token_not_yet_valid
    | {none_alg_used, Token :: t()}
    | {missing_claim, ExpClaim :: {binary(), term()}, Claims :: oidcc_jwt_util:claims()}
    | {grant_type_not_supported,
        authorization_code | refresh_token | jwt_bearer | client_credentials}
    | {invalid_property, {
        Field :: id_token | refresh_token | access_token | expires_in | scopes, GivenValue :: term()
    }}
    | no_supported_code_challenge
    | oidcc_jwt_util:error()
    | oidcc_http_util:error().

-telemetry_event(#{
    event => [oidcc, request_token, start],
    description => <<"Emitted at the start of requesting a code token">>,
    measurements => <<"#{system_time => non_neg_integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, request_token, stop],
    description => <<"Emitted at the end of requesting a code token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, request_token, exception],
    description => <<"Emitted at the end of requesting a code token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, refresh_token, start],
    description => <<"Emitted at the start of refreshing a token">>,
    measurements => <<"#{system_time => non_neg_integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, refresh_token, stop],
    description => <<"Emitted at the end of refreshing a token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, refresh_token, exception],
    description => <<"Emitted at the end of refreshing a token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, jwt_profile_token, start],
    description => <<"Emitted at the start of exchanging a JWT profile token">>,
    measurements => <<"#{system_time => non_neg_integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, jwt_profile_token, stop],
    description => <<"Emitted at the end of exchanging a JWT profile token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, jwt_profile_token, exception],
    description => <<"Emitted at the end of exchanging a JWT profile token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, client_credentials, start],
    description => <<"Emitted at the start of exchanging a client credentials token">>,
    measurements => <<"#{system_time => non_neg_integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, client_credentials, stop],
    description => <<"Emitted at the end of exchanging a client credentials token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-telemetry_event(#{
    event => [oidcc, client_credentials, exception],
    description => <<"Emitted at the end of exchanging a client credentials token">>,
    measurements => <<"#{duration => integer(), monotonic_time => integer()}">>,
    metadata => <<"#{issuer => uri_string:uri_string(), client_id => binary()}">>
}).

-doc """
Retrieve the token using the authcode received before and directly validate
the result.

The authcode was sent to the local endpoint by the OpenId Connect provider,
using redirects.

For a high level interface using `m:oidcc_provider_configuration_worker`
see `oidcc:retrieve_token/5`.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

%% Get AuthCode from Redirect

{ok, #oidcc_token{}} =
  oidcc:retrieve(AuthCode, ClientContext, #{
    redirect_uri => <<"https://example.com/callback">>}).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec retrieve(AuthCode, ClientContext, Opts) ->
    {ok, t()} | {error, error()}
when
    AuthCode :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts().
retrieve(AuthCode, ClientContext, Opts) ->
    case retrieve_with_refresh(AuthCode, ClientContext, Opts) of
        {ok, Token, _Info} -> {ok, Token};
        {error, Reason} -> {error, Reason}
    end.

-doc """
Retrieve the token, reporting what a JWKS refresh fetched.

Same as `retrieve/3`, but the third element carries whatever the `refresh_jwks`
function returned alongside the refreshed keys, or `undefined` when no refresh
happened. A function using the two element `{ok, Jwks}` return reports nothing.

`oidcc` refreshes the keys and retries validation without re-sending the
authorization code, which is single use, so this is the only way to learn what
that refresh fetched. Persisting the refreshed key set is the usual reason to
want it.

## Examples

```erlang
RefreshJwks = fun(_OldJwks, _Kid) ->
    {ok, {Jwks, Expiry, Document}} = oidcc_provider_configuration:load_jwks_raw(JwksUri, #{}),
    {ok, Jwks, {Document, Expiry}}
end,

{ok, #oidcc_token{}, {Document, Expiry}} =
    oidcc_token:retrieve_with_refresh(AuthCode, ClientContext, Opts#{refresh_jwks => RefreshJwks}).
```
""".
-doc #{since => <<"3.9.0">>}.
-spec retrieve_with_refresh(AuthCode, ClientContext, Opts) ->
    {ok, t(), refresh_info()} | {error, error()}
when
    AuthCode :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts().
retrieve_with_refresh(AuthCode, ClientContext, Opts) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        client_id = ClientId
    } = ClientContext,
    #oidcc_provider_configuration{issuer = Issuer, grant_types_supported = GrantTypesSupported} =
        Configuration,

    case lists:member(<<"authorization_code">>, GrantTypesSupported) of
        true ->
            QsBody =
                [
                    {<<"grant_type">>, <<"authorization_code">>},
                    {<<"code">>, AuthCode},
                    {<<"redirect_uri">>, maps:get(redirect_uri, Opts)}
                ],

            TelemetryOpts = #{
                topic => [oidcc, request_token],
                extra_meta => #{issuer => Issuer, client_id => ClientId}
            },

            maybe
                {ok, Token} ?=
                    retrieve_a_token(
                        QsBody, ClientContext, Opts, TelemetryOpts, true
                    ),
                extract_response(Token, ClientContext, Opts)
            end;
        false ->
            {error, {grant_type_not_supported, authorization_code}}
    end.

-doc """
Validate the JARM response, returning the valid claims as a map.

The response was sent to the local endpoint by the OpenId Connect provider,
using redirects.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

%% Get Response from Redirect

{ok, #{<<"code">> := AuthCode}} =
  oidcc:validate_jarm(Response, ClientContext, #{}),

{ok, #oidcc_token{}} = oidcc:retrieve(AuthCode, ClientContext,
  #{redirect_uri => <<"https://redirect.example/">>}).
```
""".
-doc #{since => <<"3.2.0">>}.
-spec validate_jarm(Response, ClientContext, Opts) ->
    {ok, oidcc_jwt_util:claims()} | {error, error()}
when
    Response :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: validate_jarm_opts().
validate_jarm(Response, ClientContext, Opts) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        client_id = ClientId,
        client_secret = ClientSecret,
        client_jwks = ClientJwks,
        jwks = Jwks0
    } = ClientContext,
    #oidcc_provider_configuration{
        issuer = Issuer,
        authorization_signing_alg_values_supported = SigningAlgSupported,
        authorization_encryption_alg_values_supported = EncryptionAlgSupported,
        authorization_encryption_enc_values_supported = EncryptionEncSupported
    } =
        Configuration,

    Jwks1 =
        case ClientJwks of
            none -> Jwks0;
            #jose_jwk{} -> oidcc_jwt_util:merge_jwks(Jwks0, ClientJwks)
        end,

    Jwks2 = oidcc_jwt_util:merge_client_secret_oct_keys(Jwks1, SigningAlgSupported, ClientSecret),
    Jwks = oidcc_jwt_util:merge_client_secret_oct_keys(
        Jwks2, EncryptionAlgSupported, ClientSecret
    ),
    ExpClaims = [{<<"iss">>, Issuer}],
    TrustedAudiences = maps:get(trusted_audiences, Opts, any),
    %% https://openid.net/specs/oauth-v2-jarm-final.html#name-processing-rules
    %% 1. decrypt if necessary
    %% 2. validate <<"iss">> claim
    %% 3. validate <<"aud">> claim
    %% 4. validate <<"exp">> claim
    %% 5. validate signature (valid, not <<"none">> alg, not encrypted only)
    %% 6. continue processing
    maybe
        {ok, {#jose_jwt{fields = Claims}, Jws, _Jwk}} ?=
            oidcc_jwt_util:decrypt_and_verify(
                Response, Jwks, SigningAlgSupported, EncryptionAlgSupported, EncryptionEncSupported
            ),
        ok ?= oidcc_jwt_util:verify_claims(Claims, ExpClaims),
        ok ?= verify_aud_claim(Claims, ClientId, TrustedAudiences),
        ok ?= verify_exp_claim(Claims),
        ok ?= verify_nbf_claim(Claims),
        ok ?= oidcc_jwt_util:verify_not_none_alg(Jws),
        {ok, Claims}
    end.

-doc """
Refresh Token

For a high level interface using `m:oidcc_provider_configuration_worker`
see `oidcc:refresh_token/5`.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

%% Get AuthCode from Redirect

{ok, Token} =
  oidcc_token:retrieve(AuthCode, ClientContext, #{
    redirect_uri => <<"https://example.com/callback">>}).

%% Later

{ok, #oidcc_token{}} =
  oidcc_token:refresh(Token,
                      ClientContext,
                      #{expected_subject => <<"sub_from_initial_id_token">>}).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec refresh
    (RefreshToken, ClientContext, Opts) ->
        {ok, t()} | {error, error()}
    when
        RefreshToken :: binary(),
        ClientContext :: oidcc_client_context:t(),
        Opts :: refresh_opts();
    (Token, ClientContext, Opts) ->
        {ok, t()} | {error, error()}
    when
        Token :: oidcc_token:t(),
        ClientContext :: oidcc_client_context:t(),
        Opts :: refresh_opts_no_sub().
refresh(
    #oidcc_token{
        refresh = #oidcc_token_refresh{token = RefreshToken},
        id = #oidcc_token_id{claims = #{<<"sub">> := ExpectedSubject}}
    },
    ClientContext,
    Opts
) ->
    refresh(RefreshToken, ClientContext, maps:put(expected_subject, ExpectedSubject, Opts));
refresh(RefreshToken, ClientContext, Opts) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        client_id = ClientId
    } = ClientContext,
    #oidcc_provider_configuration{issuer = Issuer, grant_types_supported = GrantTypesSupported} =
        Configuration,

    case lists:member(<<"refresh_token">>, GrantTypesSupported) of
        true ->
            ExpectedSub = maps:get(expected_subject, Opts),
            Scope = maps:get(scope, Opts, []),
            QueryString =
                [{<<"refresh_token">>, RefreshToken}, {<<"grant_type">>, <<"refresh_token">>}],
            QueryString1 = oidcc_scope:query_append_scope(Scope, QueryString),

            TelemetryOpts = #{
                topic => [oidcc, refresh_token],
                extra_meta => #{issuer => Issuer, client_id => ClientId}
            },

            maybe
                {ok, Token} ?=
                    retrieve_a_token(QueryString1, ClientContext, Opts, TelemetryOpts, true),
                {ok, TokenRecord, _Info} ?=
                    extract_response(Token, ClientContext, maps:put(nonce, any, Opts)),
                case TokenRecord of
                    #oidcc_token{id = #oidcc_token_id{claims = #{<<"sub">> := ExpectedSub}}} ->
                        {ok, TokenRecord};
                    #oidcc_token{} ->
                        {error, sub_invalid}
                end
            end;
        false ->
            {error, {grant_type_not_supported, refresh_token}}
    end.

-doc """
Retrieve JSON Web Token (JWT) Profile Token

See [https://datatracker.ietf.org/doc/html/rfc7523#section-4]

For a high level interface using {@link oidcc_provider_configuration_worker}
see {@link oidcc:jwt_profile_token/6}.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

{ok, KeyJson} = file:read_file("jwt-profile.json"),
KeyMap = json:decode(KeyJson),
Key = jose_jwk:from_pem(maps:get(<<"key">>, KeyMap)),

{ok, #oidcc_token{}} =
  oidcc_token:jwt_profile(<<"subject">>,
                          ClientContext,
                          Key,
                          #{scope => [<<"scope">>],
                            kid => maps:get(<<"keyId">>, KeyMap)}).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec jwt_profile(Subject, ClientContext, Jwk, Opts) -> {ok, t()} | {error, error()} when
    Subject :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Jwk :: jose_jwk:key(),
    Opts :: jwt_profile_opts().
jwt_profile(Subject, ClientContext, Jwk, Opts) ->
    #oidcc_client_context{provider_configuration = Configuration, client_id = ClientId} =
        ClientContext,
    #oidcc_provider_configuration{issuer = Issuer, grant_types_supported = GrantTypesSupported} =
        Configuration,

    case lists:member(<<"urn:ietf:params:oauth:grant-type:jwt-bearer">>, GrantTypesSupported) of
        true ->
            Iat = os:system_time(seconds),
            Exp = Iat + 60,

            AssertionClaims = #{
                <<"iss">> => Subject,
                <<"sub">> => Subject,
                <<"aud">> => [Issuer],
                <<"exp">> => Exp,
                <<"iat">> => Iat,
                <<"nbf">> => Iat
            },
            AssertionJwt = jose_jwt:from(AssertionClaims),

            AssertionJws0 = #{
                <<"alg">> => <<"RS256">>,
                <<"typ">> => <<"JWT">>
            },
            AssertionJws =
                case maps:get(kid, Opts, none) of
                    none -> AssertionJws0;
                    Kid -> maps:put(<<"kid">>, Kid, AssertionJws0)
                end,

            {_Jws, Assertion} = jose_jws:compact(jose_jwt:sign(Jwk, AssertionJws, AssertionJwt)),

            Scope = maps:get(scope, Opts, []),
            QueryString =
                [
                    {<<"assertion">>, Assertion},
                    {<<"grant_type">>, <<"urn:ietf:params:oauth:grant-type:jwt-bearer">>}
                ],
            QueryString1 = oidcc_scope:query_append_scope(Scope, QueryString),

            TelemetryOpts = #{
                topic => [oidcc, jwt_profile_token],
                extra_meta => #{issuer => Issuer, client_id => ClientId}
            },

            maybe
                {ok, Token} ?=
                    retrieve_a_token(QueryString1, ClientContext, Opts, TelemetryOpts, false),
                {ok, TokenRecord, _Info} ?=
                    extract_response(Token, ClientContext, maps:put(nonce, any, Opts)),
                case TokenRecord of
                    #oidcc_token{id = none} ->
                        {ok, TokenRecord};
                    #oidcc_token{id = #oidcc_token_id{claims = #{<<"sub">> := Subject}}} ->
                        {ok, TokenRecord};
                    #oidcc_token{} ->
                        {error, sub_invalid}
                end
            end;
        false ->
            {error, {grant_type_not_supported, jwt_bearer}}
    end.

-doc """
Retrieve Client Credential Token

See https://datatracker.ietf.org/doc/html/rfc6749#section-1.3.4

For a high level interface using `m:oidcc_provider_configuration_worker`
see `oidcc:client_credentials_token/4`.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

{ok, #oidcc_token{}} =
  oidcc_token:client_credentials(ClientContext,
                                 #{scope => [<<"scope">>]}).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec client_credentials(ClientContext, Opts) -> {ok, t()} | {error, error()} when
    ClientContext :: oidcc_client_context:authenticated_t(),
    Opts :: client_credentials_opts().
client_credentials(ClientContext, Opts) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        client_id = ClientId
    } = ClientContext,
    #oidcc_provider_configuration{issuer = Issuer, grant_types_supported = GrantTypesSupported} =
        Configuration,

    case lists:member(<<"client_credentials">>, GrantTypesSupported) of
        true ->
            Scope = maps:get(scope, Opts, []),
            QueryString = [{<<"grant_type">>, <<"client_credentials">>}],
            QueryString1 = oidcc_scope:query_append_scope(Scope, QueryString),

            TelemetryOpts = #{
                topic => [oidcc, client_credentials],
                extra_meta => #{issuer => Issuer, client_id => ClientId}
            },

            maybe
                {ok, Token} ?=
                    retrieve_a_token(QueryString1, ClientContext, Opts, TelemetryOpts, true),
                {ok, TokenRecord, _Info} ?=
                    extract_response(Token, ClientContext, maps:put(nonce, any, Opts)),
                {ok, TokenRecord}
            end;
        false ->
            {error, {grant_type_not_supported, client_credentials}}
    end.

-spec extract_response(TokenResponseBody, ClientContext, Opts) ->
    {ok, t(), refresh_info()} | {error, error()}
when
    TokenResponseBody :: map(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts().
extract_response(TokenResponseBody, ClientContext, Opts) ->
    maybe
        {ok, Scopes} ?= extract_scope(TokenResponseBody, Opts),
        {ok, AccessExpire} ?= extract_expiry(TokenResponseBody),
        {ok, AccessTokenRecord} ?= extract_access_token(TokenResponseBody, AccessExpire),
        {ok, RefreshTokenRecord} ?= extract_refresh_token(TokenResponseBody),
        {ok, {IdTokenRecord, IdTokenJwk, NoneUsed}, Info} ?=
            extract_id_token(TokenResponseBody, ClientContext, Opts),
        TokenRecord = #oidcc_token{
            id = IdTokenRecord,
            access = AccessTokenRecord,
            refresh = RefreshTokenRecord,
            scope = Scopes
        },
        ok ?= verify_access_token_map_hash(TokenRecord, IdTokenJwk),
        %% If none alg was used, continue with checks to allow the user to decide
        %% if he wants to use the result
        case NoneUsed of
            true ->
                {error, {none_alg_used, TokenRecord}};
            false ->
                {ok, TokenRecord, Info}
        end
    end.

-spec extract_scope(TokenMap, Opts) -> {ok, oidcc_scope:scopes()} | {error, error()} when
    TokenMap :: map(), Opts :: retrieve_opts().
extract_scope(TokenMap, Opts) ->
    Scopes = maps:get(scope, Opts, []),
    case maps:get(<<"scope">>, TokenMap, oidcc_scope:scopes_to_bin(Scopes)) of
        ScopeBinary when is_binary(ScopeBinary) ->
            {ok, oidcc_scope:parse(ScopeBinary)};
        %% Some providers (e.g. Apple and Twitch) are setting the scope value
        %% as list of string. This extends compatibility for those.
        ScopeList when is_list(ScopeList) ->
            {ok, ScopeList};
        ScopeOther ->
            {error, {invalid_property, {scope, ScopeOther}}}
    end.

-spec extract_expiry(TokenMap) -> {ok, undefined | integer()} | {error, error()} when
    TokenMap :: map().
extract_expiry(TokenMap) ->
    case maps:get(<<"expires_in">>, TokenMap, undefined) of
        undefined ->
            {ok, undefined};
        ExpiresInNum when is_integer(ExpiresInNum) ->
            {ok, ExpiresInNum};
        ExpiresInBinary when is_binary(ExpiresInBinary) ->
            try
                {ok, binary_to_integer(ExpiresInBinary)}
            catch
                error:badarg ->
                    {error, {invalid_property, {expires_in, ExpiresInBinary}}}
            end;
        ExpiresInOther ->
            {error, {invalid_property, {expires_in, ExpiresInOther}}}
    end.

-spec extract_access_token(TokenMap, Expiry) -> {ok, access()} | {error, error()} when
    TokenMap :: map(),
    Expiry :: integer().
extract_access_token(TokenMap, Expiry) ->
    case maps:get(<<"access_token">>, TokenMap, none) of
        none ->
            {ok, none};
        Token when is_binary(Token) ->
            TokenType = maps:get(<<"token_type">>, TokenMap, <<"Bearer">>),
            {ok, #oidcc_token_access{token = Token, expires = Expiry, type = TokenType}};
        Other ->
            {error, {invalid_property, {access_token, Other}}}
    end.

-spec extract_refresh_token(TokenMap) -> {ok, refresh()} | {error, error()} when
    TokenMap :: map().
extract_refresh_token(TokenMap) ->
    case maps:get(<<"refresh_token">>, TokenMap, none) of
        none ->
            {ok, none};
        Token when is_binary(Token) ->
            {ok, #oidcc_token_refresh{token = Token}};
        Other ->
            {error, {invalid_property, {refresh_token, Other}}}
    end.

-spec extract_id_token(TokenMap, ClientContext, Opts) ->
    {ok, {TokenRecord, Jwk, NoneUsed}, refresh_info()} | {error, error()}
when
    TokenMap :: map(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts(),
    TokenRecord :: id() | none,
    Jwk :: jose_jwk:key() | none,
    NoneUsed :: boolean().
extract_id_token(TokenMap, ClientContext, Opts) ->
    case maps:get(<<"id_token">>, TokenMap, none) of
        none ->
            {ok, {none, none, false}, undefined};
        Token when is_binary(Token) ->
            case validate_id_token_with_refresh(Token, ClientContext, Opts) of
                {ok, {OkClaims, Jwk}, Info} ->
                    {ok, {#oidcc_token_id{token = Token, claims = OkClaims}, Jwk, false}, Info};
                {error, {none_alg_used, NoneClaims}} ->
                    {ok, {#oidcc_token_id{token = Token, claims = NoneClaims}, none, true},
                        undefined};
                {error, Reason} ->
                    {error, Reason}
            end;
        Other ->
            {error, {invalid_property, {id_token, Other}}}
    end.

-spec verify_access_token_map_hash(TokenRecord, Jwk) ->
    ok | {error, error()}
when
    TokenRecord :: t(),
    Jwk :: jose_jwk:key() | none.
verify_access_token_map_hash(
    #oidcc_token{
        id =
            #oidcc_token_id{
                token = IdToken,
                claims =
                    #{<<"at_hash">> := ExpectedHash}
            },
        access = #oidcc_token_access{token = AccessToken}
    },
    Jwk
) ->
    maybe
        {ok, Digest} ?= id_token_hash_digest(IdToken, Jwk),
        %% The hash is truncated to its left-most half, the length of which
        %% depends on the digest used. For SHA-256 this is the left-most 128
        %% bits.
        %% See https://openid.net/specs/openid-connect-core-1_0.html#CodeIDToken
        Hash = crypto:hash(Digest, AccessToken),
        BinHash = binary:part(Hash, 0, byte_size(Hash) div 2),
        case base64:encode(BinHash, #{mode => urlsafe, padding => false}) of
            ExpectedHash ->
                ok;
            _Other ->
                {error, bad_access_token_hash}
        end
    end;
verify_access_token_map_hash(#oidcc_token{}, _Jwk) ->
    ok.

%% Digest to use for the `at_hash' claim of the given ID token.
%%
%% The digest is derived from the `alg' header of the ID token, which has
%% already been checked against the allowed signing algorithms when the
%% signature was verified.
%%
%% `EdDSA' does not name a digest, so it is derived from the curve of the key
%% the token was signed with.
-spec id_token_hash_digest(IdToken, Jwk) ->
    {ok, crypto:sha2()} | {error, oidcc_jwt_util:error()}
when
    IdToken :: binary(),
    Jwk :: jose_jwk:key() | none.
id_token_hash_digest(_IdToken, none) ->
    %% Encrypted without a nested signature, or the `none' algorithm was used:
    %% there is no signing algorithm to derive a digest from, so an `at_hash'
    %% cannot be verified.
    {error, {unsupported_signing_alg, undefined}};
id_token_hash_digest(IdToken, Jwk) ->
    #jose_jws{alg = {_Module, Alg}} = jose_jwt:peek_protected(IdToken),
    oidcc_jwt_util:signing_alg_to_digest(Alg, Jwk).

-doc """
Validate ID Token

Usually the id token is validated using `retrieve/3`.

If you get the token passed from somewhere else, this function can validate it.

## Validations

* `iss` claim must match the issuer of the provider, or match the regex pattern if `issuer_regex` is configured in quirks.
* `nonce` claim must match the `nonce` option.
* `aud` claim must match the `trusted_audiences` option.
* `exp` claim must be in the future.
* `nbf` claim must be in the past.
* `azp` claim must match the client id by default. This can be disabled by setting the `validate_azp` option to `any`.
  If the `validate_azp` option is set to a `binary()` or a list of binaries, the `azp` claim must match one of those values.

## Examples

```erlang
{ok, ClientContext} =
  oidcc_client_context:from_configuration_worker(provider_name,
                                                 <<"client_id">>,
                                                 <<"client_secret">>),

%% Get IdToken from somewhere

{ok, Claims} =
  oidcc:validate_id_token(IdToken, ClientContext, ExpectedNonce).
```

## Regex Issuer Validation

You can use a regex pattern to validate the issuer claim by adding an `issuer_regex`
to the quirks map when creating the provider configuration. See the documentation for `validate_jwt/3`
for more details.
""".
-doc #{since => <<"3.0.0">>}.
-spec validate_id_token(IdToken, ClientContext, NonceOrOpts) ->
    {ok, Claims} | {error, error()}
when
    IdToken :: binary(),
    ClientContext :: oidcc_client_context:t(),
    NonceOrOpts :: Nonce | retrieve_opts(),
    Nonce :: binary() | any,
    Claims :: oidcc_jwt_util:claims().
validate_id_token(IdToken, ClientContext, Nonce) when is_binary(Nonce) ->
    validate_id_token(IdToken, ClientContext, #{nonce => Nonce});
validate_id_token(IdToken, ClientContext, any) ->
    validate_id_token(IdToken, ClientContext, #{nonce => any});
validate_id_token(IdToken, ClientContext, Opts) when is_map(Opts) ->
    case validate_id_token_with_refresh(IdToken, ClientContext, Opts) of
        {ok, {Claims, _Jwk}, _Info} -> {ok, Claims};
        {error, Reason} -> {error, Reason}
    end.

-spec validate_id_token_with_refresh(IdToken, ClientContext, Opts) ->
    {ok, {Claims, jose_jwk:key() | none}, refresh_info()} | {error, error()}
when
    IdToken :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts(),
    Claims :: oidcc_jwt_util:claims().
validate_id_token_with_refresh(IdToken, ClientContext, Opts) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        client_id = ClientId
    } =
        ClientContext,
    #oidcc_provider_configuration{
        id_token_signing_alg_values_supported = AllowAlgorithms,
        id_token_encryption_alg_values_supported = EncryptionAlgs,
        id_token_encryption_enc_values_supported = EncryptionEncs
    } =
        Configuration,

    ValidateOpts = maps:merge(Opts, #{
        signing_algs => AllowAlgorithms,
        encryption_algs => EncryptionAlgs,
        encryption_encs => EncryptionEncs
    }),

    Nonce = maps:get(nonce, Opts, any),

    ExpClaims =
        case Nonce of
            any -> [];
            Bin when is_binary(Bin) -> [{<<"nonce">>, Nonce}]
        end,

    ValidateAzp =
        case maps:get(validate_azp, Opts, client_id) of
            client_id -> [ClientId];
            any -> any;
            Binary when is_binary(Binary) -> [Binary];
            List when is_list(List) -> List
        end,

    validate_jwt_with_refresh(IdToken, ClientContext, ValidateOpts, fun(Claims) ->
        maybe
            ok ?= oidcc_jwt_util:verify_claims(Claims, ExpClaims),
            ok ?= verify_missing_required_claims(Claims),
            ok ?= verify_azp_claim(Claims, ValidateAzp),
            ok
        end
    end).

-doc """
Validate JWT

Validates a generic JWT (such as an access token) from the given provider.
Useful if the issuer is shared between multiple applications, and the access token
generated for a user at one client is used to validate their access at another client.

Validating an arbitrary JWT token (not an ID token) is not covered by the OpenID
Connect specification. Therefore the signing / encryption algorithms are not
derieved from the provider configuration, but must be provided by the caller.

## Validations

* `iss` claim must match the issuer of the provider, or match the regex pattern if `issuer_regex` is configured in quirks.
* `aud` claim must match the `trusted_audiences` option.
* `exp` claim must be in the future.
* `nbf` claim must be in the past.

## Examples

```erlang
{ok, ClientContext} =
    oidcc_client_context:from_configuration_worker(provider_name,
                                                <<"client_id">>,
                                                <<"client_secret">>),
%% Get Jwt from Authorization header
Jwt = <<"jwt">>,

Opts = #{
  signing_algs => [<<"RS256">>]
},

{ok, Claims} =
    oidcc:validate_jwt(Jwt, ClientContext, Opts).
```

## Regex Issuer Validation

You can use a regex pattern to validate the issuer claim by adding an `issuer_regex`
to the quirks map when creating the provider configuration:

```erlang
{ok, {ProviderConfig, _}} =
    oidcc_provider_configuration:load_configuration(Issuer, #{
        quirks => #{
            issuer_regex => <<"^https://accounts\\.example\\.com/[a-z0-9]+">>
        }
    }),
```

This will allow tokens with issuer claims that match the regex pattern to validate successfully.
""".
-doc #{since => <<"3.2.0">>}.
-spec validate_jwt(Token, ClientContext, Opts) ->
    {ok, Claims} | {error, error()}
when
    Token :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: validate_jwt_opts(),
    Claims :: oidcc_jwt_util:claims().
validate_jwt(Token, ClientContext, Opts) when is_map(Opts) ->
    validate_jwt(Token, ClientContext, Opts, fun(_Claims) -> ok end).

-spec validate_jwt(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    {ok, Claims} | {error, error()}
when
    Token :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: validate_jwt_opts(),
    Claims :: oidcc_jwt_util:claims(),
    AdditionalClaimValidation :: fun((Claims) -> ok | {error, error()}).
validate_jwt(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    case validate_jwt_with_refresh(Token, ClientContext, Opts, AdditionalClaimValidation) of
        {ok, {Claims, _Jwk}, _Info} -> {ok, Claims};
        {error, Reason} -> {error, Reason}
    end.

-spec validate_jwt_with_refresh(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    {ok, {Claims, jose_jwk:key() | none}, refresh_info()} | {error, error()}
when
    Token :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: validate_jwt_opts(),
    Claims :: oidcc_jwt_util:claims(),
    AdditionalClaimValidation :: fun((Claims) -> ok | {error, error()}).
validate_jwt_with_refresh(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    RefreshJwksFun = maps:get(refresh_jwks, Opts, undefined),
    unknown_kid_retry(
        fun(RefreshedClientContext) ->
            int_validate_jwt(
                Token, RefreshedClientContext, Opts, AdditionalClaimValidation
            )
        end,
        ClientContext,
        RefreshJwksFun
    ).

-spec int_validate_jwt(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    {ok, {Claims, jose_jwk:key() | none}} | {error, error()}
when
    Token :: binary(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: validate_jwt_opts(),
    Claims :: oidcc_jwt_util:claims(),
    AdditionalClaimValidation :: fun((Claims) -> ok | {error, error()}).
int_validate_jwt(Token, ClientContext, Opts, AdditionalClaimValidation) ->
    #oidcc_client_context{
        provider_configuration = Configuration,
        jwks = #jose_jwk{} = Jwks0,
        client_id = ClientId,
        client_secret = ClientSecret,
        client_jwks = ClientJwks
    } =
        ClientContext,
    #oidcc_provider_configuration{
        issuer = Issuer,
        issuer_regex = IssuerRegex
    } =
        Configuration,

    SigningAlgs = maps:get(signing_algs, Opts, []),
    EncryptionAlgs = maps:get(encryption_algs, Opts, []),
    EncryptionEncs = maps:get(encryption_encs, Opts, []),

    case {SigningAlgs, EncryptionAlgs} of
        {[], []} ->
            error(badarg, [Token, ClientContext, Opts], []);
        _ ->
            ok
    end,

    Jwks1 =
        case ClientJwks of
            none -> Jwks0;
            #jose_jwk{} -> oidcc_jwt_util:merge_jwks(Jwks0, ClientJwks)
        end,
    Jwks2 = oidcc_jwt_util:merge_client_secret_oct_keys(Jwks1, SigningAlgs, ClientSecret),
    Jwks = oidcc_jwt_util:merge_client_secret_oct_keys(Jwks2, EncryptionAlgs, ClientSecret),
    TrustedAudiences = maps:get(trusted_audiences, Opts, any),

    maybe
        {ok, {#jose_jwt{fields = Claims}, Jws, Jwk}} ?=
            rescue_none_validated_jwt(
                oidcc_jwt_util:decrypt_and_verify(
                    Token, Jwks, SigningAlgs, EncryptionAlgs, EncryptionEncs
                )
            ),
        ExpectedClaims =
            case IssuerRegex of
                undefined ->
                    [{<<"iss">>, Issuer}];
                Pattern ->
                    [{<<"iss">>, {regex, Pattern}}]
            end,
        ok ?= oidcc_jwt_util:verify_claims(Claims, ExpectedClaims),
        ok ?= verify_missing_required_claims(Claims),
        ok ?= verify_aud_claim(Claims, ClientId, TrustedAudiences),
        ok ?= verify_exp_claim(Claims),
        ok ?= verify_nbf_claim(Claims),
        ok ?= AdditionalClaimValidation(Claims),
        case Jws of
            #jose_jws{alg = {jose_jws_alg_none, none}} ->
                {error, {none_alg_used, Claims}};
            #jose_jws{} ->
                {ok, {Claims, Jwk}};
            #jose_jwe{} ->
                %% Encrypted without a nested signature: "If the ID Token is
                %% encrypted, it MUST be signed then encrypted, with the result
                %% being a Nested JWT."
                %% https://openid.net/specs/openid-connect-core-1_0.html#IDToken
                {error, signature_required}
        end
    end.

-doc """
Authorization headers

Generate a map of authorization headers to use when using the given
access token to access an API endpoint.

## Examples

```erlang
{ok, ClientContext} =
    oidcc_client_context:from_configuration_worker(provider_name,
                                                    <<"client_id">>,
                                                    <<"client_secret">>),
%% Get Access Token record from somewhere
Headers =
    oidcc:authorization_headers(AccessTokenRecord, :get, Url, ClientContext).
```
""".
-doc #{since => "3.2.0"}.
-spec authorization_headers(AccessTokenRecord, Method, Endpoint, ClientContext) -> HeaderMap when
    AccessTokenRecord :: access(),
    Method :: post | get,
    Endpoint :: uri_string:uri_string(),
    ClientContext :: oidcc_client_context:t(),
    HeaderMap :: #{binary() => binary()}.
-spec authorization_headers(AccessTokenRecord, Method, Endpoint, ClientContext, Opts) ->
    HeaderMap
when
    AccessTokenRecord :: access(),
    Method :: post | get,
    Endpoint :: uri_string:uri_string(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: authorization_headers_opts(),
    HeaderMap :: #{binary() => binary()}.
authorization_headers(AccessTokenRecord, Method, Endpoint, ClientContext) ->
    authorization_headers(AccessTokenRecord, Method, Endpoint, ClientContext, #{}).

authorization_headers(
    #oidcc_token_access{} = AccessTokenRecord,
    Method,
    Endpoint,
    #oidcc_client_context{} = ClientContext,
    Opts
) ->
    #oidcc_token_access{token = AccessToken, type = AccessTokenType} = AccessTokenRecord,
    Header = oidcc_auth_util:add_authorization_header(
        AccessToken, AccessTokenType, Method, Endpoint, Opts, ClientContext
    ),
    maps:from_list([{list_to_binary(Key), list_to_binary([Value])} || {Key, Value} <- Header]).

-spec verify_aud_claim(Claims, ClientId, TrustedAudiences) -> ok | {error, error()} when
    Claims :: oidcc_jwt_util:claims(), ClientId :: binary(), TrustedAudiences :: [binary()] | any.
verify_aud_claim(#{<<"aud">> := ClientId}, ClientId, _TrustedAudiences) ->
    ok;
verify_aud_claim(#{<<"aud">> := Audience} = Claims, ClientId, any) when is_list(Audience) ->
    case lists:member(ClientId, Audience) of
        true -> ok;
        false -> {error, {missing_claim, {<<"aud">>, ClientId}, Claims}}
    end;
verify_aud_claim(#{<<"aud">> := Audience} = Claims, ClientId, TrustedAudiences0) when
    is_list(Audience)
->
    TrustedAudiences = [ClientId | TrustedAudiences0],
    maybe
        true ?= lists:member(ClientId, Audience),
        [] ?= [A || A <- Audience, not lists:member(A, TrustedAudiences)],
        ok
    else
        _ -> {error, {missing_claim, {<<"aud">>, ClientId}, Claims}}
    end;
verify_aud_claim(Claims, ClientId, _TrustedAudiences) ->
    {error, {missing_claim, {<<"aud">>, ClientId}, Claims}}.

-spec verify_azp_claim(Claims, Mode) -> ok | {error, error()} when
    Claims :: oidcc_jwt_util:claims(), Mode :: [binary()] | any.
verify_azp_claim(_Claims, any) ->
    ok;
verify_azp_claim(#{<<"azp">> := Azp}, AllowedAzp) when is_list(AllowedAzp) ->
    case lists:member(Azp, AllowedAzp) of
        true -> ok;
        false -> {error, {missing_claim, {<<"azp">>, AllowedAzp}, #{<<"azp">> => Azp}}}
    end;
verify_azp_claim(_, _Mode) ->
    ok.

-spec verify_exp_claim(Claims) -> ok | {error, error()} when Claims :: oidcc_jwt_util:claims().
verify_exp_claim(#{<<"exp">> := Expiry}) ->
    MaxClockSkew =
        case application:get_env(oidcc, max_clock_skew) of
            undefined -> 0;
            {ok, ClockSkew} -> ClockSkew
        end,
    case erlang:system_time(second) > Expiry + MaxClockSkew of
        true -> {error, token_expired};
        false -> ok
    end;
verify_exp_claim(Claims) ->
    {error, {missing_claim, <<"exp">>, Claims}}.

-spec verify_nbf_claim(Claims) -> ok | {error, error()} when Claims :: oidcc_jwt_util:claims().
verify_nbf_claim(#{<<"nbf">> := Expiry}) ->
    MaxClockSkew =
        case application:get_env(oidcc, max_clock_skew) of
            undefined -> 0;
            {ok, ClockSkew} -> ClockSkew
        end,
    case erlang:system_time(second) < Expiry - MaxClockSkew of
        true -> {error, token_not_yet_valid};
        false -> ok
    end;
verify_nbf_claim(_Claims) ->
    ok.

-spec verify_missing_required_claims(Claims) -> ok | {error, error()} when
    Claims :: oidcc_jwt_util:claims().
verify_missing_required_claims(Claims) ->
    Required = [<<"iss">>, <<"sub">>, <<"aud">>, <<"exp">>, <<"iat">>],
    CheckKeys = fun(Key, _Val, Acc) -> lists:delete(Key, Acc) end,
    case maps:fold(CheckKeys, Required, Claims) of
        [] ->
            ok;
        [MissingClaim | _Rest] ->
            {error, {missing_claim, MissingClaim, Claims}}
    end.

-spec retrieve_a_token(
    QsBodyIn, ClientContext, Opts, TelemetryOpts, AuthenticateClient
) ->
    {ok, map()} | {error, error()}
when
    QsBodyIn :: oidcc_http_util:query_params(),
    ClientContext :: oidcc_client_context:t(),
    Opts :: retrieve_opts() | refresh_opts(),
    TelemetryOpts :: oidcc_http_util:telemetry_opts(),
    AuthenticateClient :: boolean().
retrieve_a_token(QsBodyIn, ClientContext, Opts, TelemetryOpts, AuthenticateClient) ->
    #oidcc_client_context{provider_configuration = Configuration} =
        ClientContext,
    #oidcc_provider_configuration{
        token_endpoint = TokenEndpoint0,
        token_endpoint_auth_methods_supported = SupportedAuthMethods0,
        token_endpoint_auth_signing_alg_values_supported = SigningAlgs
    } =
        Configuration,

    QueryParams = maps:get(url_extension, Opts, []),

    Header0 = [{"accept", "application/jwt, application/json"}],

    QsBody0 = QsBodyIn ++ maps:get(body_extension, Opts, []),

    SupportedAuthMethods =
        case AuthenticateClient of
            true -> SupportedAuthMethods0;
            false -> [<<"none">>]
        end,

    DpopOpts =
        case Opts of
            #{dpop_nonce := DpopNonce} ->
                #{nonce => DpopNonce};
            _ ->
                #{}
        end,
    maybe
        {ok, QsBody} ?= add_pkce_verifier(QsBody0, Opts, ClientContext),
        {ok, {Body, Header1}, AuthMethod} ?=
            oidcc_auth_util:add_client_authentication(
                QsBody, Header0, SupportedAuthMethods, SigningAlgs, Opts, ClientContext
            ),
        TokenEndpoint = oidcc_auth_util:maybe_mtls_endpoint(
            TokenEndpoint0, AuthMethod, <<"token_endpoint">>, ClientContext
        ),
        Endpoint =
            case QueryParams of
                [] -> TokenEndpoint;
                _ -> [TokenEndpoint, <<"?">>, uri_string:compose_query(QueryParams)]
            end,
        Header = oidcc_auth_util:add_dpop_proof_header(
            Header1, post, Endpoint, DpopOpts, ClientContext
        ),
        Request =
            {Endpoint, Header, "application/x-www-form-urlencoded", uri_string:compose_query(Body)},
        RequestOpts = maps:get(request_opts, Opts, #{}),
        {ok, {{json, TokenResponse}, _Headers}} ?=
            oidcc_http_util:request(post, Request, TelemetryOpts, RequestOpts),
        {ok, TokenResponse}
    else
        {error, {use_dpop_nonce, NewDpopNonce, _}} when DpopOpts =:= #{} ->
            %% only retry automatically if we didn't use a nonce the first time
            %% (to avoid infinite loops)
            retrieve_a_token(
                QsBodyIn,
                ClientContext,
                Opts#{dpop_nonce => NewDpopNonce},
                TelemetryOpts,
                AuthenticateClient
            );
        {error, Reason} ->
            {error, Reason}
    end.

-spec add_pkce_verifier(QueryList, Opts, ClientContext) ->
    {ok, oidcc_http_util:query_params()} | {error, error()}
when
    QueryList :: oidcc_http_util:query_params(),
    Opts :: retrieve_opts() | refresh_opts(),
    ClientContext :: oidcc_client_context:t().
add_pkce_verifier(BodyQs, #{pkce_verifier := PkceVerifier} = Opts, ClientContext) ->
    #oidcc_client_context{provider_configuration = ProviderConfiguration} = ClientContext,
    #oidcc_provider_configuration{code_challenge_methods_supported = CodeChallengeMethodsSupported} =
        ProviderConfiguration,
    RequirePkce = maps:get(require_pkce, Opts, false),

    case CodeChallengeMethodsSupported of
        undefined when RequirePkce ->
            {error, no_supported_code_challenge};
        undefined ->
            {ok, BodyQs};
        Methods when is_list(Methods) ->
            case
                lists:member(<<"S256">>, CodeChallengeMethodsSupported) or
                    lists:member(<<"plain">>, CodeChallengeMethodsSupported)
            of
                true ->
                    {ok, [{<<"code_verifier">>, PkceVerifier} | BodyQs]};
                false when RequirePkce ->
                    {error, no_supported_code_challenge};
                false ->
                    {ok, BodyQs}
            end
    end;
add_pkce_verifier(_BodyQs, #{require_pkce := true}, _ClientContext) ->
    {error, pkce_verifier_required};
add_pkce_verifier(BodyQs, _Opts, _ClientContext) ->
    {ok, BodyQs}.

-spec rescue_none_validated_jwt(Result) -> Response when
    Response ::
        {ok, {#jose_jwt{}, #jose_jwe{} | #jose_jws{}, jose_jwk:key() | none}}
        | {error, oidcc_jwt_util:error()},
    Result ::
        {ok, {#jose_jwt{}, #jose_jwe{} | #jose_jws{}, jose_jwk:key() | none}}
        | {error, oidcc_jwt_util:error()}.
rescue_none_validated_jwt({ok, Valid}) ->
    {ok, Valid};
rescue_none_validated_jwt({error, {none_alg_used, Jwt0, Jws0}}) ->
    {ok, {Jwt0, Jws0, none}};
rescue_none_validated_jwt(Other) ->
    Other.

-spec unknown_kid_retry(Function, ClientContext, RefreshJwksFun) ->
    {ok, Result, refresh_info()} | {error, Error}
when
    Function :: fun((ClientContext) -> {ok, Result} | {error, Error}),
    ClientContext :: oidcc_client_context:t(),
    RefreshJwksFun :: undefined | oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
    Result :: term(),
    Error :: term().
unknown_kid_retry(Function, ClientContext, RefreshJwksFun) ->
    maybe
        {ok, Result} ?= Function(ClientContext),
        {ok, Result, undefined}
    else
        {error, {no_matching_key_with_kid, Kid}} when RefreshJwksFun =/= undefined ->
            #oidcc_client_context{jwks = OldJwks} = ClientContext,
            maybe
                {ok, RefreshedJwks, Info} ?= refresh_jwks(RefreshJwksFun, OldJwks, Kid),
                RefreshedClientContext = ClientContext#oidcc_client_context{jwks = RefreshedJwks},
                {ok, Retried} ?= Function(RefreshedClientContext),
                {ok, Retried, Info}
            end;
        {error, Reason} ->
            {error, Reason}
    end.

%% The three element return is what lets a caller learn what the refresh
%% actually fetched. A function that only hands back a key forces anything else,
%% the document and its expiry for instance, out through a side channel.
-spec refresh_jwks(RefreshJwksFun, Jwks, Kid) ->
    {ok, jose_jwk:key(), refresh_info()} | {error, term()}
when
    RefreshJwksFun :: oidcc_jwt_util:refresh_jwks_for_unknown_kid_fun(),
    Jwks :: jose_jwk:key(),
    Kid :: binary().
refresh_jwks(RefreshJwksFun, Jwks, Kid) ->
    case RefreshJwksFun(Jwks, Kid) of
        {ok, RefreshedJwks} -> {ok, RefreshedJwks, undefined};
        {ok, RefreshedJwks, Info} -> {ok, RefreshedJwks, Info};
        {error, Reason} -> {error, Reason}
    end.
````

## oidcc/src/oidcc_scope.erl

Version `3.9.0`, repository `erlef/oidcc`, commit `aa212d52d0140addf057c34917b734647401b34e`.

Git blob `02ba1208b90fe9fdf11b1c0ba1f597020604d98b`; SHA256 `76b4932a5d91db66f40b8a3b8ef715659439470bbe6f482c04b93bef1c231683`; size `1985` bytes.

Source: https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_scope.erl

````erlang
%% SPDX-FileCopyrightText: 2023 Erlang Ecosystem Foundation
%% SPDX-License-Identifier: Apache-2.0

-module(oidcc_scope).

-feature(maybe_expr, enable).

-moduledoc "OpenID Scope Utilities".
-moduledoc #{since => <<"3.0.0">>}.

-export([parse/1]).
-export([query_append_scope/2]).
-export([scopes_to_bin/1]).

-export_type([scopes/0]).
-export_type([t/0]).

-doc #{since => <<"3.0.0">>}.
-type scopes() :: [nonempty_binary() | atom() | nonempty_string()].

-doc #{since => <<"3.0.0">>}.
-type t() :: binary().

-doc """
Compose `t:scopes/0` into `t:t/0`.

## Examples

```erlang
<<"openid profile email">> = oidcc_scope:scopes_to_bin(
  [<<"openid">>, profile, "email"]).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec scopes_to_bin(Scopes :: scopes()) -> t().
scopes_to_bin(Scopes) ->
    NormalizedScopes =
        lists:map(
            fun
                (Scope) when is_binary(Scope) ->
                    Scope;
                (Scope) when is_atom(Scope) ->
                    atom_to_binary(Scope, utf8);
                (Scope) when is_list(Scope) ->
                    list_to_binary(Scope)
            end,
            Scopes
        ),
    SeparatedScopes = lists:join(<<" ">>, NormalizedScopes),
    list_to_binary(SeparatedScopes).

-doc false.
-spec query_append_scope(Scope, QueryList) -> QueryList when
    Scope :: t() | scopes(),
    QueryList :: [{unicode:chardata(), unicode:chardata() | true}].
query_append_scope(<<>>, QueryList) ->
    QueryList;
query_append_scope(Scope, QueryList) when is_binary(Scope) ->
    [{<<"scope">>, Scope} | QueryList];
query_append_scope(Scopes, QueryList) when is_list(Scopes) ->
    query_append_scope(scopes_to_bin(Scopes), QueryList).

-doc """
Parse `t:t/0` into `t:scopes/0`.

## Examples

```erlang
[<<"openid">>, <<"profile">>] = oidcc_scope:parse(<<"openid profile">>).
```
""".
-doc #{since => <<"3.0.0">>}.
-spec parse(Scope :: t()) -> scopes().
parse(Scope) ->
    binary:split(Scope, [<<" ">>], [trim_all, global]).
````

## oidcc/lib/oidcc/token.ex

Version `3.9.0`, repository `erlef/oidcc`, commit `aa212d52d0140addf057c34917b734647401b34e`.

Git blob `cc2259e691e463107cab0c358b94f189f8dc615f`; SHA256 `d8b6c176c9cc8954dc44375ed3921a4119fc1c169cbc7beda7329e92462ff72d`; size `17254` bytes.

Source: https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/lib/oidcc/token.ex

````elixir
# SPDX-FileCopyrightText: 2023 Erlang Ecosystem Foundation
# SPDX-License-Identifier: Apache-2.0

defmodule Oidcc.Token do
  use TelemetryRegistry

  telemetry_event(%{
    event: [:oidcc, :request_token, :start],
    description: "Emitted at the start of requesting a code token",
    measurements: "%{system_time: non_neg_integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :request_token, :stop],
    description: "Emitted at the end of requesting a code token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :request_token, :exception],
    description: "Emitted at the end of requesting a code token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :refresh_token, :start],
    description: "Emitted at the start of refreshing a token",
    measurements: "%{system_time: non_neg_integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :refresh_token, :stop],
    description: "Emitted at the end of refreshing a token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :refresh_token, :exception],
    description: "Emitted at the end of refreshing a token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :jwt_profile_token, :start],
    description: "Emitted at the start of exchanging a JWT profile token",
    measurements: "%{system_time: non_neg_integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :jwt_profile_token, :stop],
    description: "Emitted at the end of exchanging a JWT profile token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :jwt_profile_token, :exception],
    description: "Emitted at the end of exchanging a JWT profile token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :client_credentials, :start],
    description: "Emitted at the start of requesting a client credentials token",
    measurements: "%{system_time: non_neg_integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :client_credentials, :stop],
    description: "Emitted at the end of requesting a client credentials token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  telemetry_event(%{
    event: [:oidcc, :client_credentials, :exception],
    description: "Emitted at the end of requesting a client credentials token",
    measurements: "%{duration: integer(), monotonic_time: integer()}",
    metadata: "%{issuer: :uri_string.uri_string(), client_id: String.t()}"
  })

  @moduledoc """
  Facilitate OpenID Code/Token Exchanges

  ## Telemetry

  #{telemetry_docs()}
  """
  @moduledoc since: "3.0.0"

  use Oidcc.RecordStruct,
    internal_name: :token,
    record_name: :oidcc_token,
    hrl: "include/oidcc_token.hrl"

  alias Oidcc.ClientContext
  alias Oidcc.Token.Access
  alias Oidcc.Token.Id
  alias Oidcc.Token.Refresh

  @typedoc since: "3.0.0"
  @type t() :: %__MODULE__{
          id: Id.t() | none,
          access: Access.t() | none,
          refresh: Refresh.t() | none,
          scope: :oidcc_scope.scopes()
        }

  @type retrieve_opts() :: :oidcc_token.retrieve_opts()

  @doc """
  retrieve the token using the authcode received before and directly validate
  the result.

  the authcode was sent to the local endpoint by the OpenId Connect provider,
  using redirects

  For a high level interface using `Oidcc.ProviderConfiguration.Worker`
  see `Oidcc.retrieve_token/5`.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://api.login.yahoo.com"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "client_id",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> # Get auth_code from redirect
      ...> auth_code = "auth_code"
      ...>
      ...> Oidcc.Token.retrieve(
      ...>   auth_code,
      ...>   client_context,
      ...>   %{redirect_uri: "https://my.server/return"}
      ...> )
      ...> # => {:ok, %Oidcc.Token{}}

  """
  @doc since: "3.0.0"
  @spec retrieve(
          auth_code :: String.t(),
          client_context :: ClientContext.t(),
          opts :: retrieve_opts()
        ) ::
          {:ok, t()} | {:error, :oidcc_token.error()}
  def retrieve(auth_code, client_context, opts) do
    client_context = ClientContext.struct_to_record(client_context)

    auth_code
    |> :oidcc_token.retrieve(client_context, opts)
    |> normalize_token_response()
  end

  @doc """
  Retrieve the token, reporting what a JWKS refresh fetched

  Same as `retrieve/3`, but the third element carries whatever the
  `refresh_jwks` function returned alongside the refreshed keys, or `:undefined`
  when no refresh happened.

  oidcc refreshes the keys and retries validation without re-sending the
  authorization code, which is single use, so this is the only way to learn what
  that refresh fetched. Persisting the refreshed key set is the usual reason to
  want it.

  ## Examples

      refresh_jwks = fn _old_jwks, _kid ->
        {:ok, {jwks, expiry, document}} =
          Oidcc.ProviderConfiguration.load_jwks_raw(jwks_uri, %{})

        {:ok, JOSE.JWK.to_record(jwks), {document, expiry}}
      end

      {:ok, %Oidcc.Token{}, {document, expiry}} =
        Oidcc.Token.retrieve_with_refresh(auth_code, client_context, %{
          redirect_uri: "https://my.server/return",
          refresh_jwks: refresh_jwks
        })

  """
  @doc since: "3.9.0"
  @spec retrieve_with_refresh(
          auth_code :: String.t(),
          client_context :: ClientContext.t(),
          opts :: retrieve_opts()
        ) ::
          {:ok, t(), :oidcc_token.refresh_info()} | {:error, :oidcc_token.error()}
  def retrieve_with_refresh(auth_code, client_context, opts) do
    client_context = ClientContext.struct_to_record(client_context)

    case :oidcc_token.retrieve_with_refresh(auth_code, client_context, opts) do
      {:ok, token, info} -> {:ok, record_to_struct(token), info}
      {:error, reason} -> {:error, reason} |> normalize_token_response()
    end
  end

  @doc """
  Validate the JARM response, returning the valid claims as a map.

  the response was sent to the local endpoint by the OpenId Connect provider,
  using redirects

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://api.login.yahoo.com"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "client_id",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> # Get auth_code from redirect
      ...> response = "JWT"
      ...>
      ...> Oidcc.Token.validate_jarm(
      ...>   response,
      ...>   client_context,
      ...>   %{}
      ...> )
      ...> # => {:ok, %{"code" => auth_code}}

  """
  @doc since: "3.2.0"
  @spec validate_jarm(
          response :: String.t(),
          client_context :: ClientContext.t(),
          opts :: :oidcc_token.validate_jarm_opts()
        ) ::
          {:ok, :oidcc_jwt_util.claims()} | {:error, :oidcc_token.error()}
  def validate_jarm(response, client_context, opts) do
    client_context = ClientContext.struct_to_record(client_context)

    :oidcc_token.validate_jarm(response, client_context, opts)
  end

  @doc """
  Refresh Token

  For a high level interface using `Oidcc.ProviderConfiguration.Worker`
  see `Oidcc.refresh_token/5`.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://api.login.yahoo.com"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "client_id",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> # Get refresh_token from redirect
      ...> refresh_token = "refresh_token"
      ...>
      ...> Oidcc.Token.refresh(
      ...>   refresh_token,
      ...>   client_context,
      ...>   %{expected_subject: "sub"}
      ...> )
      ...> # => {:ok, %Oidcc.Token{}}

  """
  @doc since: "3.0.0"
  @spec refresh(
          refresh_token :: String.t(),
          client_context :: ClientContext.t(),
          opts :: :oidcc_token.refresh_opts()
        ) :: {:ok, t()} | {:error, :oidcc_token.error()}
  @spec refresh(
          token :: t(),
          client_context :: ClientContext.t(),
          opts :: :oidcc_token.refresh_opts_no_sub()
        ) :: {:ok, t()} | {:error, :oidcc_token.error()}
  def refresh(token, client_context, opts) do
    token =
      case token do
        token when is_binary(token) -> token
        %__MODULE__{} = token -> struct_to_record(token)
      end

    client_context = ClientContext.struct_to_record(client_context)

    token
    |> :oidcc_token.refresh(client_context, opts)
    |> normalize_token_response()
  end

  @doc """
  Validate ID Token

  Usually the id token is validated using `retrieve/3`.
  If you get the token passed from somewhere else, this function can validate it.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://api.login.yahoo.com"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "client_id",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> #Get IdToken from somewhere
      ...> id_token = "id_token"
      ...>
      ...> Oidcc.Token.validate_id_token(id_token, client_context, :any)
      ...> # => {:ok, %{"sub" => "sub", ... }}

  """
  @doc since: "3.0.0"
  @spec validate_id_token(
          id_token :: String.t(),
          client_context :: ClientContext.t(),
          nonce_or_opts :: String.t() | :any | retrieve_opts()
        ) :: {:ok, :oidcc_jwt_util.claims()} | {:error, :oidcc_token.error()}
  def validate_id_token(id_token, client_context, nonce_or_opts),
    do:
      :oidcc_token.validate_id_token(
        id_token,
        ClientContext.struct_to_record(client_context),
        nonce_or_opts
      )

  @doc """
  Validate JWT

  Validates a generic JWT (such as an access token) from the given provider.
  Useful if the issuer is shared between multiple applications, and the access token
  generated for a user at one client is used to validate their access at another client.

  Validating an arbitrary JWT token (not an ID token) is not covered by the OpenID
  Connect specification. Therefore the signing / encryption algorithms are not
  derieved from the provider configuration, but must be provided by the caller.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://api.login.yahoo.com"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "client_id",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> # Get JWT from Authorization header
      ...> jwt = "jwt"
      ...>
      ...> opts = %{
      ...>   signing_algs: client_context.provider_configuration.id_token_signing_alg_values_supported
      ...> }
      ...>
      ...> Oidcc.Token.validate_jwt(jwt, client_context, opts)
      ...> # => {:ok, %{"sub" => "sub", ... }}

  """
  @doc since: "3.0.0"
  @spec validate_jwt(
          jwt :: String.t(),
          client_context :: ClientContext.t(),
          opts :: :oidcc_token.validate_jwt_opts()
        ) :: {:ok, :oidcc_jwt_util.claims()} | {:error, :oidcc_token.error()}
  def validate_jwt(jwt, client_context, opts),
    do:
      :oidcc_token.validate_jwt(
        jwt,
        ClientContext.struct_to_record(client_context),
        opts
      )

  @doc """
  Retrieve JSON Web Token (JWT) Profile Token

  See https://datatracker.ietf.org/doc/html/rfc7523#section-4

  For a high level interface using `Oidcc.ProviderConfiguration.Worker`
  see `Oidcc.jwt_profile_token/6`.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://erlef-test-w4a8z2.zitadel.cloud"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     "JWT Profile Test",
      ...>     "client_secret"
      ...>   )
      ...>
      ...> %{"key" => key, "keyId" => kid, "userId" => subject} = "JWT_PROFILE"
      ...>   |> System.fetch_env!()
      ...>   |> JOSE.decode()
      ...>
      ...> jwk = JOSE.JWK.from_pem(key)
      ...>
      ...> {:ok, %Oidcc.Token{}} =
      ...>   Oidcc.Token.jwt_profile(
      ...>     subject,
      ...>     client_context,
      ...>     jwk,
      ...>     %{scope: ["openid", "urn:zitadel:iam:org:project:id:zitadel:aud"], kid: kid}
      ...>   )

  """
  @doc since: "3.0.0"
  @spec jwt_profile(
          subject :: String.t(),
          client_context :: ClientContext.t(),
          jwk :: JOSE.JWK.t(),
          opts :: :oidcc_token.jwt_profile_opts()
        ) :: {:ok, t()} | {:error, :oidcc_token.error()}
  def jwt_profile(subject, client_context, jwk, opts) do
    jwk = JOSE.JWK.to_record(jwk)
    client_context = ClientContext.struct_to_record(client_context)

    subject
    |> :oidcc_token.jwt_profile(client_context, jwk, opts)
    |> normalize_token_response()
  end

  @doc """
  Retrieve Client Credential Token

  See https://datatracker.ietf.org/doc/html/rfc6749#section-1.3.4

  For a high level interface using `Oidcc.ProviderConfiguration.Worker`
  see `Oidcc.client_credentials_token/4`.

  ## Examples

      iex> {:ok, pid} =
      ...>   Oidcc.ProviderConfiguration.Worker.start_link(%{
      ...>     issuer: "https://erlef-test-w4a8z2.zitadel.cloud"
      ...>   })
      ...>
      ...> {:ok, client_context} =
      ...>   Oidcc.ClientContext.from_configuration_worker(
      ...>     pid,
      ...>     System.fetch_env!("CLIENT_CREDENTIALS_CLIENT_ID"),
      ...>     System.fetch_env!("CLIENT_CREDENTIALS_CLIENT_SECRET")
      ...>   )
      ...>
      ...> {:ok, %Oidcc.Token{}} =
      ...>   Oidcc.Token.client_credentials(
      ...>     client_context,
      ...>     %{scope: ["openid"]}
      ...>   )

  """
  @doc since: "3.0.0"
  @spec client_credentials(
          client_context :: ClientContext.t(),
          opts :: :oidcc_token.client_credentials_opts()
        ) :: {:ok, t()} | {:error, :oidcc_token.error()}
  def client_credentials(client_context, opts),
    do:
      client_context
      |> ClientContext.struct_to_record()
      |> :oidcc_token.client_credentials(opts)
      |> normalize_token_response()

  @doc false
  @spec normalize_token_response(
          response :: {:ok, :oidcc_token.t()} | {:error, :oidcc_token.error()}
        ) ::
          {:ok, t()} | {:error, :oidcc_token.error()}
  def normalize_token_response(response)
  def normalize_token_response({:ok, token}), do: {:ok, record_to_struct(token)}

  def normalize_token_response({:error, {:none_alg_used, token}}),
    do: {:error, {:none_alg_used, record_to_struct(token)}}

  def normalize_token_response({:error, reason}), do: {:error, reason}

  @impl Oidcc.RecordStruct
  def record_to_struct(record) do
    record
    |> super()
    |> update_if_not_none(:id, &Id.record_to_struct/1)
    |> update_if_not_none(:access, &Access.record_to_struct/1)
    |> update_if_not_none(:refresh, &Refresh.record_to_struct/1)
  end

  @impl Oidcc.RecordStruct
  def struct_to_record(struct) do
    struct
    |> update_if_not_none(:id, &Id.struct_to_record/1)
    |> update_if_not_none(:access, &Access.struct_to_record/1)
    |> update_if_not_none(:refresh, &Refresh.struct_to_record/1)
    |> super()
  end

  defp update_if_not_none(map, key, callback) do
    Map.update!(map, key, fn
      :none -> :none
      other -> callback.(other)
    end)
  end
end
````

## oidcc/LICENSE

Version `3.9.0`, repository `erlef/oidcc`, commit `aa212d52d0140addf057c34917b734647401b34e`.

Git blob `6e78ee3d673c1c732101d408a6fc08feaf4bd24d`; SHA256 `4963e95276dd77eff345c75f44cc0af800edebf3e4a7cf4a154ef35aae4f16e9`; size `11377` bytes.

Source: https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/LICENSE

````text

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS

   APPENDIX: How to apply the Apache License to your work.

      To apply the Apache License to your work, attach the following
      boilerplate notice, with the fields enclosed by brackets "[]"
      replaced with your own identifying information. (Don't include
      the brackets!)  The text should be enclosed in the appropriate
      comment syntax for the file format. We also recommend that a
      file or class name and description of purpose be included on the
      same "printed page" as the copyright notice for easier
      identification within third-party archives.

   Copyright 2023 Jonatan Männchen / Erlang Ecosystem Foundation

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
````

## telemetry/src/telemetry.erl

Version `1.3.0`, repository `beam-telemetry/telemetry`, commit `8d8af76720856bcf26641ee1307658ad8f25e466`.

Git blob `7f4bb28e6ce4c43e363f038d70ba6f0582b63fbf`; SHA256 `faebd2146716eade18c610ce13daedfbfe421fa0b5d5d244d8a47c38ba22a77e`; size `15646` bytes.

Source: https://github.com/beam-telemetry/telemetry/blob/8d8af76720856bcf26641ee1307658ad8f25e466/src/telemetry.erl

````erlang
-module(telemetry).

-export([attach/4,
         attach_many/4,
         detach/1,
         list_handlers/1,
         execute/2,
         execute/3,
         span/3]).

-export([report_cb/1]).

-include("telemetry.hrl").

?MODULEDOC("""
`telemetry` allows you to invoke certain functions whenever a
particular event is emitted.

For more information see the documentation for `attach/4`, `attach_many/4`
and `execute/2`.
""").

-type handler_id() :: term().
-type event_name() :: [atom(), ...].
-type event_measurements() :: map().
-type event_metadata() :: map().
-type event_value() :: number().
-type event_prefix() :: [atom()].
-type handler_config() :: term().
-type handler_function() :: fun((event_name(), event_measurements(), event_metadata(), handler_config()) -> any()).
-type span_result() :: term().
-type span_function() :: fun(() -> {span_result(), event_metadata()}) | {span_result(), event_measurements(), event_metadata()}.
-type handler() :: #{id := handler_id(),
                     event_name := event_name(),
                     function := handler_function(),
                     config := handler_config()}.

-export_type([handler_id/0,
              event_name/0,
              event_measurements/0,
              event_metadata/0,
              event_value/0,
              event_prefix/0,
              handler_config/0,
              handler_function/0,
              handler/0,
              span_result/0,
              span_function/0]).

-import_lib("kernel/import/logger.hrl").

?DOC("""
Attaches the handler to the event.

`HandlerId` must be unique, if another handler with the same ID already exists the
`{error, already_exists}` tuple is returned.

See `execute/3` to learn how the handlers are invoked.

> #### Function Captures {: .info}
>
> Due to how anonymous functions are implemented in the Erlang VM, it is best to use
> function captures (`fun mod:fun/4` in Erlang or `&Mod.fun/4` in Elixir) as event handlers
> to achieve the best performance. In other words, avoid using literal anonymous functions
> (`fun(...) -> ... end` or `fn ... -> ... end`) or local function captures (`fun handle_event/4`
> or `&handle_event/4`) as event handlers.

All the handlers are executed by the process dispatching event. If the function fails (raises,
exits or throws) then the handler is removed and a failure event is emitted.

Handler failure events `[telemetry, handler, failure]` should only be used for monitoring
and diagnostic purposes. Re-attaching a failed handler will likely result in the handler
failing again.

Note that you should not rely on the order in which handlers are invoked.
""").
-spec attach(HandlerId, EventName, Function, Config) -> ok | {error, already_exists} when
      HandlerId :: handler_id(),
      EventName :: event_name(),
      Function :: handler_function(),
      Config :: handler_config().
attach(HandlerId, EventName, Function, Config) ->
    attach_many(HandlerId, [EventName], Function, Config).

?DOC("""
Attaches the handler to many events.

The handler will be invoked whenever any of the events in the `EventNames` list is emitted. Note
that failure of the handler on any of these invocations will detach it from all the events in
`EventNames` (the same applies to manual detaching using `detach/1`).

<b>Note:</b> due to how anonymous functions are implemented in the Erlang VM, it is best to use
function captures (i.e. `fun mod:fun/4` in Erlang or `&Mod.fun/4` in Elixir) as event handlers
to achieve maximum performance. In other words, avoid using literal anonymous functions
(`fun(...) -> ... end` or `fn ... -> ... end`) or local function captures (`fun handle_event/4`
or `&handle_event/4`) as event handlers.

All the handlers are executed by the process dispatching event. If the function fails (raises,
exits or throws) a handler failure event is emitted and then the handler is removed.

Handler failure events `[telemetry, handler, failure]` should only be used for monitoring
and diagnostic purposes. Re-attaching a failed handler will likely result in the handler
failing again.

Note that you should not rely on the order in which handlers are invoked.
""").
-spec attach_many(HandlerId, [EventName], Function, Config) -> ok | {error, already_exists} when
      HandlerId :: handler_id(),
      EventName :: event_name(),
      Function :: handler_function(),
      Config :: handler_config().
attach_many(HandlerId, EventNames, Function, Config) when is_function(Function, 4) ->
    assert_event_names(EventNames),
    case erlang:fun_info(Function, type) of
        {type, external} ->
            ok;
        {type, local} ->
            ?LOG_INFO(#{handler_id => HandlerId,
                        event_names => EventNames,
                        function => Function,
                        config => Config,
                        type => local},
                      #{report_cb => fun ?MODULE:report_cb/1})
    end,
    telemetry_handler_table:insert(HandlerId, EventNames, Function, Config).

?DOC("""
Removes the existing handler.

If the handler with given ID doesn't exist, `{error, not_found}` is returned.
""").
-spec detach(handler_id()) -> ok | {error, not_found}.
detach(HandlerId) ->
    telemetry_handler_table:delete(HandlerId).

?DOC("""
Emits the event, invoking handlers attached to it.

When the event is emitted, the handler function provided to `attach/4` is called with four
arguments:

  * the event name
  * the map of measurements
  * the map of event metadata
  * the handler configuration given to `attach/4`

#### Best practices and conventions:

While you are able to emit messages of any `t:event_name/0` structure, it is recommended that you follow the
the guidelines laid out in `span/3` if you are capturing start/stop events.
""").
-spec execute(EventName, Measurements, Metadata) -> ok when
      EventName :: event_name(),
      Measurements :: event_measurements() | event_value(),
      Metadata :: event_metadata().
execute(EventName, Value, Metadata) when is_number(Value) ->
    ?LOG_WARNING("Using execute/3 with a single event value is deprecated. "
                 "Use a measurement map instead.", []),
    execute(EventName, #{value => Value}, Metadata);
execute([_ | _] = EventName, Measurements, Metadata) when is_map(Measurements) and is_map(Metadata) ->
    Handlers = telemetry_handler_table:list_for_event(EventName),
    ApplyFun =
        fun(#handler{id=HandlerId,
                     function=HandlerFunction,
                     config=Config}) ->
            try
                HandlerFunction(EventName, Measurements, Metadata, Config)
            catch
                ?WITH_STACKTRACE(Class, Reason, Stacktrace)
                    detach(HandlerId),
                    FailureMetadata = #{event_name => EventName,
                                        handler_id => HandlerId,
                                        handler_config => Config,
                                        kind => Class,
                                        reason => Reason,
                                        stacktrace => Stacktrace},
                    FailureMeasurements = #{monotonic_time => erlang:monotonic_time(), system_time => erlang:system_time()},
                    execute([telemetry, handler, failure], FailureMeasurements, FailureMetadata),
                    ?LOG_ERROR("Handler ~p has failed and has been detached. "
                               "Class=~p~nReason=~p~nStacktrace=~p~n",
                               [HandlerId, Class, Reason, Stacktrace])
            end
        end,
    lists:foreach(ApplyFun, Handlers).

?DOC("""
Runs the provided `SpanFunction`, emitting start and stop/exception events, invoking the handlers attached to each.

The `SpanFunction` must return a `{result, stop_metadata}` or a `{result, extra_measurements, stop_metadata}` tuple.

When this function is called, 2 events will be emitted via `execute/3`. Those events will be one of the following
pairs:

  * `EventPrefix ++ [start]` and `EventPrefix ++ [stop]`
  * `EventPrefix ++ [start]` and `EventPrefix ++ [exception]`

However, note that in case the current process crashes due to an exit signal
of another process, then none or only part of those events would be emitted.
Below is a breakdown of the measurements and metadata associated with each individual event.

When providing `StartMetadata` and `StopMetadata`, these values will be sent independently to `start` and
`stop` events. If an exception occurs, exception metadata will be merged onto the `StartMetadata`. In general,
it is **highly recommended** that `StopMetadata` should include the values from `StartMetadata`
so that handlers, such as those used for metrics, can rely entirely on the `stop` event. Failure to include
all of `StartMetadata` in `StopMetadata` can add significant complexity to event handlers.

A default span context is added to event metadata under the `telemetry_span_context` key if this key is not provided
by the user in the `StartMetadata`. This context is useful for tracing libraries to identify unique
executions of span events within a process to match start, stop, and exception events. Metadata keys which
should be available to both `start` and `stop` events need to supplied separately for `StartMetadata` and
`StopMetadata`.

If `SpanFunction` returns `{result, extra_measurements, stop_metadata}`, then a map of extra measurements
will be merged with the measurements automatically provided. This is useful if you want to return, for example,
bytes from an HTTP request. The standard measurements `duration` and `monotonic_time` cannot be overridden.

For `telemetry` events denoting the **start** of a larger event, the following data is provided:

  * Event:

    ```
    EventPrefix ++ [start]
    ```

  * Measurements:

    ```
    #{
      % The current system time in native units from
      % calling: erlang:system_time()
      system_time => integer(),
      monotonic_time => integer(),
    }
    ```

  * Metadata:

    ```
    #{
      telemetry_span_context => term(),
      % User defined metadata as provided in StartMetadata
      ...
    }
    ```



For `telemetry` events denoting the **stop** of a larger event, the following data is provided:

  * Event:

    ```
    EventPrefix ++ [stop]
    ```

  * Measurements:

    ```
    #{
      % The current monotonic time minus the start monotonic time in native units
      % by calling: erlang:monotonic_time() - start_monotonic_time
      duration => integer(),
      monotonic_time => integer(),
      % User defined measurements when returning `SpanFunction` as a 3 element tuple
    }
    ```

  * Metadata:

    ```
    #{
      % An optional error field if the stop event is the result of an error
      % but not necessarily an exception.
      error => term(),
      telemetry_span_context => term(),
      % User defined metadata as provided in StopMetadata
      ...
    }
    ```

For `telemetry` events denoting an **exception** of a larger event, the following data is provided:

  * Event:

    ```
    EventPrefix ++ [exception]
    ```

  * Measurements:

    ```
    #{
      % The current monotonic time minus the start monotonic time in native units
      % by calling: erlang:monotonic_time() - start_monotonic_time
      duration => integer(),
      monotonic_time => integer()
    }
    ```

  * Metadata:

    ```
    #{
      kind => throw | error | exit,
      reason => term(),
      stacktrace => list(),
      telemetry_span_context => term(),
      % User defined metadata as provided in StartMetadata
       ...
    }
    ```

""").
-spec span(event_prefix(), event_metadata(), span_function()) -> span_result().
span(EventPrefix, StartMetadata, SpanFunction) ->
    StartTime = erlang:monotonic_time(),
    DefaultCtx = erlang:make_ref(),
    execute(
        EventPrefix ++ [start],
        #{monotonic_time => StartTime, system_time => erlang:system_time()},
        merge_ctx(StartMetadata, DefaultCtx)
    ),

    try SpanFunction() of
      {Result, StopMetadata} ->
          StopTime = erlang:monotonic_time(),
          execute(
              EventPrefix ++ [stop],
              #{duration => StopTime - StartTime, monotonic_time => StopTime},
              merge_ctx(StopMetadata, DefaultCtx)
          ),
          Result;
      {Result, ExtraMeasurements, StopMetadata} ->
          StopTime = erlang:monotonic_time(),
          Measurements = maps:merge(ExtraMeasurements, #{duration => StopTime - StartTime, monotonic_time => StopTime}),
          execute(
              EventPrefix ++ [stop],
              Measurements,
              merge_ctx(StopMetadata, DefaultCtx)
          ),
          Result

    catch
        ?WITH_STACKTRACE(Class, Reason, Stacktrace)
            StopTime = erlang:monotonic_time(),
            execute(
                EventPrefix ++ [exception],
                #{duration => StopTime - StartTime, monotonic_time => StopTime},
                merge_ctx(StartMetadata#{kind => Class, reason => Reason, stacktrace => Stacktrace}, DefaultCtx)
            ),
            erlang:raise(Class, Reason, Stacktrace)
    end.

?DOC("""
Same as [`execute(EventName, Measurements, #{})`](`execute/3`).
""").
-spec execute(EventName, Measurements) -> ok when
      EventName :: event_name(),
      Measurements :: event_measurements() | event_value().
execute(EventName, Measurements) ->
    execute(EventName, Measurements, #{}).

?DOC("""
Returns all handlers attached to events with given prefix.

Handlers attached to many events at once using `attach_many/4` will be listed once for each
event they're attached to.
Note that you can list all handlers by feeding this function an empty list.
""").
-spec list_handlers(event_prefix()) -> [handler()].
list_handlers(EventPrefix) ->
    assert_event_prefix(EventPrefix),
    [#{id => HandlerId,
       event_name => EventName,
       function => Function,
       config => Config} || #handler{id=HandlerId,
                                     event_name=EventName,
                                     function=Function,
                                     config=Config} <- telemetry_handler_table:list_by_prefix(EventPrefix)].

%%

-spec assert_event_names(term()) -> [ok].
assert_event_names(List) when is_list(List) ->
    [assert_event_name(E) || E <- List];
assert_event_names(Term) ->
    erlang:error(badarg, Term).

-spec assert_event_prefix(term()) -> ok.
assert_event_prefix(List) when is_list(List) ->
    case lists:all(fun erlang:is_atom/1, List) of
        true ->
            ok;
        false ->
            erlang:error(badarg, List)
    end;
assert_event_prefix(List) ->
    erlang:error(badarg, List).

-spec assert_event_name(term()) -> ok.
assert_event_name([_ | _] = List) ->
    case lists:all(fun erlang:is_atom/1, List) of
        true ->
            ok;
        false ->
            erlang:error(badarg, List)
    end;
assert_event_name(Term) ->
    erlang:error(badarg, Term).

-spec merge_ctx(event_metadata(), any()) -> event_metadata().
merge_ctx(#{telemetry_span_context := _} = Metadata, _Ctx) -> Metadata;
merge_ctx(Metadata, Ctx) -> Metadata#{telemetry_span_context => Ctx}.

?DOC(false).
report_cb(#{handler_id := Id}) ->
    {"The function passed as a handler with ID ~w is a local function.\n"
     "This means that it is either an anonymous function or a capture of a function "
     "without a module specified. That may cause a performance penalty when calling "
     "that handler. For more details see the note in `telemetry:attach/4` "
     "documentation.\n\n"
     "https://hexdocs.pm/telemetry/telemetry.html#attach/4", [Id]}.
````

## telemetry/LICENSE

Version `1.3.0`, repository `beam-telemetry/telemetry`, commit `8d8af76720856bcf26641ee1307658ad8f25e466`.

Git blob `4947287f7b5ccb5d1e8b7b2d3aa5d89f322c160d`; SHA256 `0cec06e0e55fbc3dc5cee4fca9b607f66cb8f4e4dbcf3b3c013594dd156732e9`; size `10173` bytes.

Source: https://github.com/beam-telemetry/telemetry/blob/8d8af76720856bcf26641ee1307658ad8f25e466/LICENSE

````text

                                 Apache License
                           Version 2.0, January 2004
                        http://www.apache.org/licenses/

   TERMS AND CONDITIONS FOR USE, REPRODUCTION, AND DISTRIBUTION

   1. Definitions.

      "License" shall mean the terms and conditions for use, reproduction,
      and distribution as defined by Sections 1 through 9 of this document.

      "Licensor" shall mean the copyright owner or entity authorized by
      the copyright owner that is granting the License.

      "Legal Entity" shall mean the union of the acting entity and all
      other entities that control, are controlled by, or are under common
      control with that entity. For the purposes of this definition,
      "control" means (i) the power, direct or indirect, to cause the
      direction or management of such entity, whether by contract or
      otherwise, or (ii) ownership of fifty percent (50%) or more of the
      outstanding shares, or (iii) beneficial ownership of such entity.

      "You" (or "Your") shall mean an individual or Legal Entity
      exercising permissions granted by this License.

      "Source" form shall mean the preferred form for making modifications,
      including but not limited to software source code, documentation
      source, and configuration files.

      "Object" form shall mean any form resulting from mechanical
      transformation or translation of a Source form, including but
      not limited to compiled object code, generated documentation,
      and conversions to other media types.

      "Work" shall mean the work of authorship, whether in Source or
      Object form, made available under the License, as indicated by a
      copyright notice that is included in or attached to the work
      (an example is provided in the Appendix below).

      "Derivative Works" shall mean any work, whether in Source or Object
      form, that is based on (or derived from) the Work and for which the
      editorial revisions, annotations, elaborations, or other modifications
      represent, as a whole, an original work of authorship. For the purposes
      of this License, Derivative Works shall not include works that remain
      separable from, or merely link (or bind by name) to the interfaces of,
      the Work and Derivative Works thereof.

      "Contribution" shall mean any work of authorship, including
      the original version of the Work and any modifications or additions
      to that Work or Derivative Works thereof, that is intentionally
      submitted to Licensor for inclusion in the Work by the copyright owner
      or by an individual or Legal Entity authorized to submit on behalf of
      the copyright owner. For the purposes of this definition, "submitted"
      means any form of electronic, verbal, or written communication sent
      to the Licensor or its representatives, including but not limited to
      communication on electronic mailing lists, source code control systems,
      and issue tracking systems that are managed by, or on behalf of, the
      Licensor for the purpose of discussing and improving the Work, but
      excluding communication that is conspicuously marked or otherwise
      designated in writing by the copyright owner as "Not a Contribution."

      "Contributor" shall mean Licensor and any individual or Legal Entity
      on behalf of whom a Contribution has been received by Licensor and
      subsequently incorporated within the Work.

   2. Grant of Copyright License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      copyright license to reproduce, prepare Derivative Works of,
      publicly display, publicly perform, sublicense, and distribute the
      Work and such Derivative Works in Source or Object form.

   3. Grant of Patent License. Subject to the terms and conditions of
      this License, each Contributor hereby grants to You a perpetual,
      worldwide, non-exclusive, no-charge, royalty-free, irrevocable
      (except as stated in this section) patent license to make, have made,
      use, offer to sell, sell, import, and otherwise transfer the Work,
      where such license applies only to those patent claims licensable
      by such Contributor that are necessarily infringed by their
      Contribution(s) alone or by combination of their Contribution(s)
      with the Work to which such Contribution(s) was submitted. If You
      institute patent litigation against any entity (including a
      cross-claim or counterclaim in a lawsuit) alleging that the Work
      or a Contribution incorporated within the Work constitutes direct
      or contributory patent infringement, then any patent licenses
      granted to You under this License for that Work shall terminate
      as of the date such litigation is filed.

   4. Redistribution. You may reproduce and distribute copies of the
      Work or Derivative Works thereof in any medium, with or without
      modifications, and in Source or Object form, provided that You
      meet the following conditions:

      (a) You must give any other recipients of the Work or
          Derivative Works a copy of this License; and

      (b) You must cause any modified files to carry prominent notices
          stating that You changed the files; and

      (c) You must retain, in the Source form of any Derivative Works
          that You distribute, all copyright, patent, trademark, and
          attribution notices from the Source form of the Work,
          excluding those notices that do not pertain to any part of
          the Derivative Works; and

      (d) If the Work includes a "NOTICE" text file as part of its
          distribution, then any Derivative Works that You distribute must
          include a readable copy of the attribution notices contained
          within such NOTICE file, excluding those notices that do not
          pertain to any part of the Derivative Works, in at least one
          of the following places: within a NOTICE text file distributed
          as part of the Derivative Works; within the Source form or
          documentation, if provided along with the Derivative Works; or,
          within a display generated by the Derivative Works, if and
          wherever such third-party notices normally appear. The contents
          of the NOTICE file are for informational purposes only and
          do not modify the License. You may add Your own attribution
          notices within Derivative Works that You distribute, alongside
          or as an addendum to the NOTICE text from the Work, provided
          that such additional attribution notices cannot be construed
          as modifying the License.

      You may add Your own copyright statement to Your modifications and
      may provide additional or different license terms and conditions
      for use, reproduction, or distribution of Your modifications, or
      for any such Derivative Works as a whole, provided Your use,
      reproduction, and distribution of the Work otherwise complies with
      the conditions stated in this License.

   5. Submission of Contributions. Unless You explicitly state otherwise,
      any Contribution intentionally submitted for inclusion in the Work
      by You to the Licensor shall be under the terms and conditions of
      this License, without any additional terms or conditions.
      Notwithstanding the above, nothing herein shall supersede or modify
      the terms of any separate license agreement you may have executed
      with Licensor regarding such Contributions.

   6. Trademarks. This License does not grant permission to use the trade
      names, trademarks, service marks, or product names of the Licensor,
      except as required for reasonable and customary use in describing the
      origin of the Work and reproducing the content of the NOTICE file.

   7. Disclaimer of Warranty. Unless required by applicable law or
      agreed to in writing, Licensor provides the Work (and each
      Contributor provides its Contributions) on an "AS IS" BASIS,
      WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
      implied, including, without limitation, any warranties or conditions
      of TITLE, NON-INFRINGEMENT, MERCHANTABILITY, or FITNESS FOR A
      PARTICULAR PURPOSE. You are solely responsible for determining the
      appropriateness of using or redistributing the Work and assume any
      risks associated with Your exercise of permissions under this License.

   8. Limitation of Liability. In no event and under no legal theory,
      whether in tort (including negligence), contract, or otherwise,
      unless required by applicable law (such as deliberate and grossly
      negligent acts) or agreed to in writing, shall any Contributor be
      liable to You for damages, including any direct, indirect, special,
      incidental, or consequential damages of any character arising as a
      result of this License or out of the use or inability to use the
      Work (including but not limited to damages for loss of goodwill,
      work stoppage, computer failure or malfunction, or any and all
      other commercial damages or losses), even if such Contributor
      has been advised of the possibility of such damages.

   9. Accepting Warranty or Additional Liability. While redistributing
      the Work or Derivative Works thereof, You may choose to offer,
      and charge a fee for, acceptance of support, warranty, indemnity,
      or other liability obligations and/or rights consistent with this
      License. However, in accepting such obligations, You may act only
      on Your own behalf and on Your sole responsibility, not on behalf
      of any other Contributor, and only if You agree to indemnify,
      defend, and hold each Contributor harmless for any liability
      incurred by, or claims asserted against, such Contributor by reason
      of your accepting any such warranty or additional liability.

   END OF TERMS AND CONDITIONS
````

## telemetry/NOTICE

Version `1.3.0`, repository `beam-telemetry/telemetry`, commit `8d8af76720856bcf26641ee1307658ad8f25e466`.

Git blob `19276dc18512936865f0a91499e0af1af647f582`; SHA256 `3ca23c239bc03e2bcd3899da04d4271370e230e30f7dc171c7e8ad35809c6bb0`; size `578` bytes.

Source: https://github.com/beam-telemetry/telemetry/blob/8d8af76720856bcf26641ee1307658ad8f25e466/NOTICE

````text
Copyright (c) 2018, Chris McCord and Erlang Solutions

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
````
