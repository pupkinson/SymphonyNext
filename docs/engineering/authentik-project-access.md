# Authentik project access: Task1 dependency preflight

## Queued credential expiry repair — 2026-10-06

Attempt `SN005-AUTH-PROTOCOL-01-QUEUED-EXPIRY-REPAIR-20261006` continues the
[owner admission](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6014254748).
[Executor continuation](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6014518354)
was published before tracked changes. Original T0 `2026-10-06T10:21:27Z` and
absolute deadline `2026-10-06T10:51:27Z` are unchanged; executor began at
`2026-10-06T10:38:27.167958506Z`, using only the remaining budget.
Baseline HEAD `be5371e71db363d5a07c7109d6dd010a6ceca7ef`,
tree `b0f828141ca90851f6e037d6f1741aaaa28496de`,
PR base `233dda1878533a425574074b8d34344b50d41cf7` were checked against fresh fetch.
One writer, two repair cycles, zero profile changes; only the six admitted paths changed.
Previous source reports below and both native HOLD attempts remain historical records.

The coordinator's unrun54-line draft was applied with identical diff SHA256
`23ff9acaa6b723c1db7b96b618ff21b78600dca56189c5acd91ee52c18de6904`.
Its first runnable probe produced51/2: one expired-identity assertion and one positive-control
test-wiring failure because the existing redaction fixture requires a recorded captured log.
Only the test wiring was corrected to capture and record the actual exchange logs.
An earlier Mix socket EPERM failure and default-sandbox fetch failure are infrastructure
observations, never semantic RED. Ordinary network permission kept the existing proxy and
toolchain; Elixir/Mix1.19.5 on OTP28/ERTS16.4 exited0. No profile or credential was replaced.

The existing unchanged HTTPS fixture holds JWKS while the caller is suspended. A real
Oidc.exchange worker completes verification, queues its identity in that caller's mailbox,
and exits normally before caller resumption. The negative test waits until the queued
credential has expired while the original monotonic network deadline still remains valid.
The positive control resumes while both bounds remain valid. Both assert exactly one token
POST, worker termination and absence of secret echo in captured logs.

From elixir, the same command was observed before and after the product change:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

Clean semantic RED: **51 tests/1 failure, exit2**, output SHA256
`998eb52eef0e0194d23f75d3dfafe3fceaacffa5e323c9efe3d7d5efacd14033`.
The otherwise verified expired identity was returned instead of `{:error, :forbidden}`;
the queued-valid positive control passed. Product bytes were unchanged at this RED.
GREEN: **51/0, exit0**, output SHA256
`41c5da25f86ce01f293a1756b6359bdbc888cbb0ebd68a061bca49ea3d84a103`.

The product keeps the existing monotonic acceptance guard first, preserving deadline error
projection. Only successful verified identities then receive a current UTC expiry check:
`credential_expires_at_ms <= System.system_time(:millisecond)` gives the fixed forbidden
result. URL results and existing errors pass through unchanged. This adds no public hooks,
token retry, network operation or alternate authentication architecture. Receipt-anchored
expiry, encrypted-only unsigned rejection, DPoP one-POST and previous wire regressions remain.

The first makeall stopped at strict Credo: the new helper clause exceeded120 columns,
exit2 (Credo child4). Coverage and Dialyzer were NOT_RUN in that invocation. The second
and final repair cycle split only the clause result line without changing behavior;
the full unchanged gates were repeated. No threshold/exclusion/check was relaxed.
Final makeall: **exit0,464/0/6,seed94528**, configured total/Config/Clock/Oidc100%;
format/specs/strictCredo passed and Dialyzer0errors/0skips. Output SHA256
`5a83478a3c0048e8f97ec65f53efc3c4394afa557e58188da6a2ea1acfea2510`.
Bootstrap12/0 and MCP input-contract11/0 exited0; manifest42/diff/PR-body checks exited0.
An optional second fixed-seed suite was NOT_RUN: makeall already executed the full suite,
and the unchanged deadline bounds final publication/cleanup. Dependency retrieval emitted
security advisories for frozen existing packages; dependency updates are outside this allowance.
Full gates and cleanup results are recorded in the final checkpoint; an absent check stays
NOT_RUN. A fresh private PostgreSQL17.11 fixture uses0700 data/socket directories, no TCP,
port55474 and its own sn004_fixture/sn004_test. Existing unprivileged Cloud developer tools
were reused without system installation, cache copying, root/sudo or production database use.
Initialization/start/database creation/version plus SELECT1 readiness all exited0.
The final owned stop/status commands retain their actual child exits before metadata work.

