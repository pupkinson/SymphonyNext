# Authentik project access: Task1 dependency preflight

Status at 2026-10-04: **BLOCKED — environment_unavailable**. Task1 is incomplete. No authentication code, fixture, dependency pin or live configuration has been installed.

The owner approved the [implementation plan](../superpowers/plans/2026-10-04-authentik-project-access.md) at 2026-10-04T14:53:30Z, exact commit `233dda1878533a425574074b8d34344b50d41cf7`, tree `d68a8b7bd39c3f570523c3094d0b86faa3e0a466`. Its SHA256 is `f5285de9b65b40cacfa6b8a8ed57b15695807d894ef254e331f94941cc7acb9f`. The approved [design](../superpowers/specs/2026-10-04-authentik-project-access-design.md) remains binding.

Task `SN005-AUTH-PROTOCOL-01` was [accepted on GH33](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5981323352) before tracked writes. Its native worktree is `/srv/rdc-workspace/sn005-authentik-design-20261004/source`, feature branch `feat/sn005-oidc-protocol-20261004`. The initial source tuple above remains the product baseline for this documentation checkpoint.

## Observed results

| Check | Classification | Result |
| --- | --- | --- |
| Own linked worktree, exact approved HEAD/tree, canonical source hashes | VERIFIED | Clean baseline; one writer |
| Public Hex release and archive checksum | VERIFIED | Oidcc 3.9.0; 83,456 bytes; metadata checksum matches downloaded bytes |
| Maintainer tag and immutable source/API inspection | VERIFIED source observation | Tag v3.9.0 resolves to commit below; GitHub reports a valid tag signature |
| Compatibility with OTP28/Elixir1.19 | INFERRED | Declared minimum OTP27 and Elixir `~> 1.17`; no compilation performed |
| Native `/usr/bin/env mix --version` | BLOCKED | Actual exit127: Mix not found |
| Transitive resolution, compilation, semantic RED/GREEN, format/specs/full gates | UNKNOWN / NOT_RUN | Required toolchain unavailable |
| Production Authentik bindings, live eligibility/revocation and acceptance | UNKNOWN / BLOCKED | No live evidence; authentication remains disabled |

The failed version command ran at 2026-10-04T15:02:31Z under UID997 on `1c-db`. Its log SHA256 is `c6c5c3d5cda4b4da7367453fd661954085f206ae4e47ad572441f722cf3af68d`. The accessible native PATH, scratch environment and inspected owned toolchain directories did not provide Erlang/Elixir/Mix. This does not assert that the whole host lacks a toolchain.

Missing test infrastructure is not the product assertion failure required by Task1. Product implementation therefore stops before RED; neither this report nor dependency availability completes Task1.

## Dependency provenance

