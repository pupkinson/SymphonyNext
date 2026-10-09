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

## Dependency context and wire regression continuation — 2026-10-06

Attempt `SN005-AUTH-PROTOCOL-01-DEPENDENCY-CONTEXT-20261006` uses the separate
[owner admission](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6019281088)
and [executor ACCEPTED](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6019741212).
T0 `2026-10-06T15:33:59.000Z`, absolute deadline `2026-10-06T16:03:59.000Z`, maximum1800s includes cleanup
and publication. One writer, repair cycles **2/2**, profile changes **0/0**.
Owned detached worktree `/workspace/scratch/sn005-dep-context-src` starts at HEAD `8c5828b1a5c4a2261fb2cd0a021235109a8e07a3`,
tree `496889153378c3e22bd58c96cf0f6855364117e5`, base `233dda1878533a425574074b8d34344b50d41cf7`; fresh explicit-ref fetch matches all three.
An earlier read of stale remote-tracking refs exited128 and is retained; it was
not used as source identity. Existing source/native budgets and native7cd15ad
terminal HOLD remain closed. All preceding report bytes are preserved.

Assignment requested gpt-6.1-sol/xhigh, with existing speed unchanged. Real client
requested/resolved/observed model, effort and speed are **UNKNOWN**: the current
thread, environment and selected runtime variables expose no such fields.
No replacement model agent or profile was started; this report does not certify
a GPT-6.1 Sol run. Managed Cloud is running/connected, configuration revision32,
existing network policy enforced. Composition0.5+MCP-SN031-r2 all8 hashes match;
project-policy SHA256831e8f86170211d2b800960c64ce977d7816167501fb9ec831bdbce702e097a9
is unchanged. Fresh Elixir/Mix1.19.5 on OTP28/ERTS16.4 and mix setup each exited0.
Frozen mix.lock SHA25613489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073
and all dependency pins remain unchanged. Hex emitted advisories for existing
frozen packages; no package update was performed.

### Verified context target

[oidcc-3.9.0-review-context.md](oidcc-3.9.0-review-context.md) contains complete
HTTP utility, token exchange, Elixir token wrapper, scope parser and telemetry
span/module source, plus complete Apache2.0 licenses and Telemetry NOTICE.
All8 actual selected source files match supplied size/SHA256/Git-blob records.
Oidcc's retained outer archive and recomputed inner checksum match frozen lock;
its five selected files match archive members. Telemetry's selected source bytes
match the immutable comparison; full Telemetry Hex archive equivalence remains
NOT_VERIFIED because no archive was retained. A tag alone was never treated as
package equivalence. The132351-byte inert source document is below700000 bytes;
PR source size/page estimates remain within unchanged2MiB/400-call limits.
No executable code is vendored and no native reviewer capability is widened.

### Actual baseline and regression matrix

Added **43 tests**:42 real signed-token HTTPS wire cases plus one recursive scanner
self-test. Scoped collectors attach only for each exchange, collect every request_token
start/stop/exception event with measurements/metadata, and detach only their own
handler in cleanup. Assertions scan logs and complete nested metadata, including
map keys/values, tuples, lists, integer lists/charlists and exception stack values.
They scan the actual fixture ID/access/refresh tokens, issued code and synthetic
client secret, including Base64/BasicAuth/URL and JSON-escaped representations.
The scanner self-test catches intentionally raised assertion failures for nested
charlist, escaped JSON and Base64 values; those are scanner controls, not product RED.
Every reached token endpoint case asserts exactly one real POST.