Evidence root: `/workspace/scratch/SN005-AUTH-PROTOCOL-01-QUEUED-EXPIRY-REPAIR-20261006`.
Actual argv/cwd/start/end UTC/exit/output hashes and source bindings are in command records.
All2776 prior Cloud FIXUP evidence entries were verified unchanged. Oidcc==3.9.0 and the
transitive lock remain frozen, SHA256
`13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`.
HTTPS fixture, CoreTest, shared support, testhelper, dependency/coverage policy and protected
CI/profile/installed native package remain unchanged. Six existing skips are preserved.

**VERIFIED:** real queued-expiry semantic RED/GREEN and queued-valid control with one POST.
**INFERRED:** the acceptance guard meets the specified caller-resumption refusal contract.
**UNKNOWN:** arbitrary scheduler suspension, clock rollback and live IdP eligibility/isolation.
**BLOCKED:** independent review of the new HEAD, new trusted exact-HEAD attempt and live
acceptance remain separate NOT_RUN stages. Author gates do not certify these stages.
Authentication stays disabled; Task2–5, merge/deploy and native attempt replay were not run.
Rollback source is the preserved be5371e; no runtime or schema rollout occurred.
Next bounded action is independent new-HEAD review and separately admitted trusted checking.

## Cloud fixup attempt — 2026-10-05