Candidate: **Oidcc 3.9.0**, Apache-2.0, not retired in the observed [Hex release metadata](https://hex.pm/api/packages/oidcc/releases/3.9.0).

- Archive: [oidcc-3.9.0.tar](https://repo.hex.pm/tarballs/oidcc-3.9.0.tar).
- Archive SHA256: `5a825092fe9b3214017a5777ba7ed871c6e3ff9532848f600f6c1fe31c5e41ce`.
- Annotated tag object: `e5bad400ecb538bc0d826d54516fd7ee3b1cb2a8`.
- Immutable source commit: [aa212d52d0140addf057c34917b734647401b34e](https://github.com/erlef/oidcc/tree/aa212d52d0140addf057c34917b734647401b34e).
- Signature status is GitHub-reported verification, not independent local GPG verification.
- Required dependency ranges: jose `~> 1.11`, telemetry `~> 1.2`, telemetry_registry `~> 0.3.1`; optional igniter. Actual transitive versions and `mix.lock` remain unresolved.

The archive was downloaded and hashed, not extracted, installed or executed. Source inspection does not prove archive/source equivalence or runtime compatibility.

Do not substitute the cached 3.7.2 documentation as a dependency pin: the maintainer's [GHSA-533g-4vf3-xwrj advisory](https://github.com/erlef/oidcc/security/advisories/GHSA-533g-4vf3-xwrj) covers versions before 3.9.0 and describes acceptance of encrypted unsigned identity tokens. Add an explicit encrypted-only unsigned token denial case to the planned signature tests.

## Contracts to prove with the wire fixture

The following are source observations and implementation requirements, not passed tests:

1. Fetch the separately configured discovery URL through bounded transport; decode it with `oidcc_provider_configuration:decode_configuration/1,2`, validate the exact issuer/endpoints, and construct `oidcc_client_context:from_manual/4,5`. Do not use unsafe issuer/HTTP overrides.
2. The exported authorization API is `oidcc_authorization:create_redirect_url/2`. Explicitly require PKCE and permit S256 only; provider metadata must not widen the approved algorithm or endpoint bindings.
3. Set `request_opts.http_adapter` on each outbound operation. Discovery/JWKS worker options are not inherited by token or later eligibility requests. The `request/5` adapter must verify TLS, deny redirects, enforce the response cap while receiving and share one absolute monotonic deadline across the exchange and any JWKS refresh.
4. `oidcc_token:retrieve_with_refresh/3` reports refreshed keys and retries validation without resending the authorization code. Permit at most one refresh, within the original deadline.
5. The library's `retrieve_a_token` can retry a token request after a first DPoP nonce challenge. Enforce at most one token POST per code exchange, including this branch. A wire test must count actual POSTs; an ambiguous exchange must never cause a second submission.
6. Verify the operator's signing allowlist, exact issuer/client audience/azp/nonce, nonempty subject, expiry and bounded future iat. Reject plain PKCE fallback, unsigned/encrypted-only unsigned tokens and request-selected keys/endpoints.

Relevant immutable source files are [provider configuration](https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_provider_configuration.erl), [HTTP adapter](https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_http_adapter.erl), [authorization](https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_authorization.erl) and [token exchange](https://github.com/erlef/oidcc/blob/aa212d52d0140addf057c34917b734647401b34e/src/oidcc_token.erl). Their exact Git blob identities are retained in the attempt evidence.

## Concrete test environment handoff

Provide an existing or owner-provisioned isolated runner with **Elixir1.19.x / OTP28, Mix and rebar3**, an absolute toolchain path or runner identity, and writable owned worktree/build directories. Task1 needs scoped public dependency retrieval and disposable loopback HTTPS listeners with a test CA and synthetic credentials. It does not need PostgreSQL, production Authentik credentials or production ingress changes.

First verify the real toolchain with `mix --version`, then run `cd elixir && mix setup`. Once infrastructure is ready, write the exact Task1 fixture/regressions and observe semantic RED with:

```sh
cd elixir
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

After the implementation, rerun those tests, `mix format --check-formatted` and `mix specs.check`, then the required broader gates. All these commands are presently **NOT_RUN**. The dependency-compatible protected profile and independent review remain the CI owner's responsibility.

This handoff authorizes no installer, root/sudo/Docker scope expansion, old cache/config copy or replay of previously refused owner-install/validator operations.

## Evidence and continuation

Native evidence root: `/srv/rdc-workspace/sn005-oidc-protocol-20261004`. It contains the immutable initial attempt/baseline, downloaded release/archive, dependency contract, source blob provenance, instruction manifest and runner request. The ignored SDD ledger preserves every ruling; no task-done record is emitted.

The attempt began at 2026-10-04T15:02:31.043350Z with a 1800-second wall budget, zero repair cycles and zero profile changes. Provisioning or continuation must preserve this history rather than reset the attempt. On exhaustion, stop/checkpoint and obtain a separate bounded admission.

This checkpoint changes only this document and its MANIFEST.sha256 entry. Runtime rollback is not applicable: no product/dependency/schema/config change occurred. Full SN004/SN005 acceptance, production isolation and live access revocation remain unverified.