Missing/empty/wrong/malformed validUTF8 Content-Type is refused with fixed forbidden;
valid UTF8 parameters and application/*+json remain accepted. Malformed expires_in
string/list/map/null and access/refresh list/map/null give fixed forbidden. Valid
binary access/refresh, numeric-string expiry and binary/list scope retain acceptance;
map/null scope is refused. Malformed token_type string/list/map/null and unknown
credential-bearing nested extension fields remain accepted under the existing
contract, without observed metadata/log disclosure; no stricter contract is invented.
Missing/empty/nonbinary/invalid sole id_token and malformed JSON refuse identity.
Escaped keys/canaries, large integer and duplicate extensions are accepted; overflow
float and lone surrogate are rejected by both measured decoders. For duplicate
id_token keys both Jason and OTP JSON select the first value: signed-first accepts,
invalid-first refuses even with signed-last. These bounded observations are not a
general equivalence claim for all JSON.

The initial probe **94/2, exit2** incorrectly expected last-key selection. A separate
decoder probe measured first-key selection for both libraries, exit0; repair1
corrected only test expectations. This was not semantic product RED. The corrected
baseline **94/0, exit0** passed while product oidc.ex remained byte-identical.
The first full makeall stopped on new test-helper Credo readability/complexity,
exit2 (lint child12); coverage and Dialyzer were NOT_RUN in that invocation.
Repair2 only split layout/fixture clauses and used a sigil without changing wire
bytes or assertions. Candidate targeted **94/0, exit0** then passed.
**Product semantic RED NOT_OBSERVED; product patch NOT_NEEDED.**
Adapter SHA256056f08b40209a8d40a95d222ccc078d1db88ff33a6d922b1328b26ea0a73145b
is unchanged. Previous HTTP202/nonUTF8/unsigned/encrypted-only/DPoP/lost-response/
deadline/refresh/queued-expiry controls and assertions remain intact.

### Full gates and owned resources

A second makeall gave507/2/6 with configured coverage100, exit2: both failures were
unrelated dashboard LazyHTML Enumerable lookup. The executor had incorrectly used
MIX_BUILD_PATH=_build, mixing dev/test artifacts; test-only LazyHTML was absent from
that consolidated protocol. A read-only probe of standard MIX_BUILD_ROOT confirmed
actual _build/test and Enumerable.LazyHTML, exit0. No tracked repair, dependency,
toolchain, profile or gate setting changed. The same full gates were rerun with
MIX_BUILD_ROOT=/workspace/SymphonyNext/elixir/_build and MIX_BUILD_PATH unset;
MIX_DEPS_PATH selects the already verified existing package sources. This is standard
build-directory isolation, not a new source repair cycle or allowance reset.

Final `make all` from elixir: **exit0,507 tests/0 failures/6 existing skips,seed858462**;
configured total/Config/Clock/Oidc coverage100%; setup/build/format/specs/strictCredo/
coverage/deps/Dialyzer all passed with actual stage exits0. Dialyzer0errors/0skips.
Output SHA256 `0d8730840f576d99b5635c6ccb6dc7c4aa1acff90253dc13c6561347f71a017f`.
Bootstrap12/0 and MCP11/0 exited0. Source byte/allowlist/composition/budget validation
passed; final manifest/diff/actual PR-body/remote identity are recorded in the
publication checkpoint, never inferred from an unrun command.

Owned PostgreSQL17.11 has new0700 data/socket directories, no TCP listener, own
sn004_fixture/sn004_test and port55474; init/start/create/SELECT version()+SELECT1
all exit0. Existing unprivileged Cloud binaries were reused without toolchain or
system installation. Stop/status results below are actual retained child exits.
Full-suite tests did not change CoreTest/test_helper/mix/coverage controls.
Evidence directory `/workspace/scratch/SN005-AUTH-PROTOCOL-01-DEPENDENCY-CONTEXT-20261006` contains command argv/cwd/UTC/exit/outputSHA256 records,
raw outputs, source/evidence manifests and publication responses. No production DB
or protected/native resource was used. Auth remains disabled. Task2–5, native replay,
check publication, merge/deploy/GitHub Actions and live acceptance remain NOT_RUN.
Independent exact-new-HEAD source review and trusted native check are separate stages.
Author source gates do not establish full Task1/SN005/production acceptance.

### Recorded gate and cleanup evidence

| Command label | Exit | Output SHA256 |
| --- | --- | --- |
| 01-source | 0 | `7e6eed581ed16c77b5d0893b07cbef782f40cdbb47c21b1233d9aa108e0aec83` |
| 02-clean | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 03-elixir-version | 0 | `b7bc746ca83ed80c14bbb1d4a097a39a1e61e01f8d50cf14c35dcfefd2faa765` |
| 04-mix-version | 0 | `c5d8941ea9c5bb7a6b2a755fafb64c04ba91b6345eb1f62ec2e3b594353e4305` |
| 05-setup | 0 | `9a61e102152c091dae5ef2c8abdc7888a1f924cefcbd3edae50712c6beefb9be` |
| 06-test-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 07-product-unchanged | 0 | `e6ada66e4a22c74a474ac8ce56a73220eeaef3cc32a1aecb8673c70903a8924f` |
| 09-pg-init | 0 | `9add09dfdb16932de7f15012e851ac936cb681740cb0ead7f35fa631f5f6b7dd` |
| 08-baseline-targeted | 2 | `5b8c7dba5aba60701102d34cda511610f817ae56f70344a12546f3ebd3661169` |
| 10-decoder-probe | 0 | `ba69414b9455e083c0287a2714269f13716e68d7aa66de60d7197acf3143b890` |
| 11-pg-start | 0 | `66afd0411ccc09366e99fdd99b85f21899c8d2d064f5835126859618802153ad` |
| 12-pg-db | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 13-pg-ready | 0 | `a9e7617273063f924895faf86757f4faad02b0e55c4c66709453fd62d27f1f5b` |
| 14-repair-test-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 15-baseline-green | 0 | `328e880d7c40e3e4c32284c08849bd1875166fe1146ca553a2a43204fdfb2694` |
| 16-dependency-context | 0 | `eb154809252d2c07fd9cab4e1ef3de617239565407d71258ec9d3ddb5020796c` |
| make-stage-1791301497326750460-setup | 0 | `34daa5000c5cc12042f1ed8c7baff720be80b239f90367c83aec8160877e3481` |
| make-stage-1791301504632554481-build | 0 | `10c153ae9a01b37aff57f3c667ec951cb2ac28b2e0f9b2717231d480e8b8d45f` |
| make-stage-1791301516529573412-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 18-bootstrap | 0 | `fe12817179cd260fdfc89bac9f7be610d195981085d4bfeb80271e8f9e821c6d` |
| 19-mcp-source | 0 | `b70f99e7698c6bf03a3be0a373c296209c9eadd12117438974840b25bf4d2c86` |
| make-stage-1791301519471414715-lint | 12 | `2681714d8a53bd6d5fa0c327ee46f19d1e1ac2f26ff1daa920f2053d1b5a855f` |
| 17-make-all | 2 | `ab4b9871d23cc0f9021657872feb50c83f7f4d8a8ff3502a9c63ff77abb29a1e` |
| 20-fresh-fetch | 0 | `5816735dbc156cb8fe323d6b94e62a1c08befa9661b9a1504f83ecf2350d86ed` |
| 21-remote-baseline | 128 | `b555323ff03fc5db504ca60c860b2392f39b580df29d4c5918d87f1186f7a50d` |
| 22-cycle2-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| 23-candidate-targeted | 0 | `4a99bb1db3494fa7e684d062572ec5733578dadeaa4ee0e77f6f70e7b3330f8e` |
| 24-fetch-explicit | 0 | `3a7bf38588c4e1ebc85b98acc04de12427c6b8e6f98852a4fb4454291f8f7455` |
| 25-fresh-tuple | 0 | `2cb46be023bf2e5b264ddda3146c5a8f71e9d13749e8caad2485a93d155427e6` |
| make-stage-1791301794138604458-setup | 0 | `3179257998c68d8905f9ffe1503d1d1e03a5cc43d6ab3a8668fa1254b839439a` |
| make-stage-1791301796763780034-build | 0 | `10c153ae9a01b37aff57f3c667ec951cb2ac28b2e0f9b2717231d480e8b8d45f` |
| make-stage-1791301804955109548-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| make-stage-1791301805840386513-lint | 0 | `b653736cf586b36c7c797dc25eda1e0df80007a4ccf4ddc00444ecc7e421bb33` |
| make-stage-1791301811169595445-test | 2 | `0b020096575eb28cff46af0c982f7b2c5a744a15fb9e67c56e9a322e17a967d2` |
| 26-make-all-green | 2 | `6636d76d8cb74aae102756214facb2d98c4bfa228e13a0486a5823224ac48d01` |
| 27-build-isolation-probe | 0 | `d31366e8d415451b99ab741300ee6bde74fe1cb95dae9f096e9760a615d6d0b1` |
| 28-source-validation | 0 | `6994db8c3d7fa7a47572976b30c442542192f79f329e3c6895cc3d1ec9b10754` |
| make-stage-1791302070144250426-setup | 0 | `1bf556349d1e46126f1e59344fbb4dd072f5f08bf59320416db42aa47a370822` |
| make-stage-1791302072810775294-build | 0 | `691612a71a587486b8ad4d5cf830121efd5e8fc38f57441dcd1705e54eb3b215` |
| make-stage-1791302086851248470-format | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| make-stage-1791302087890501507-lint | 0 | `1ed4de28d5b27be949abc73a1629cfba6779890757a858fab961551a5421f079` |
| make-stage-1791302093609418230-test | 0 | `18e068abde22c5058cd4534c6ad596a4617642aca2d9f3b034a5ca1404badb47` |
| make-stage-1791302183029845848-deps.get | 0 | `a2bfa93ccef1e0a8b5d91868cee09af9f2a8bd3b8c275bedb8e6f91db0f045bd` |
| make-stage-1791302186478129065-dialyzer | 0 | `4805498672ca638516d1bd6f927a6bf29474c0c425494b7baa643298887fde69` |
| 29-make-all-isolated | 0 | `0d8730840f576d99b5635c6ccb6dc7c4aa1acff90253dc13c6561347f71a017f` |
| cleanup-pg-stop | 0 | `ca19178a35ab4153b75b494963b66ce8243e1b94c173107c87b44d09db23652d` |
| cleanup-pg-status | 3 | `e138ccb54fdb08283c6eb21159c53207bbbbf07077246e2804e18d22efe6e250` |

Exact argv/cwd/start/endUTC for these records are retained in commands.jsonl; finalization adds later records to the final evidence manifest/checkpoint.

## TLS fixture source attempt — 2026-10-07 (BLOCKED checkpoint)

`SN005-AUTH-PROTOCOL-01-TLS-FIXTURE-20261007` is a new source attempt, independent
of closed source2/2 and immutable native42283ecf. [ACCEPTED6036287648](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6036287648)
preceded tracked edits. T0 `2026-10-07T10:39:04Z`, absolute deadline
`2026-10-07T11:09:04Z`, one writer, repair cycles **2/2**, profile changes **0**.
Implementation stopped after cycle2 failed; this checkpoint does not grant another cycle.
Requested GPT-6.1 Sol/xhigh/current client speed; actual backend/effort/speed **UNKNOWN**.
No model was substituted and no additional agent was started.

Fresh connector/fetch and exact blobs verified baseline HEAD
`6925de7e291d8cb36f83493d254679527a83c34d`, tree
`b10931da9fa383bb5f22ca36f5f89e0038385e25`, PR base
`233dda1878533a425574074b8d34344b50d41cf7`. HEAD remains unchanged; the owned
`/workspace/scratch/sn005-tls-fixture-src-20261007` checkout is **DIRTY**, with an
uncommitted six-path draft. Commit/non-force push/new remote source are **NOT_RUN**.
Primary checkout remains clean. Frozen fixture/test/product blobs respectively:
`8656a8602b7641b1f0a6450ab95f221b2d8b3405`,
`be43772cf9dfb2ec029203d59b66becbd4ac1b05`,
`0add8aba2e92d70d179e1e836b2d6fb81e07a4c4`.
Product bytes, dependency lock and protected controls have no delta.

All eight spec-index composition hashes verified for0.5+MCP-SN031-r2; policy0.5
SHA256 `831e8f86170211d2b800960c64ce977d7816167501fb9ec831bdbce702e097a9`.
Elixir/Mix1.19.5, OTP28/ERTS16.4 and setup succeeded. Cloud observed revision89,
quota4CPU,16GiB,pids.max=max, OTP smp4:4 and empty ERL_FLAGS differ from owner-reported
protected2CPU/4GiB/pids256/+S2:2/networknone-loopback. **Cloud equivalence is not proved**.

Owner-reported native42283ecf: HOLD worker_stage_exit_coverage, final1, coverage2,
507/1/6,100%,seed876309/maxcases4; tls_accept expected1/observed0 at original line531.
Owner-provided worker-log SHA256
`94f5765f898350c31b23c18b9102c843e080a302463210edb1a51ba52a6d223c`
is **not independently verified**. Full private native log was not read.
The reported er_child_setup error32 has **UNKNOWN** causal relation. Native replay,
private native reads, resource/profile/worker changes and check publication were not performed.

### Actual observations and unfinished draft

The first unchanged line525 command was GREEN. Config/OIDC baseline94/0 and
full fixed-seed baseline507/0/6 also passed; there is **no Cloud product semantic RED**.
A new adverse setup-pause regression against the old fixture failed at SNI count2
instead of1. This is **fixture RED**, not the native tls_accept0 failure or product RED.
It shows setup/handshake sensitivity; exact native causality remains UNKNOWN.

The uncommitted fixture removes filler TCP/backlog0, acknowledges readiness, records
credential-free monotonic stage events, delays handshake dispatch600ms after an actual
client transport accept, and applies SNI700ms once per connection (OTP can call SNI
again). Discovery/JWKS200ms each deliberately consume the same exchange deadline;
this measures a composite real-wire deadline rather than relying on OS backlog timing.
The1500ms exchange deadline, elapsed<1700ms, tls_accept1/tls_handshake1 and latePOST0
assertions remain. The800ms adverse setup pause is a controlled mailbox timer barrier,
not an enlarged auth timeout. Caller/worker monitors and explicit fixture done replace
an absence assertion made after an arbitrary sleep.

Cycle1: both bounded negative controls passed; the new long-window positive expected
forbidden but observed unknown_outcome. Cycle2 corrected that fixed400 result expectation
and added real caller/worker lifecycle assertions. Config/OIDC then reported96/1.
The positive control exposed **another fixture defect**: ssl.recv returns a charlist,
while String.starts_with?/2 requires a binary. The fixture crashes before recording POST.
The positive wire control therefore remains **FAILED**, not GREEN. Its raw synthetic
request stack remains confined to local evidence; no raw request is published here.
A minimal next-attempt proposal is explicit binary mode for this SSL listener, followed
by the same positive/negative controls and all frozen gates. It is **NOT_APPLIED/NOT_RUN**;
repair2/2 is exhausted and no production adapter edit is proposed.

Candidate fixed-seed full run:509 tests/1 failure/6 skips, configured coverage100%,exit2.
It was already running when implementation stopped. PostgreSQL stop completed at
10:54:37.929072Z, before the final test/coverage command finished at10:54:53.001529Z;
no additional DB failure appeared, but this ordering is explicitly retained and does
not establish an uninterrupted candidate PG fixture gate. No candidate source READY claim.

Actual commands below ran from the owned worktree's `elixir` directory unless noted.
Complete argv/cwd/start/endUTC/exit/outputSHA256 are in local `commands.jsonl`.

| Label / command | Actual result | Exit | Output SHA256 |
| --- | --- | --- | --- |
| `mix setup` | dependencies unchanged | 0 | `ccaf88601071b79d900e450dc998fb76c434b84cd58baf4ab0d422ce70c71967` |
| `mix test test/symphony_control/auth/oidc_test.exs:525 --seed 876309 --trace` | 1/0 | 0 | `08d9360751b33ad28009e33a191bd4f1e61def4b6dba3d842092c19a425dca28` |
| `mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace --seed 876309` | 94/0 | 0 | `14ec4b465580e104cf99d04de4041b11bd2d701357247dc9cdf0e1aaa9410c45` |
| `mix test --cover --seed 876309 --max-cases 4` | 507/0/6;100% | 0 | `bb25174eeb871fc830d858a2711f9821b20d250bff80333ca2b53c587a3a1214` |
| `mix test test/symphony_control/auth/oidc_test.exs:544 --seed 876309 --trace` | 1/1;fixture SNI count2 | 2 | `31f22aa50df7c1f3e247638d2e72ca5f731db82d08dbebcee4d2aee8cdde061c` |
| `mix test test/symphony_control/auth/oidc_test.exs:525 test/symphony_control/auth/oidc_test.exs:555 test/symphony_control/auth/oidc_test.exs:568 --seed 876309 --trace` | 3/1;positive typed-result mismatch | 2 | `3313370826024772ee6b587a8155c858148cea4f85ddf042e3c8a8ecc198a6e0` |
| `same complete Config/OIDC command` | 96/1;positive charlist crash | 2 | `fbed59028d3a2174214d1ce17ae8f473c1332e09e5e292a9892d7195b7b13df6` |
| `same fixed-seed full coverage command` | 509/1/6;100% | 2 | `3d31a3017ed125dd2fc9ba6a19a59522fd7e5eb35cb294280690b622cc62b5ae` |

Format commands on the two admitted test files exited0. Full makeall, final format-check,
specs/strictCredo/Dialyzer, scheduler-load repeat and independent/trusted/live acceptance
are **NOT_RUN** after repair exhaustion; configured coverage100% does not offset test failure.
Bootstrap/MCP/manifest/scope/actual PR-body checkpoint checks have their actual results
in the final workpad, rather than assumed success here.

Owned PostgreSQL17.11 used fresh0700 data/socket directories, no TCP, private local
sn004_fixture/sn004_test,port55474; init/start/readiness exited0. Stop **0**, status **3**
(no server running), executed before optional metadata. Mix/ExUnit runs finished, both
negative protocol workers were killed and callers terminated; positive worker exited normally,
fixture listener/socket closed in after blocks even when its charlist assertion failed.
No owned DB or test VM is retained running. Evidence and source draft remain preserved.

Evidence root: `/workspace/scratch/SN005-AUTH-PROTOCOL-01-TLS-FIXTURE-20261007`.
Frozen lockSHA256 `13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`.
All earlier reports/history remain unchanged. Six allowed paths only; Task2–5/auth activation,
merge/deploy/native retry excluded. Independent readonly review of any future newHEAD and
separately reviewed CI retarget/trusted check remain separate **NOT_RUN** stages.

**VERIFIED:** baseline GREEN; fixture RED; two negative candidate wire controls and their
stage timestamps/lifecycle; candidate positive failure; source/lock identity; PG stop0/status3.
**INFERRED:** stage-relative dispatch removes dependence on an already elapsed setup timer.
**UNKNOWN:** exact native failure cause, actual model profile and Cloud/native equivalence.
**BLOCKED:** repair_cycles_exhausted; positive control/full candidate suite; all unrun gates,
commit/push/newHEAD and full Task1/SN005/live acceptance.

Checkpoint evidence limitation: initial document-reading and some diagnostic shells were
outside the command recorder; their complete argv/start/end/hash record is unavailable.
No retrospective timings or exit codes are manufactured. The listed test/setup/gate/cleanup
records are retained with actual outputs. The first manifest checkpoint exited1 because
the two changed test-file records were stale; checkpoint bookkeeping updated these existing
records and the repeated43-entry check exited0. No further fixture repair was applied.


## AUTH-TLS-SOURCE-20261008-NEXT — recovered source checkpoint (2026-10-08)

**RECOVERED; final author source gates passed, with earlier failures retained.**
Owner Denis explicitly admitted this new source-only cycle; ACCEPTED
[6064724231](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6064724231).
T0 `2026-10-08T16:39:48.149604+00:00`; deadline `2026-10-08T17:09:48.149604+00:00`; last300s reserved from
`2026-10-08T17:04:48.149604+00:00`. One writer, repair2/2, profile changes0, no additional
executors. Real visible model/effort/speed and Cloud task URL UNKNOWN; observed
session `01a1085f-06b1-722a-94dc-f5b333728047`. This is an additional bounded
project attempt, not a reset/replay of closed source/native history.

Published baseline at start / pre-publication Git HEAD `6925de7e291d8cb36f83493d254679527a83c34d`,
HEAD tree `b10931da9fa383bb5f22ca36f5f89e0038385e25`, PR base
`233dda1878533a425574074b8d34344b50d41cf7`. Own worktree
`/workspace/scratch/auth-tls-source-next-20261008` is DIRTY in exactly six allowed
paths at this pre-publication snapshot; commit/push outcome belongs to the final workpad readback. Primary and original historical worktrees
were preserved. Spec0.5+MCP-SN031-r2 composition hashes/policy0.5/source blobs
verified. Production Oidc/Config/Clock, dependencies/lock, shared infrastructure,
CoreTest, requirements, CI and thresholds are byte-unchanged.

### Provenance and observed fixture behavior

The original Cloud directories were available in this environment. Exported all
six dirty full files, binary unstaged patch, empty staged patch/untracked inventory
and2195 original evidence/data files before applying a copy in the new worktree.
Patch bytes match SHA256
`8683f7727ef571678bba27b1fba41f8eb1a87d1d30826030f79c51747e526025`;
original journal/manifest hashes independently matched. Read-only export manifest
`507e9c27967d6b43bc49642da1961fa69c723d1bfc098566bfc23323ae401b4f`.
No old scripts, drivers or processes executed. Original bytes rechecked unchanged.

Published baseline: staged1/0, Config/OIDC94/0, broad507/0/6, coverage100%, exits0
with seed876309 (broad max-cases4). Applying the recovered draft reproduced
**fixture RED3/1, exit2**: real ssl.recv returns a charlist to String.starts_with?,
then positive endpoint termination assertion detects function_clause. This is B,
not a semantic product RED or a reproduction of native A(tls_accept0).
Repair1 sets explicit `mode: :binary`; scoped3/0 and two bounded repeats with
two owned CPU workers pass. Recovered synchronization starts dispatch delay600ms
after real-client accept, awaits readiness/done, removes filler/backlog/timer-from-setup
dependency, and counts one SNI handshake despite TLS1.3 repeated SNI callback.
Negative tests retain1500ms deadline/<1700ms elapsed, tls_accept1/tls_handshake1,
POST0 after explicit endpoint completion and terminated caller/worker; positive
5000ms window receives a real POST once and fixed400. Adverse setup pause800ms
retains both delays measured from accept/SNI, not setup. Credential-free monotonic
ready/accept/dispatch/SNI/token/done and caller/worker observations are retained.

Initial candidate Config/OIDC96/1 and isolated unchanged line5161/1 failed because
the existing650ms absolute-deadline test saw token count0 instead of1. Bounded
confirmation96/0 and final96/0 passed; cause UNKNOWN, failed evidence preserved,
no assertion/deadline changed. Strict Credo exit16 found three IO.inspect diagnostics;
repair2 replaces them with explicit IO.puts+inspect, preserving observations and
all assertions. Strict lint/specs then exit0.

**Mandatory candidate broad seed876309/max-cases4:509/1/6, coverage100%, exit2.**
Failure is unchanged ProjectReadHttpTest line184/189: immediately after repository
and listener restart Health.readiness().ready was false. No causal attribution
to TLS or production defect is established; fixing unrelated source is outside
this frozen scope. One explicitly bounded confirmation on unchanged source/seed876309/max-cases4 then passed509/0/6, coverage100%, exit0. Earlier failure remains recorded; it is not rewritten as PASS. Full make all was executed once: exit0,
509 tests, 0 failures, 6 skipped; stage exits and actual seed are in the journal. A successful make
run cannot erase the failed fixed-seed gate. Related commit/push are authorized only after final manifest/scope/readback checks; their actual outcome is recorded separately.

### Gates, resources and handoff

Cloud Elixir/Mix1.19.5, OTP28 ERTS16.4, schedulers4;4CPU/16GiB/pids.max=max
differs from protected2CPU/4GiB/pids256/+S2:2/loopback-only. No Cloud/native
equivalence, native HOLD resolution or error32/PID causality is claimed.
Owned PostgreSQL17.11 uses new0700 data/socket, private Unix socket port55474,
no TCP, sn004_fixture/sn004_test. Init/start/readiness exits0. It remained alive
through complete fixed-seed coverage and make all/process waits; only then stop0
and status3 confirmed cleanup. CPU load children were terminated and reaped.
No foreign resource/process or historical attempt was changed.

| Command label | Actual exit | Complete output SHA256 |
| --- | --- | --- |
| `recovery-export` | 0 | `037ca34b5c08afafd4416a8904c0b3fe8d3b897aa959d2955066a21dda9217d6` |
| `elixir-version` | 0 | `b7bc746ca83ed80c14bbb1d4a097a39a1e61e01f8d50cf14c35dcfefd2faa765` |
| `mix-version` | 0 | `c5d8941ea9c5bb7a6b2a755fafb64c04ba91b6345eb1f62ec2e3b594353e4305` |
| `setup` | 0 | `6f25aa31edc985edb1f85da02cf70317bccdf43dc2382654128b1f73f2329a5b` |
| `baseline-staged` | 0 | `7904b5d8d20ce4c40354082a975bf8690a3db01e02003fb4100e85666148dadf` |
| `baseline-auth` | 0 | `6dc2c6a4e02cf45d61d0511de8c5fcc6895c1a1f64cb179c5b786bed95b0655c` |
| `baseline-cover` | 0 | `dde400414a097e6a92e86f20ad39047f6b174daa6ac5090806b1956d605a39a5` |
| `recovered-red` | 2 | `3a1755c2503a4d094989f13a746c121af6a35b6507e1930110bbd24509819e38` |
| `staged-green` | 0 | `8c9a96b3201eb9d3feba4abb1c9d7f75d35d5fa4fb82b0cab9b0d037a46b43c6` |
| `candidate-auth` | 2 | `9bb570e1efc7189ace99789dd4c8f9c6cbf8d6e69dc6c7f8047ac769e3cacfec` |
| `diagnostic-existing-deadline` | 2 | `eb3d34c8b25ed61e960492c691b89f11171de6124e0f7c74966c005b588810b5` |
| `candidate-auth-confirm` | 0 | `4bd8542679bae764d916d0d069c060295a1251597683d605df2d0d7a7fb5ad60` |
| `loaded-staged-1` | 0 | `47dbe1a65dec41482e4890162c109d0a1117171d9e35b9de375515b549dccd5c` |
| `loaded-staged-2` | 0 | `fbdb7c90b756ea46cb2c10642f03de6c54f28965b014d7f8f08116d6443cb937` |
| `strict-lint` | 16 | `d042ab7c348ae67ea2677ab9f56dad96c631081cb6582d5f2530bc50ba898364` |
| `strict-lint-green` | 0 | `51bd26ff6c53b4b01adccf56ff69eff9cab342fa94b6e2c35b1a9a5e5e2d09cd` |
| `final-auth` | 0 | `5d824fa58b6515d68e6cf951b27af8cde2c46efa1c6e898659a1500866c5c861` |
| `candidate-cover` | 2 | `980ed9b0e325a3de40327565f45446be7c82cd597ac1386cdee8f9d1eb311b4b` |
| `candidate-cover-confirm` | 0 | `d2eda5384c70ffabdc463a264ffa6c80837648773c62824f31af57800d93657b` |
| `make-all` | 0 | `fb3d98f74eaec8093c1243083ba81a9b6d8df008c1fe56218a2bbe50addee144` |
| `standalone-dialyzer` | NOT_RUN | — |
| `bootstrap` | 0 | `5ac80e6514bd6b15dbbd112f5610195d73a547778332a18d19ed1dbfb072be4e` |
| `mcp-contracts` | 0 | `078efdecf324cf6a54dd91322c09a2b3b24b9ab35e476e63652dfcc6d02149ea` |
| `cleanup-pg-stop` | 0 | `ca19178a35ab4153b75b494963b66ce8243e1b94c173107c87b44d09db23652d` |
| `cleanup-pg-status` | 3 | `e138ccb54fdb08283c6eb21159c53207bbbbf07077246e2804e18d22efe6e250` |

All argv/cwd/start/endUTC/stdout+stderr hashes and owned-resource evidence are
in `/workspace/scratch/AUTH-TLS-SOURCE-20261008-NEXT/commands.jsonl`.
Final MANIFEST/scope/PR-body/remote readbacks are subsequent checkpoint records.
Independent review of a new HEAD, trusted native check, native retarget/replay,
live acceptance, Task2–5/auth activation/merge/deploy are NOT_RUN. An exact-baseline
HEAD/candidate-tree packet and dirty patch/full files are prepared; independent exact-new-HEAD review remains NOT_RUN; the final packet binds any published commit after readback.
Next bounded step: independent exact-candidate source/evidence review, including the retained intermittent650ms/repository-restart failures, before any separate protected/native check. Historical native422 remains HOLD; full SN005/working Authentik acceptance
is BLOCKED. Checkpoint generated at `2026-10-08T17:02:52.702973+00:00` within the original budget.


## SN005-DEADLINE-POST-BARRIER-20261008 — separate source-only P2 repair

Owner admission [6068039141](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6068039141);
executor [ACCEPTED6068294050](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6068294050).
New T0 `2026-10-08T20:08:53.827823Z`, absolute deadline
`2026-10-09T00:08:53.827823Z`; implementation stops by23:38:53Z to reserve
the final1800s of this14400s allowance for export/publication/owned cleanup.
One writer; repairs2/2, profile changes0, no additional agents. Actual exposed
model/effort/speed and Cloud task URL UNKNOWN; session
`01a1085f-06b1-722a-94dc-f5b333728047`. This is a new admitted task; no old
allowance/counter/journal is reset. In particular, the old AUTH-TLS-SOURCE attempt
remains terminal **BLOCKED budget_violation**, including its28.518396s late
finalization corrected in [6065132178](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6065132178).
Old native422 HOLD and both prior source2/2 histories remain immutable.

Fresh baseline HEAD `bf1f983fe2ddc58d66d89836b8055bad98145eb7`, TREE
`047a5db67a56c9a1d3598c482aa320d3e3aa5f79`, PR BASE
`233dda1878533a425574074b8d34344b50d41cf7`; existing draftPR75 / branch
`feat/sn005-oidc-protocol-20261004`. Own initially CLEAN detached worktree
`/workspace/scratch/sn005-deadline-post-barrier-src-20261008`. Fresh GitHub/fetch,
worktree/process inventory and source/spec0.5+MCP-SN031-r2/policy0.5 hashes verified.
No competing source writer observed. Old dirty/staged/unstaged/untracked inventory,
full files and historical evidence bindings exported read-only before edits;
bound old evidence bytes were rechecked unchanged. This repair starts from the
published bf1 source, not a replay of the old TLS driver or an unverified draft.

### Observed baseline, fixture RED and minimal repair

Unchanged isolated deadline line516 failed1/1, exit2, token count0 instead of1;
the unchanged complete Config/OIDC baseline then passed96/0, exit0. Both outputs
are retained. This reproduces P2's missing scheduling precondition in Cloud; it
does not establish every historical failure's cause or reproduce native A.
Generic delay200ms applies separately to discovery/JWKS/token, so the original
test could spend its650ms budget before reaching the token endpoint.

The new regression first failed1/1, exit2, because no reference-bound validated
POST barrier event arrived, although the unchanged fixture returned a valid
signed identity. This is **fixture RED**, not semantic product/native RED.
Repair1 adds scoped reference/owner-bound barriers for discovery/JWKS/token.
The token barrier is reached only after `read_body` returns the complete body
and real POST/client/code/redirect/PKCE validation succeeds; neither a socket
accept nor the earlier call counter substitutes for that observation.

The negative test creates its absolute deadline ONCE, before public Oidc.exchange:
`started+650ms`. It confirms validated POST receipt before that deadline and
releases the response at the SAME deadline+20ms, using an absolute monotonic timer.
No deadline is renewed after POST. The caller returns fixed unknown_outcome
within850ms of the original start; one POST and caller/worker termination are
asserted. The valid signed positive control uses the same650ms window and succeeds
after immediate release. A separate test holds discovery until original start+150ms,
then holds JWKS past the original650ms deadline, proving shared pre-token budget,
no late token POST and cleanup. No artificial pre-token200ms race remains in the
post-receipt test. Invalid PKCE binding cannot emit the validated-body event.

Provider ready/released/done observations contain only references, stage names,
PIDs and monotonic timestamps. Barriers monitor their owner and fail after a
bounded1000ms no-progress interval; owner-death and abandoned-release controls
assert fixed503 and termination. Test cleanup cancels its timers, releases held
providers and stops the owned supervised HTTPS listener, preventing a failed
assertion from leaving an indefinite request wait. Negative tests verify response
release is after the original deadline, explicit done and provider/listener absence.

Initial3/0 fixture GREEN and candidate101/0 Config/OIDC passed. Strict Credo
exit4 found one overlong assert_receive line; repair2 introduces a local remaining
time without changing its value or timeout. Specs/strict Credo then exit0.
Final candidate Config/OIDC101/0 exit0 retains all prior controls. The test delta
replaces one race-prone test with six cases: net+5 tests, no new skips/exclusions.

Two bounded loaded repeats passed7/0 each, covering the three deadline cases,
owner/no-progress cleanup and TLS positive endpoint. Their original line selectors
also selected an expiry control rather than both TLS negatives; these outputs
are retained without claiming those missing scenarios. One explicitly corrected
six-scenario run under two owned CPU workers passed6/0: POST negative/positive,
pre-token budget, TLS negative/positive and adverse setup pause. All load children
were terminated and reaped. No retry-until-pass or seed change was used.
TLS1500ms/<1700ms, tls_accept1/tls_handshake1/latePOST0 and the working real-POST
positive endpoint remain unchanged. Native A is still OPEN/HOLD.

### Full gates and resource lifetime

`mix test --cover --seed 876309 --max-cases 4`:514/0/6, configured coverage100%, exit0.
`make -C elixir all` ran once:514/0/6, actual seed772427/max-cases8, coverage100%,
exit0. Setup/build/format/specs+strictCredo/coverage/deps/Dialyzer stage exits0;
Dialyzer0 errors/0 skips. The existing Makefile's MIX command was wrapped solely
to record each unchanged argv/exit; checks, thresholds and protected profiles
were not edited. Bootstrap12/0 and MCP input contracts11/0, exits0.

Own PostgreSQL17.11: new0700 data/socket directories, private Unix socket port55474,
sn004_fixture/sn004_test, listen_addresses empty (no TCP). Init/start/database/
readiness exits0. It stayed running through the final targeted suite, fixed-seed
coverage, full make and completed dependent process waits. Only after every
Mix/make process completed, pg_ctl stop exited0 and status exited3 (no server).
No foreign DB or process was used/stopped. Runtime Cloud Elixir/Mix1.19.5, OTP28
ERTS16.4,4CPU/16GiB/pids.max=max/schedulers4 differs from protected
2CPU/4GiB/pids256/+S2:2/loopback-only; equivalence is not claimed.

Production Oidc SHA256 `056f08b40209a8d40a95d222ccc078d1db88ff33a6d922b1328b26ea0a73145b`
and mix.lock `13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073`
remain unchanged, as do Config/Clock/CoreTest/test_helper, canonical requirements,
CI/worker/locks/policy/thresholds. Only the six admitted paths change; documentation
appends this checkpoint and MANIFEST refreshes their existing records.

### Actual command evidence

Complete verification/resource argv, cwd, start/endUTC, exits and separate
stdout/stderr/output SHA256 are in
`/workspace/scratch/SN005-DEADLINE-POST-BARRIER-20261008/commands.jsonl`.
The table below binds the complete combined output; no failure is rewritten as PASS.

| Command label | Exit | Complete output SHA256 |
| --- | --- | --- |
| `elixir-version` | 0 | `b7bc746ca83ed80c14bbb1d4a097a39a1e61e01f8d50cf14c35dcfefd2faa765` |
| `mix-version` | 0 | `c5d8941ea9c5bb7a6b2a755fafb64c04ba91b6345eb1f62ec2e3b594353e4305` |
| `setup` | 0 | `ee1a58046d7c6fc0bc5f8b67e28a3abe4c536626dbc9fc09bc90b55ae890b326` |
| `baseline-deadline` | 2 | `85ceb7070e384bb2a97de45b5e8643841f40cd6f7889b67379f9a8bd30ba6968` |
| `baseline-auth` | 0 | `fc0493c1d1c06096c7aebca700a6f0aa77f810ff28a210b2c666d6fd4d6fd7d2` |
| `fixture-barrier-red` | 2 | `beb47ff575931297920c2cfbeafab6d992446474e366344b08d360682f18b848` |
| `barrier-green` | 0 | `d930ccf11aa46e8d8b074747c3e544440f09bec6fc7450de6bd34e526b97f9ac` |
| `pg-init` | 0 | `ff692dd6e475e85d68904b803bae698f0cdb10f0f1b087bf6bd3138cad896a7a` |
| `candidate-auth` | 0 | `55b87a0880a7e463466912a86040038a2c901a8922127026bb7f67d2937cdacd` |
| `pg-start` | 0 | `66afd0411ccc09366e99fdd99b85f21899c8d2d064f5835126859618802153ad` |
| `strict-lint` | 4 | `3a8aba449ed5e3a1e928d2124b63e66fcb8695fce0451a47440897a0a1408f90` |
| `pg-createdb` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `pg-ready` | 0 | `b0e4a6f05a9389c169ea1ef2621ee19f67b4ab3cca36b42b388211b3226b97cc` |
| `strict-lint-green` | 0 | `e7be7c99933fde35702bcb16c44bfedaf525835a954f22444a64132ea51bfd42` |
| `loaded-controls-1` | 0 | `3a546ea2fc8fdd4086eaa15c751304a7c08dc91b15c0eef3d8fcd8a7890ff48d` |
| `loaded-controls-2` | 0 | `bcdcfcf318869e46f30c2a04c0a68d5f8678eb0c053e718e692a49b5e6114093` |
| `loaded-required-controls-1` | 0 | `ef2b40aebc2f4224293ed86171ae325a57d68ada15987716a26bc7995e0cdc9c` |
| `bootstrap` | 0 | `19205df4c3ef1da195d5483f61a3552b3046d3fee52101fbb61c75dd976f5d2e` |
| `mcp-contracts` | 0 | `90e9de3e62ea64ee1af964b7538416ef42a7aedb7871df281aced05f35f512ae` |
| `final-auth` | 0 | `be885eb22c54b06496324c8a1bbd886a0f70ae669ed1c0ac2ed44cf05ed95fbb` |
| `candidate-cover` | 0 | `294bd3a406e9b8edfde8382e2b03a4f34bb800c3725a8f81041fd48e1f74728c` |
| `make-stage-1791491622595809495-setup` | 0 | `fc011cc4198c0064f528dfe57afc346b89cbb99cd3fa62edde5a33df18091d08` |
| `make-stage-1791491625038539733-build` | 0 | `10c153ae9a01b37aff57f3c667ec951cb2ac28b2e0f9b2717231d480e8b8d45f` |
| `make-stage-1791491631676357513-format` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `make-stage-1791491632901501222-lint` | 0 | `9a8b87c1e5a081e99e36407f7ce3bf77b4d9a2df4dc0435e6042213c3845e123` |
| `make-stage-1791491639089288923-test` | 0 | `1ca8e78e81f1051320c29d11c1748771f071fe38b6ffc78b8e73a01cd6bee627` |
| `make-stage-1791491730753739900-deps.get` | 0 | `db093bb8992d050d0c0001876308c16024347ed25ed5aac2e91eec142d0b9b93` |
| `make-stage-1791491734815984235-dialyzer` | 0 | `3ef469a7b0285a1a7c38cfc6b51389e2695056e26dc8e9dfd5acd0a1306b4f0e` |
| `make-all` | 0 | `6a35605e4590cc7be8d0b55781a4826901c229cc2863bdd3ae3c1c1d20e78b36` |
| `dependent-processes-complete` | 0 | `eb5be4fb270ff7730da246614925f86a427127585839acd3680b79c40b681f05` |
| `cleanup-pg-stop` | 0 | `ca19178a35ab4153b75b494963b66ce8243e1b94c173107c87b44d09db23652d` |
| `cleanup-pg-status` | 3 | `e138ccb54fdb08283c6eb21159c53207bbbbf07077246e2804e18d22efe6e250` |

Tested executable source SHA256:

- `elixir/test/support/auth_oidc_fixture.exs`: `661f6b1acd6260bdf6a9f7a528ee7ebde33b1eadd06ca1af7c2937353be09122`.
- `elixir/test/symphony_control/auth/oidc_test.exs`: `4915535cb0efaa6db64409e0a7af1cb324ba974a56958332102640c90ada481e`.

This pre-publication report snapshot was generated at `2026-10-08T20:39:25.441459+00:00`; source test bytes
were rechecked after all gates. The worktree is DIRTY in the admitted paths until
explicit staging/commit. Final manifest/scope/PR-body/commit/non-force push and
fresh remote HEAD/tree/clean readback belong to the subsequent final workpad
checkpoint; they are not inferred from the tests. The final packet includes a
portable patch/full changed files, exact-source identities and complete retained
RED/GREEN/gate logs. No new owning issue/PR or trusted status is created.

VERIFIED: observed P2 baseline failure, fixture RED→GREEN, unchanged650/850 bounds,
real validated POST, pre-token shared budget, positive/negative TLS controls,
source gates and owned cleanup. INFERRED: removing the pre-token scheduling race
addresses the reproduced fixture precondition; it does not prove protected/native
behavior. UNKNOWN: actual exposed model/effort/speed and causes of all older failures.
BLOCKED: native quality/fullSN005/live Authentik acceptance. Independent review of
the new HEAD, trusted native check, live acceptance and Task2–5/auth activation/
merge/deploy remain NOT_RUN. PR90's blocked native dependency preparation is not
replayed. Next bounded step: independent read-only review of the exact published
candidate and this retained evidence; no second model is started by the author.


## Owner-down observer repair — SN005-OWNER-DOWN-OBSERVER-41D840

Denis launched one additional source-only repair for
[P2 inline4224147701](https://github.com/pupkinson/SymphonyNext/pull/75#discussion_r4224147701),
qualified by coordinator4224166358 and [handoff6069127083](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6069127083).
[ACCEPTED6069483906](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6069483906)
preceded tracked edits. T0 `2026-10-08T21:28:00.540139Z`, deadline
`2026-10-09T01:28:00.540139Z`; final1800s reserved from00:58:00.540139Z.
The preceding POST-barrier attempt remains CLOSED2/2; this separately admitted
additional cycle used1/1. Zero profile changes, one writer, zero extra agents.
Earlier source/native attempts and budget_violation records are not renewed.
Actual exposed model/effort/speed/taskURL remain UNKNOWN; Cloud revision197 was
observed current/running. Fresh GitHub/fetch and a clean isolated checkout agreed
on HEAD41d840cc75fb773251b2b88f8631affbce7679e5,
TREEa909c047c1e298f5577bc439c385e3c1fa07052f,
BASE233dda1878533a425574074b8d34344b50d41cf7. Prior writer was released;
no competing writer was found in current33/95/PR75. Old six dirty files,
staged/unstaged/untracked inventory and sealed historical evidence were copied
and hash-verified without changing their original worktrees.

### Observable completion and mutation evidence

The fixture accepts an optional `barrier_observer` PID for its existing `:done`
message. The monitored owner still controls readiness/release and owner death;
the observer receives the actual completion outcome with the same unique
reference, stage and provider PID. With no observer, completion still goes to
the owner. Both existing real HTTPS503 cleanup tests now require their exact
`:owner_down` or `:abandoned` outcome and retain owner/caller/provider/listener
termination assertions. No new short timing bound or production behavior is added.

All observations below use the same command, from the indicated isolated copy:
`mix test test/symphony_control/auth/oidc_test.exs:582 --seed 876309 --trace`.

| Fixture/test state | Actual result | Exit |
| --- | --- | --- |
| Published parent, unchanged tests | 2/0 | 0 |
| Parent in separate mutation copy, only DOWN receive clause removed | 2/0; old test misses mutation | 0 |
| Outcome assertions added, original fixture | 2/1; owner_down event missing; fixture RED | 2 |
| Optional observer implemented | 2/0 | 0 |
| Same new tests, only DOWN clause removed in mutation copy | 2/1; actual abandoned versus expected owner_down; abandonment passes | 2 |
| Exact candidate fixture bytes restored, same new tests | 2/0 | 0 |

The mutant changed only the DOWN receive clause relative to each saved fixture.
Restoration checked full bytes and SHA256, without reset/clean; no mutant is
published. Candidate fixtureSHA256
`3677fbf3507bc404b16ee475b56420de9a1225e395bc8115bf631a768ff0ad46`
and testsSHA256 `1dc67f0d778e320bacb1be9c3ac0468ae839acf0586a53bce6ab846dcc318ef2`
match the restored copy. This is fixture regression RED, not semantic product
or native RED. Original owner-down handling already worked; the repaired test
now distinguishes it from the unchanged1000ms fallback.

### Gates, frozen controls and resource cleanup

Final Config/OIDC:101/0, seed876309, exit0; no new tests/skips. Related explicit
deadline/POST/invalid-binding/owner cleanup/threeTLS controls:9/0, seed876309, exit0.
One full `make -C elixir all`:514/0/6, actual seed535217/max-cases8, coverage100%,
exit0. Setup/build/format/specs+strictCredo/coverage/deps/Dialyzer stages all0;
Dialyzer0 errors/0 skips. Bootstrap12/0 and MCP contracts11/0, exits0.
All test commands were sequential, verified from start/end records. Make's dev
setup/build/format overlapped the end of targeted tests using separate dev/test
build paths; its coverage test started only after targeted completion. The
dependency lock and executable source bytes stayed unchanged during these gates.

Elixir/Mix1.19.5, OTP28 ERTS16.4; version/setup exits0. Frozen Oidcc3.9.0 and
mix.lockSHA13489fc8ae1bd909063bcfbc56e2bc7c3d080ef9154dc25a0f4f132521d23073 retained.
Cloud cgroupCPU quota4,16GiB,pids.max=max,schedulers4 (nproc5 observed) differs
from protected2CPU/4GiB/pids256/+S2:2/loopback-only. Native equivalence is not claimed.
Own PostgreSQL17.11 uses new0700 data/socket, private Unix55474,
sn004_fixture/sn004_test, empty listen_addresses/noTCP. Init/start/readiness0.
It stayed alive through all dependent gates and final process completion checks;
stop2026-10-08T21:41:04.830392Z exit0, status3. No running own server or owned
HTTPS temp fixture remains; previous zombies/init/foreign processes were untouched.

Byte comparisons preserve the whole stagedTLS fixture implementation and test
suffix, including all threeTLS scenarios/helpers,1500ms/<1700ms/accept1/handshake1/
latePOST0/positive/adverse setup. Validated POST/one650msdeadline/<850ms,
discovery/JWKS shared-budget/positive/invalid-binding blocks and helpers are also
byte-identical. Production Oidc/Config/Clock, dependencies, CoreTest/test_helper,
canonical requirements/index/policy and CI/thresholds/exclusions are unchanged.
Only the six admitted paths change; MANIFEST retains43 existing records and
updates only the five changed allowed source/document hashes.

### Complete command records and portable handoff

Evidence root `/workspace/scratch/SN005-OWNER-DOWN-OBSERVER-41D840`;
own checkout `/workspace/scratch/sn005-owner-down-observer-src`, sequential
mutation copy `/workspace/scratch/sn005-owner-down-observer-mutation`.
`commands.jsonl` and raw `.stdout/.stderr/.output` retain complete argv/cwd,
start/endUTC, exits and separate hashes. Selected complete output hashes:

| Command label | Exit | SHA256 |
| --- | --- | --- |
| `elixir-version` | 0 | `b7bc746ca83ed80c14bbb1d4a097a39a1e61e01f8d50cf14c35dcfefd2faa765` |
| `mix-version` | 0 | `c5d8941ea9c5bb7a6b2a755fafb64c04ba91b6345eb1f62ec2e3b594353e4305` |
| `mix-setup` | 0 | `3f9498e43d094a45da3d9a6bf870b9b3de5c7d5ad34a8a0615269b9800878b0c` |
| `baseline-owner-cases` | 0 | `1bef5cda406afc4d2b2dff057b08b7b0ca6e1c546083049de62f196de170e314` |
| `baseline-down-disabled` | 0 | `f1699d7783f5d9e91c75550ebd4f926151d99518ef130389f78b6fdf3bd18115` |
| `observer-fixture-red` | 2 | `cc0e929f966a1647d8e1faff6d7aab4f054b671ca12833ef0a7343b621d49101` |
| `observer-green` | 0 | `0a767bf1397c5c829febef4b4a1a0db700c2d56d8b9e2e08a8ad38f38cad744d` |
| `candidate-down-disabled` | 2 | `85242d03c812b333adcbb9720cd4d05188bae2e3d99126a8c782342b168d1834` |
| `candidate-mutation-restore` | 0 | `922ae86ddb8b2fc8c4f1f72cd09aca0fa202b667ae6564079a1bfc86161f14f1` |
| `restored-observer-green` | 0 | `c663f1789f2020a3b825a0e0542ba2531e5b19f1af6eb3051a6a50ab75790240` |
| `related-deadline-tls-cleanup` | 0 | `f687fb97f08871d023822febeb22659362ab031bad1fbbd779e0a1c839ebfae2` |
| `final-config-oidc` | 0 | `542133ee0a600be5eed2b52537be1ee06848bd0aa1e253146b29790683c1a666` |
| `make-all` | 0 | `08f4f460ab9e957b38814db76ed5f9a2f18889af3ee37c4f48c45c02a45f5943` |
| `bootstrap` | 0 | `d1a78221f4c616afcb6cc481132d1cfe215654ca22d4c8f55833501402b327dc` |
| `mcp-contracts` | 0 | `cae7d5cea057dfae49fff50a39b7b2390ce23a693428c60cbc409d0b71f862b0` |
| `dependent-processes-complete` | 0 | `d89fd5090089373161f10e8499098319b0a8c2ff2cc50df1e5e08476388eb77e` |
| `pg-stop` | 0 | `ca19178a35ab4153b75b494963b66ce8243e1b94c173107c87b44d09db23652d` |
| `pg-status` | 3 | `e138ccb54fdb08283c6eb21159c53207bbbbf07077246e2804e18d22efe6e250` |

Report snapshotUTC `2026-10-08T21:42:19.234226+00:00`; elapsed858.694s.
Publication, final MANIFEST/scope/actualPRbody checks and fresh remote tuple/clean
readback are subsequent recorded steps in the final33 checkpoint, not inferred
from runtime GREEN. Portable patch/full changed files/evidence and an exact-HEAD
review handoff are prepared separately; the restored mutant copy is not published.

VERIFIED: old test misses the controlled mutation; new outcome assertions detect
it; normal/restored fixture and mandatory author gates pass with owned cleanup.
INFERRED: the test now protects the owner-death branch independently of fallback
timing. UNKNOWN: client model/effort/speed and root cause of old nativeA failure.
BLOCKED: fullSN005/native quality/live Authentik acceptance. Auth stays disabled,
native422 HOLD/history unchanged. Independent review of the new HEAD/trusted
native/live acceptance NOT_RUN; no reviewer is launched or self-accepted here.
Task2–5/PR90 blocked dependency preparation/main/release/production/DF Assistant/
credentials/permissions/CI/rootdrivers/merge/deploy remain excluded.
Next bounded action: independent read-only review of the exact published HEAD
and preserved mutation/gate packet; subsequent native/live stages remain separate.
# Task2 durable state — source continuation 2026-10-09

Task2 adds a separately testable local state layer. Authentication remains disabled;
HTTP login, middleware, IdP eligibility and live revocation belong to Tasks3–5.
Task1 stays pinned at `1a01e11846a9516edb1b2066bab0511f2d1b314f` with source acceptance
only. Historical native HOLD and trusted/native/live gates remain open.

The new migration `20261004000000` creates seven `control_auth_*` tables: users,
exact issuer/subject identities, sessions, pending logins, memberships, platform
grants and logout JTIs. UUID foreign keys, immediate unique keys, required fields,
recognized human roles, positive revisions and expiry bounds are database contracts.
The original CreateProjects migration and project rows are preserved. Auth state has
no automatic registration or IdP email/group/admin mapping. Session identity has a
composite foreign key to the exact local identity and user.

`Store` is an internal control API, not a request authorizer. It owns each bounded
operation; callers must not nest it in their own Repo transactions or retry an unknown
write. `put_login/4` stores SHA256 state/browser hashes and encrypted nonce/verifier.
`consume_login/4` uses a browser/config/boot/time-guarded UPDATE RETURNING inside a
transaction and decrypts only after confirmed commit. A foreign browser does not
consume the legitimate flow; the lifetime is exactly300000ms, exclusive at expiry.
Consumed records survive process restart.

`open_session/4` requires an existing active local issuer/subject identity and issues
32random bytes encoded as an opaque URL-safe handle. The database stores its SHA256,
never the handle. Rotation revokes the old row and inserts a fresh session atomically;
only a confirmed transaction releases the new handle. Sessions expire at the smaller
of3600000ms and credential expiry. Reads never extend that lifetime.

`Actor` carries session/local-user UUIDs, issuer/subject, config generation and boot
epoch. It has no roles, email or tokens and grants no authority. `local_actor/3` checks
current local state and authenticated ciphertext; it makes no IdP eligibility claim.
`actor_current?/3` repeats those checks. `permissions/4` rereads current local
memberships or the independent `runtime_identity_read` platform grant. The only
project permission this slice produces is `:project_read`; all five human roles can
read their own explicitly assigned project. It grants no mutation or admission right.

UTC and monotonic elapsed times must agree exactly in the same boot epoch. Either
expiry or clock uncertainty fails closed; this conservative rule can require a new
login after an observed clock offset change. A new boot epoch always rejects old
sessions and pending flows, while persistent consumed/revoked/JTI state remains.
No continuity across restart is promised. `revoke/3` and `accept_logout/5` accept only
internal tagged selectors; exact issuer plus sid/sub intersection prevents cross-user
logout. JTI deduplication and revocation commit together, with at least3600000ms
retention. This does not verify a logout JWT; signature/HTTP handling is Task4.

`TokenVault.seal/open/3` uses OTP AES-256-GCM with a runtime32byte key reference.
Envelope v1 is one version byte, a fresh12byte nonce,16byte tag, then ciphertext.
Store AAD encodes version, flow/session kind, UUID and config generation. Callers
cannot choose the nonce. Wrong AAD/key/tamper returns a sanitized error; missing or
malformed keys fail without plaintext fallback. Token maps remain private encrypted
terms and are not returned in Actor or permission results.

Every Store query/transaction uses timeout500ms, queue:false, log:false; one outer
750ms task bounds the complete operation, including pool checkout and COMMIT.
Timeout/connection loss on writes returns `:unknown_outcome`, never a flow or handle.
Unknown outcomes require scoped reconciliation; no automatic exchange retry.

Health accepts legacy version `[20260925000000]` only with auth disabled and no auth
tables. The exact two-version set `[20260925000000,20261004000000]` requires both
project and auth contracts. The internal `:control_auth_enabled` flag requires that
second set; this task does not connect or enable a production auth supervisor.
Missing/future versions, missing or weakened FK/unique/check constraints, nullable
required fields and invalid backing indexes fail readiness. Liveness and the public
health response shape remain unchanged; health never applies migrations.

Only an owner-provisioned disposable Unix-socket PostgreSQL fixture is used for
source tests. `AuthDbFixture` requires `SN005_TEST_PG_SOCKET`, `SN005_TEST_PG_PORT`,
`SN005_TEST_PG_USER`, `SN005_TEST_PG_DB`, and `SN005_TEST_KEY_ROOT`, creates a random
isolated schema and runs the standard migrator. Synthetic key files are private and
removed by test cleanup. These test variables do not configure production. Existing
SN004 tests keep their original own-fixture contract. PostgreSQL is kept alive until
all dependent processes finish, then only the owned postmaster is stopped and reaped.

Source verification and publication results are recorded in the exact-head review
handoff. Fixture GREEN is distinct from independent review, protected checks and real
Authentik acceptance. No production migration, merge or auth activation is authorized
by this source layer. Down migration deliberately refuses destructive auth-state
removal; any recovery needs a separately reviewed compatible procedure.

Task2 source verification in the newly published Cloud task: fresh tools7/7 match
the owner-provided PostgreSQL17.11 binary hashes, agent UID/GID1000:1000; an owned
private Unix-socket smoke completed successfully and removed its data/socket/process.
Admission is [#33/comment6083322412](https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6083322412).
The separate application fixture stayed alive through all Mix/make processes;
cleanup confirmed stop0, status3, readiness2, exact owned waitpid0 and absent
socket/pidfile/postmaster. No installation or privilege transition was needed.

Final targeted auth plus unchanged foundation/schema tests:61/0. Full
`make -C elixir all`:551tests/0failures/6existing live skips, configured coverage100%,
format/build/specs/strictCredo/Dialyzer exit0. Bootstrap12/0 and MCP11/0. Existing
project migration, legacy tests, Config/Clock/Oidc, dependency locks, policies and CI
are unchanged. All43original MANIFEST records remain, with9new auth contract records.

Evidence includes one confirmed parallel flow consumer, wrong-browser non-consumption,
299999/300000ms flow boundaries, exact local identity/no registration, session
absolute/credential limits, current membership/platform separation, durable revoked
and consumed rows across restart, malformed-role refusal, AES/AAD/key/tamper
negatives, and direct SQL constraint violations. A deferred trigger delayed COMMIT:
the API returned unknown_outcome without a handle/plaintext; rotation and consumption
rolled back in the observed fixture. This proves that timeout scenario, not every
possible network-loss outcome. A suspended pool and pool death also failed closed.

Failures are retained: initial legacy+enabled readiness RED; restart fixture startup
readiness failures; mistaken autogenerated check names; missing-auth-version legacy
fallback; initial style findings; first full run547/0/6 with99.85%coverage; malformed
membership role RED. Two Task2 repair cycles were used, with no agents/profile
changes or reset of Task1/setup history. The final full-run output SHA256 is
`9c58e30c7348198b450369c150e9bec245df79690b932a8eac0d3416f4399107`.
These are implementer source tests; independent review and trusted/native/live
acceptance remain NOT_RUN. Historical native HOLD remains open and auth stays disabled.
