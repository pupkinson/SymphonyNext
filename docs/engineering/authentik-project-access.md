# Authentik project access: Task1 dependency preflight

## Cloud repair attempt — 2026-10-05

Status: **BLOCKED — repair allowance exhausted; source gates remain red**.
Attempt `SN005-AUTH-PROTOCOL-01-CLOUD-REPAIR-20261005` was separately admitted in
[GH33 comment5991103450](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5991103450)
and [ACCEPTED before tracked edits](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5991221882).
Source/base HEAD `d087257670213a545e9dcd5600bcea68b421c327`,
tree `698307f7ea86a1bdef1559069ce353d731d27ed4`; one Cloud writer, same13-path Task1 allowlist.
T0 was 2026-10-05T08:46:52.850766Z; deadline 09:16:52.850766Z, 1800 seconds including preflight.
Repair cycles: **2/2**, profile changes: **0**. Implementation stopped after failed broader gates.
The preceding native and Cloud reports below retain their original results and budgets.

### Reviewed protocol corrections and wire evidence

The five findings in [review5411919574](https://github.com/pupkinson/SymphonyNext/pull/75#pullrequestreview-5411919574)
are represented by source corrections or independent wire assertions:
unsupported token statuses are rejected before response bodies reach Oidcc telemetry;
a deadline-owned task bounds the exchange and cleanup, with remaining-time checks and a send timeout
immediately before transmission; zero/negative access lifetime and final expiry at/before current UTC
are rejected; Oidcc trusted audiences are closed and identity admits only this scalar/singleton client;
trusted-CA/wrong-SAN refusal is separate from untrusted-CA refusal.
A single-client token without optional azp remains valid. Multi-audience tokens are all refused.
Crypto remains owned by Oidcc3.9.0; the dependency and transitive lock are unchanged
(lock SHA256 `13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`).

Observed semantic RED: **39 tests/5 failures, exit2**, covering202 telemetry disclosure,
zero/negative lifetime, additional audience and multi-audience/missing-azp.
RED output SHA256 `444804ab3d9b5fc42575a1c162c6f568d7e5cd7a5e8201b8755bc69c244aae84`.
The real staged TCP/TLS test fills a private listener's accept queue, releases it after600ms,
then delays TLS SNI handling700ms. On original d087257 with a1500ms deadline, return took2534ms:
**1 test/1 failure, exit2**, output SHA256
`61fa05c559fa324fa3d8861687096604521b55de51251db1f7777953369e75e4`.
That diagnostic worktree used current test/fixture overlays only; original product and lock stayed pinned,
and the overlays were restored afterwards. The corrected source passes the bound and observes no POST,
including after the delayed peer resumes.

Final targeted command from elixir:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

Result: **43 tests/0 failures, exit0**, SHA256
`a4047512447cfee4cb1c20d863de2baf25cb2888baea8fa5acea23e0ab058779`.
HTTP202 captures stop/exception telemetry and logs and checks actual ID/access/code/secret canaries
with one POST. Encrypted-only unsigned rejection, DPoP/lost-response one-POST and one unknown-kid
refresh remain passing. Missing access expiry, malformed discovery/keys and429 were additionally exercised.
The wrong-SAN finding was a missing proof; its new wire assertion passes with existing Mint hostname verification.

A FIFO deadline probe passed on the original source and was not semantic RED.
Its writer cleanup hung; the run was killed. A later fixture-directory collision reused a retained FIFO
because unique_integer is only VM-local; fixture roots now include OS PID and random bytes.
Both terminated runs and the unsuccessful probe are retained in the evidence directory.
A malformed-discovery regression then failed with a forbidden projection; decoding failures now return
the fixed dependency_unavailable reason. No ignored errors or coverage exemptions were introduced.

### Cloud PostgreSQL and unchanged CoreTest comparison

PostgreSQL17.11 Debian tools were downloaded/extracted into the owned evidence directory without
system installation, root/sudo or protected-profile changes. Private cluster/data and Unix socket0700,
listen_addresses='', port55474, role sn004_fixture/database sn004_test; version readback and SELECT1
both exited0. Only SN004_TEST_PG_SOCKET selects this disposable fixture.
The cluster is stopped at handoff; retained data/logs belong to this attempt.

The same three unchanged CoreTest lines1022/1062/1102 were run with seed20261005 on isolated
a2deb11 and d087257 worktrees, preserving each lock, and on the repaired source.
Each run had **3 tests/2 failures, exit2**: normal continuation retry and progressive abnormal retry
missed their remaining-time assertions; first abnormal retry passed in the focused comparison.
Output SHA256s: baseline `17fbd96098266b4d78b34b90c878c29dcca545c36c101a03955ce4c5e2038517`,
original `556c81d6756503ee18ec84cf327f30622e398b5348961d16629296e820b267c5`,
repaired `4c6a14afac0fa5403fa5efbcd5a569c40b4c89e6fd2d73e6376dc24f42666a7c`.
These results reproduce two baseline failures; they do not justify changing CoreTest/orchestrator or its timings.
The broad run also failed first abnormal retry; that case's broad baseline status remains UNKNOWN.

### Actual gates and remaining blockers

| Command | Actual result |
| --- | --- |
| elixir --version / mix --version | exit0; Elixir/Mix1.19.5, OTP28/ERTS16.4 |
| mix setup, baseline setup, original setup | exit0 |
| mix format --check-formatted within make all | exit0 |
| mix build within make all | exit0; escript built, not executed |
| mix specs.check | exit0 |
| mix credo --strict | exit12; six findings |
| mix dialyzer --format short | exit2; one error |
| make all with PostgreSQL fixture | exit2 at strict lint |
| mix test --cover with PostgreSQL fixture | exit3; 456 tests/3 failures/6 existing skips |
| bootstrap snapshot unittest | exit0; 12/0 |
| unchanged MCP input contract unittest | exit0; 11/0 |

Full coverage is **99.64%**, Oidc **97.24%**, Config/Clock **100%**.
Full-run output SHA256 `27333c521e837becbd09896885df112106add7b67046eab33300dbb5368ccf96`.
All76 PostgreSQL fixture failures from the prior Cloud attempt are cleared; remaining full-suite failures
are the three named CoreTest timing cases. Coverage100 remains required and unachieved.
Line-level HTML coverage is retained; no threshold/exclusion/skip change occurred.
Credo reports long lines at Oidc159/216 and test134, nested bounded task creation, and two fixture
respond functions above the complexity limit. Dialyzer rejects create_redirect_url's options contract:
trusted_audiences was added to the shared authorization/exchange options map.
The exhausted repair allowance prevents another correction in this attempt.

Evidence root: `/workspace/scratch/SN005-AUTH-PROTOCOL-01-CLOUD-REPAIR-20261005`.
Command records contain UTC start/end, argv/cwd, actual exit and output hashes; checkpoint and evidence
manifest contain the final HEAD/tree, changed paths, fixture and source hashes, PR identity and cleanup.
Manifest/diff/actual PR-body checks and exact-HEAD follow-up results are recorded there and in GH33.
**VERIFIED:** targeted assertions, fixture/readbacks and the actual failures above.
**INFERRED:** source corrections implement the reviewed refusal contracts; independent approval is absent.
**UNKNOWN:** unexecuted broad baseline status of the third timing failure and production bindings.
**BLOCKED:** Task1 source acceptance by lint/Dialyzer/coverage, independent new-HEAD review and trusted check.
Protected dependency-compatible profile, trusted status, independent review and live acceptance remain **NOT_RUN**.
Production auth remains disabled. Task2–5, CI policy/profile edits, merge and deployment were not performed.
Rollback before merge is the preserved d087257 source; no runtime/schema rollback is needed.
Next bounded action requires separate admission for the remaining Task1 gate defects; CoreTest repair needs its own scope.


## Cloud attempt — 2026-10-04

**Current status: targeted GREEN; Task1 acceptance remains BLOCKED by broader source gates.**
This is a separately authorized Cloud attempt, not a continuation with a reset of the native budget.
[Cloud ACCEPTED](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5983786826)
was published before source writes. Initial HEAD/base `a2deb11d0be829ffca201b2b81a7505fe354d0a6`,
tree `741c6c5615f38bd3626a4eddf4bda6e8bb5224c7`, branch `feat/sn005-oidc-protocol-20261004`.
Attempt `SN005-AUTH-PROTOCOL-01-CLOUD-20261004T195151Z` began at
2026-10-04T19:51:51Z, deadline 2026-10-04T20:21:51Z (1800 seconds, including preflight).
Two repair cycles are consumed; profile changes: zero. One writer; no subagents.
The native report below is retained as history, with its original results and refusal boundaries.

### Verified dependency and protocol behavior

Elixir 1.19.5 / Mix 1.19.5 / Erlang OTP28 are available. `mix setup` and
`mix deps.compile` both exited 0. Dependency pin is `{:oidcc, "== 3.9.0"}`;
new locked transitive releases are JOSE 1.11.12 and telemetry_registry 0.3.2,
with existing telemetry 1.3.0 unchanged. The public release/archive was fetched again;
archive SHA256 `5a825092fe9b3214017a5777ba7ed871c6e3ff9532848f600f6c1fe31c5e41ce`
matches current Hex metadata. Apache-2.0 notices and the installed 3.9.0 source APIs were read.
Compilation verifies compatibility for this Cloud toolchain; it does not attest a protected runner.

Config accepts exact operator HTTPS endpoints, asymmetric signing algorithms and confidential
client-auth methods; secret values and CA overrides are rejected by `Config.load/1`.
Only secret references are stored. A fixture injects its disposable CA directly into its owned
configuration; that CA is not loaded by the product config parser. `activation_allowed?/1`
remains false for every Task1 configuration; no auth supervisor, routes or authorizer are installed.
Clock exposes UTC/monotonic milliseconds and one random 32-byte epoch per start.

Oidcc owns PKCE and token signature/claim validation. The adapter loads the independent discovery
URL, compares exact issuer/authorization/token/JWKS/logout bindings, strips provider-selected
optional transports/profiles, requires S256, and restricts signing/client-auth metadata.
TLS verification includes hostname checking through Mint. HTTP/1 uses a fresh passive connection,
no redirects/retries, a 1MiB raw response bound enforced before parsing each received fragment,
and one absolute monotonic deadline capped at 5000ms for all discovery/key/token operations.
The 1MiB cap includes HTTP framing and headers, so the usable body limit is slightly smaller.
ID tokens are limited to 16KiB; external key headers and encrypted-only/unsigned tokens are denied.

Each exchange has an atomic one-POST budget. Non-success token responses, including a DPoP nonce
challenge, stop at the transport boundary and never trigger the library's implicit token retry.
Unknown-kid validation permits one JWKS refresh without resending the authorization code.
Identity contains exact issuer/nonempty subject, optional sid, bounded credential expiry and private
token material; email/roles/group claims never become identity or grants.

### TDD and gates

The disposable HTTPS fixture uses a generated test CA and signed server certificate, real discovery,
JWKS and token endpoints, real JOSE-signed tokens, one-time codes and request counters.
The first infrastructure runs exposed certificate/teardown defects; they are retained and are
**not product RED**. After fixture readiness passed, semantic RED was 28 tests / 27 failures
from missing Config/Oidc/Clock, exit 2. RED log SHA256:
`b876378ec1bf65c53b215f24881ebd569c339fe88a2ea9b22c5df42a552193cc`.
Initial GREEN was 28/0. A further regression exposed malformed URI acceptance; it was fixed
within repair cycle 2, alongside the real captured-log assertion correction.
Final targeted command was:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

Final targeted result: **32 tests / 0 failures, exit 0**. GREEN log SHA256:
`8a085f04b65d43df116445cce1652ca6080f5aa1f121c19ce6051b2c0e8320fe`.
This includes encrypted-only unsigned token denial, DPoP/lost-response one-POST checks,
unknown-kid refresh, expiry/nonce/audience/signature/azp/future-iat/subject failures,
TLS trust failure, endpoint/redirect/size/deadline bounds and missing/oversized secret errors.

| Command | Actual result |
| --- | --- |
| `mix setup` (initial and pinned) | exit 0 |
| `mix deps.compile` | exit 0 |
| targeted RED | exit 2, 28/27; HTTPS readiness passed |
| final targeted GREEN | exit 0, 32/0 |
| `mix format --check-formatted` | exit 0 |
| `mix specs.check` | exit 0 |
| `mix credo --strict` | exit 0 |
| `mix dialyzer --format short` | exit 0, zero errors |
| bootstrap snapshot unittest | exit 0, 12/0 |
| unchanged MCP input contracts unittest | exit 0, 11/0 |
| `make all` | exit 2; 445 tests / 79 failures / 6 existing skips; coverage 89.66% |

The first full coverage run was 441 tests / 78 failures / 6 existing skips, exit 3:
76 existing SN004 fixture failures due to missing `SN004_TEST_PG_SOCKET`, plus
`CoreTest: normal worker exit schedules active-state continuation retry` and
`CoreTest: abnormal worker exit increments retry attempt progressively` timing failures.
Those existing sources were not changed. PostgreSQL binaries were not found on PATH or at
`/usr/lib/postgresql`; no installation, shared database fallback or coverage exclusion was added.
Initial configured coverage was 89.15%, Oidc 91.67%, Config/Clock 100%; final values are recorded below.
Final configured coverage is **89.66%**, Oidc **95.31%**, Config/Clock **100%**.
The final full run has 76 missing-PostgreSQL fixture failures and three CoreTest timing failures:
`abnormal worker exit increments retry attempt progressively`,
`normal worker exit schedules active-state continuation retry`, and
`first abnormal worker exit waits before retrying`. The complete failure-name list is
retained in `full-failures.json`. All Task1 tests passed in that full run.
Oidc's remaining uncovered defensive/error branches are a source acceptance blocker in their
own right; supplying PostgreSQL alone does not produce the required 100% coverage.
Current Hex resolution also reports advisories on unchanged baseline dependencies; this attempt
pins Oidcc only and does not silently upgrade the baseline dependency set.

### Handoff boundary

Evidence directory: `/workspace/scratch/sn005-cloud-20261004T195151Z`; command records contain
UTC start/end, argv/cwd, actual exit codes and output SHA256. It retains native GH33 history,
ACCEPTED, both infrastructure failures, both product REDs, GREENs, all gate failures and repairs.
The final checkpoint records HEAD/tree/source/fixture/lock hashes and all unchanged-policy blockers.

Task1 is not accepted from targeted GREEN alone. Full 100% coverage, an owner-prepared
dependency-compatible protected CI profile, independent read-only review and trusted exact-HEAD
check remain required. No production Authentik bindings, auth activation, Task2 migration,
protected CI/profile change, trusted status, merge or deployment occurred. Full SN004/SN005 and
live revocation acceptance remain BLOCKED. A new source repair needs separate bounded admission;
this attempt does not acquire more repairs by changing its label.

## Native attempt history (original report retained)


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