Status: **auth protocol and local retry fixtures GREEN; independent acceptance pending**.
Attempt `SN005-AUTH-PROTOCOL-01-CLOUD-FIXUP-20261005` follows
[admission5992821181](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5992821181)
and [independent review5413148652](https://github.com/pupkinson/SymphonyNext/pull/75#pullrequestreview-5413148652).
[ACCEPTED5992887315](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5992887315)
preceded tracked edits. Source HEAD `d6d029915dd45685092e2bbd08e9ad16559af6b8`,
tree `2ee1ebf979173923fdf56de05248363e7d8cd4ed`; branch `feat/sn005-oidc-protocol-20261004`.
Actual T0 `2026-10-05T10:42:16.822537Z`; deadline `2026-10-05T11:12:16.822537Z`.
One writer, **one repair cycle, zero profile changes**, exact eight-path allowlist.
Final committed-source gates/HEAD/tree, immutable command records, cleanup and evidence hashes are
in this attempt's checkpoint and [existing workpad33](https://github.com/pupkinson/SymphonyNext/issues/33).
No earlier attempt's allowance or outcome is reset; all previous report bodies below are preserved.

### Byte-compatible UTF8 headers and structural telemetry regression

The reviewed trigger is a valid signed HTTP200 token response with a quoted Content-Type parameter
containing actual synthetic ID/access/code/client-secret canaries and valid UTF8 U+0100.
The old String.to_charlist conversion succeeded but produced integer256. Oidcc's downstream
iolist_to_binary then raised inside its telemetry span and exposed the canary-bearing BIF argument list.
The real HTTPS regression walks metadata maps/tuples/lists/binaries and decodes integer-list/charlist
representations structurally. A substring search of inspect(metadata) is insufficient for this case.

Response-header names retain Oidcc's expected string representation; values now retain their original
binary bytes after a callback-local UTF8 validity check. Invalid UTF8 still fails closed within the
existing guard, before any exception reaches Oidcc. Valid UTF8 parameters are byte-compatible and
allow the otherwise valid signed identity. The new test checks stop/exception metadata and logs,
asserts no exception telemetry and exactly one real token POST. Existing nonUTF8/status/TLS/algorithm/
audience/size/deadline/lifetime/one-POST safeguards remain in place.

From elixir:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

Observed semantic RED: **49 tests/1 failure, exit2**, SHA256 `8f5fe7b6cc6306229b0e7ebe9b3c6ca3b6a58f7b093d45b25ce923ac67285a80`.
GREEN: **49/0, exit0**, SHA256 `cfe3bfdb404fafbd0c2faebef2708cb6081c4cc400b51bab8b9a9bc1d63a2643`.
The RED is credential disclosure detected structurally in integer-list telemetry, not fixture failure.
Encrypted-only unsigned tokens remain rejected; DPoP nonce/lost response remain at most one POST;
unknown-kid refresh is bounded; expiry remains anchored before refresh; late success is refused.

### Only three test-local empty memory fixtures

Before the change, focused CoreTest lines1022/1062/1102 with seed20261005 produced **3/2, exit2**:
normal continuation and progressive abnormal retry failed; initial abnormal retry passed.
Output SHA256 `f2b7339d11d56bf038635f21a3a315c01a49d81af4316e06556dac83d9634253`. Observed durations were2134.5/4186.9/375.8ms respectively.
Orchestrator startup schedules an immediate poll; the unchanged shared test workflow selects Linear.
Synchronous external polling is the source-supported delay hypothesis, not independently traced causality.

Only the three admitted test bodies select tracker_kind=memory in their owned workflow and bind an
empty issue list before starting their named orchestrator. Their cleanup stops only that owned process
and restores the prior memory issues. Production Orchestrator/tracker and global test support are unchanged.
Every existing assertion, completion/claim/attempt/error check, real timer and sleep remains unchanged,
including remaining-time ranges500..1100/39500..40500/9000..10500ms. Byte comparison proves all code
outside these three tests and their original assertion/timer bodies unchanged after removing only
local fixture setup/cleanup delta.

Focused memory run at lines1022/1067/1112: **3/0, exit0**, SHA256 `cc704f0b653064b2eaf3c8f9d110be05b76f40e009359ed10b067d8643f125ed`;
durations58.5/57.3/75.0ms for continuation/progressive/initial retry.
Full CoreTest `mix test test/symphony_elixir/core_test.exs --seed 20261005 --trace`:
**52/0, exit0**, SHA256 `7702c83e1f815ed761a8def220666cda6618f718f5f448a3f93cfb68cbab3212`.
These observations support the local fixture correction without weakening timer assertions.

### Broad evidence, frozen controls and handoff

The prior evidence manifest's3656 entries were checked without modifying that evidence root.
Historical baseline413/3/6 and d6d0299 candidate461/3/6 remain retained results, not rewritten as GREEN.
The old PostgreSQL recorder wrapperexit1 and original child stop exit **NOT_RECORDED** remain intact.
The new recorder persists the child command exit before optional Git metadata and uses a valid cwd.

A fresh owned PostgreSQL17.11 cluster has private0700 data/socket paths, noTCP,port55474,
role sn004_fixture/database sn004_test. Existing owned unprivileged Cloud developer binaries are reused;
no installation/cache-copy/native/root/sudo/shared database or profile change. Version/SELECT1 readiness
exited0; SN004_TEST_PG_SOCKET points only to this attempt. Own-cluster stop/readback and retained data/logs
are recorded in the final checkpoint.

Precommit full `mix test --cover --seed 20261005` with that fixture: **462/0/6, exit0**,
configured total/Config/Clock/Oidc **100%**, SHA256 `44e8e41fdaa0801e9840486269dcbb533f256dd7dd98923aebd7b32da26aa19e`.
StrictCredo exit0/no findings; Dialyzer exit0/0errors/0skips; bootstrap12/0 and MCP input-contract11/0 exit0.
Final makeall/privatePG, fixed-seed full coverage and committed-source command bindings are retained in
the checkpoint; a missing command is never inferred PASS. PinOidcc==3.9.0 and transitive lock remain frozen,
lock SHA256 `13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`.
Configured coverage threshold/exclusions and all six existing skips are unchanged.

Evidence root: `/workspace/scratch/SN005-AUTH-PROTOCOL-01-CLOUD-FIXUP-20261005`.
**VERIFIED:** authored HTTPS RED/GREEN, focused/full CoreTest, broad coverage100 and exact fixture-only delta.
**INFERRED:** external synchronous polling explains the prior timing delay; runtime calls were not independently traced.
**UNKNOWN:** live IdP bindings, production isolation/revocation and arbitrary scheduling behavior.
**BLOCKED:** independent exact-HEAD acceptance, dependency-compatible protected profile/trusted check and
live acceptance remain separate **NOT_RUN** stages. Source GREEN does not activate auth or admit SN005 live acceptance.
Config/Clock/testhelper/dependencies/shared support/production code/CI/status/profile remain frozen;
Task2–5, auth activation, merge and deploy were not performed.
Rollback source is the preservedd6d0299; no runtime/schema rollback is needed.
Next bounded action is independent new-HEAD source review and separately prepared trusted exact-HEAD check.

## Cloud gates attempt — 2026-10-05

Status: **BLOCKED by reproduced baseline CoreTest failures; Task1 protocol regressions GREEN**.
Attempt `SN005-AUTH-PROTOCOL-01-CLOUD-GATES-20261005` is separately approved in
[admission5991961338](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5991961338),
with [ACCEPTED5992031893](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-5992031893)
published before tracked edits. Initial HEAD `366eeb1ce8542016b56cb82ac3adfd7f2e6cb3f3`,
tree `507838760b2fdd6ee8bf8ea5f1ac6116f4e5bbc7`; branch `feat/sn005-oidc-protocol-20261004`.
T0 `2026-10-05T09:43:46.470138Z`; deadline `2026-10-05T10:13:46.470138Z`.
One Cloud writer, Task1's original13-path allowlist, **one repair cycle, zero profile changes**.
Previous reports below, their stopped budgets and refusals are retained verbatim.

### Three review findings: observed RED and GREEN

[Review5412576418](https://github.com/pupkinson/SymphonyNext/pull/75#pullrequestreview-5412576418)
is represented by real HTTPS/public-API regressions. The otherwise valid signed-token response carries
actual synthetic ID/access/code/client-secret canaries followed by a nonUTF8 byte in its header.
The old request callback raised UnicodeConversionError into Oidcc exception telemetry. Adapter request
exceptions now receive a fixed safe projection before crossing that telemetry boundary. Stop/exception
metadata and logs are checked for every canary; one real token POST is observed.

A controlled caller suspension lets a completed protocol worker queue its successful authorization
result before the deadline, then resumes the caller after expiry. The old API accepted it. The caller
now checks the absolute deadline before acceptance; a yield timeout uses shutdown only for cleanup,
discarding its result. A separate held-JWKS timeout proves worker termination and zero token POSTs.
This proves fail-closed acceptance, not OS scheduling guarantees under arbitrary suspension.
The existing staged TCP/TLS and pre-send/send-timeout assertions remain in place.

With a valid signed ID token, expires_in=1 and an unknown kid, the fixture delays only the refresh
response by1200ms. The old API restarted the access lifetime after refresh. Receipt UTC is now captured
at the completed token response before validation/refresh, and expiry is anchored to that receipt.
An already elapsed lifetime is refused; refresh count2 and token POST count1 are asserted.

Targeted command from elixir:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

Observed RED: **46 tests/3 semantic failures, exit2**, SHA256 `e4a26debc3cae490bf459e1ea38f7b3dbd9eb11e6060fc525fb0d490fc86a579`.
First GREEN: **46/0, exit0**, SHA256 `8edc9b794e2573fd906aaade987cdcdea69da31a95861abde1f02f7563e938e8`.
Additional timeout-cleanup and invalid-outgoing-header checks: **48/0, exit0**, SHA256 `f41e4927ca116e63b67c2db6dbc23d972f3383494efb17b89d895ad7df078183`.
Encrypted-only unsigned token rejection, DPoP nonce challenge and lost-response at-most-one POST remain GREEN.
The candidate removed redundant context/finish deadline branches: dispatch checks the shared deadline
before networking, receive checks it while reading, and the caller rejects completion after expiry.
The duplicate rescue/catch projection is one catch for error/exit/throw. Actual malformed-JWKS/header
exceptions and failed outbound-header submission cover meaningful error behavior; no artificial coverage
calls, test weakening, new ignores/exclusions/skips or threshold changes were introduced.

### Strict gates and broad baseline comparison

Token-only trusted_audiences=[] belongs to exchange options; authorization now uses only its pinned
Oidcc contract. All existing strictCredo findings are closed by line splitting and smaller fixture/helper
functions. Credo exit0/no findings; Dialyzer exit0/**0 errors,0 skipped**.
The unchanged configured coverage threshold100 is met: **total100%, Config100%, Clock100%, Oidc100%**.
The exact Oidcc3.9.0 pin and transitive lock remain unchanged:
lock SHA256 `13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`.
Fresh mix setup exited0 on Elixir/Mix1.19.5 and Erlang/OTP28.5.

Fresh owned PostgreSQL17.11 data/socket directories0700 use no TCP, port55474,
role sn004_fixture/database sn004_test. Existing owned Cloud developer binaries were reused without
system installation, cache-copy, root/sudo or profile change. Version/SELECT1 readiness exited0.
SN004_TEST_PG_SOCKET selects only this attempt's fixture. Its data/logs and own-cluster stop are retained.

Broad comparisons used each source's original lock and the same private fixture, with:

```sh
SN004_TEST_PG_SOCKET=<this-attempt-private-socket> mix test --cover --seed 20261005
```

Baseline `a2deb11d0be829ffca201b2b81a7505fe354d0a6` in its isolated clean worktree:
**413 tests/3 failures/6 existing skips, total100%, exit2**, SHA256 `c67142349d45cd615761594646ab3410633477eb17b1fabe1b04518eeedb1842`.
Candidate: **461 tests/3 failures/6 existing skips, total100%, exit2**, SHA256 `4dd93be2a2231af64d2e57e299438e0a5089d2379e755d9729002412f06deda4`.
Both runs fail the same unchanged CoreTest cases:

| Case | Broad baseline remaining ms | Candidate remaining ms | Minimum ms |
| --- | ---: | ---: | ---: |
| first abnormal worker exit waits before retrying | 7916 | 7921 | 9000 |
| normal worker exit schedules active-state continuation retry | -2103 | -3128 | 500 |
| abnormal worker exit increments retry attempt progressively | 37922 | 37921 | 39500 |

Thus the previously unknown third broad-baseline outcome is observed RED as well.
These are diagnostics under the current Cloud environment, not permission to repair CoreTest,
orchestrator/shared support, timings or assertions. Their source is unchanged; all PostgreSQL tests pass.

The final committed-source commands, UTC/cwd/exits, output hashes, sourceHEAD/tree and cleanup readback
are recorded in the evidence checkpoint and GH33. Precommit format/specs, strictCredo, Dialyzer,
bootstrap12/0 and MCP input-contract11/0 exited0. Full makeall with the private PostgreSQL fixture: **exit2 at coverage**,461/3/6, coverage100%,
output SHA256 `73ae5506fd3db455e9f3ba92125c76bd29052824cacfb7a07d119c0c559636d0`. Setup/build/format/specs/strictCredo succeeded; make's
Dialyzer target was **NOT_RUN** after coverage failure, so Dialyzer was run separately with exit0.
Evidence root: `/workspace/scratch/SN005-AUTH-PROTOCOL-01-CLOUD-GATES-20261005`.
Raw logs, failed preflight/lint probes and HTML coverage are preserved; evidence manifest hashes them.

**VERIFIED:** three semantic RED-to-GREEN regressions, targeted48/0, strict lint/Dialyzer/coverage100,
and all three timing failures on both broad baseline and candidate.
**INFERRED:** corrections meet the reviewed refusal contracts; independent new-HEAD approval is absent.
**UNKNOWN:** live IdP bindings, production isolation/revocation and arbitrary scheduling behavior.
**BLOCKED:** full Task1 acceptance while the unchanged CoreTest source gate is red; independent exact-HEAD
review and protected dependency-compatible trusted check remain **NOT_RUN** separate stages.
Auth stays disabled; Task2–5, dependencies, protected CI/profile/status, merge/deploy were not changed.
Rollback before merge is the preserved366eeb1 source; no runtime/schema rollback is required.
Next bounded action is independent new-HEAD review plus separately scoped CoreTest/environment diagnosis.

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
