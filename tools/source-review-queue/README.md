# Prospective development limits — 2026-10-08

Source-only candidate for the existing PR90/GH87. Owner authority is GH95
comment6066736597, implementation admission GH87 comment6066853172.
Not installed; GH96 actual-prompt binding P1 remains unresolved. This change
does not grant source approval, native/trusted checks, merge, deployment,
new model privileges or extra attempts for any terminated task.

## Behavior, not a global budget reset

New prepare_task calls pin `snq-development-limits/2026-10-08` into task.json
and packet.json and the existing whole-task SHA256 snapshot. Worker start and
successful finalization validate that binding. A context-local policy selects
limits; imported legacy constants remain unchanged. Genuine old journals keep
`snq-legacy-limits/v1`, the old1700s worker bound and old4096-byte page layout.
Reader instances retain their selected layout across caller scopes. No old
claim/deadline/reservation/evidence file is migrated or rewritten. This remains
a service-owned consistency check, not a signature against an actor rewriting
all journal files coherently.

| Limit | Legacy jobs | Newly prepared jobs |
| --- | ---: | ---: |
| v1 full packet bytes | 650000 | 2097152 |
| v1 prompt bytes | 670000 | 2162688 |
| v2 unique source bytes | 2097152 | 16777216 |
| Individual blob bytes | 500000 | 4194304 |
| Page response bytes | 8192 | 32768 |
| Reader calls | 400 | 4096 |
| Source result bytes | 4194304 | 67108864 |
| Catalog bytes | 100000 | 1048576 |
| Documents / aliases / explicit refs | 256 / 600 / 64 | 2048 / 8192 / 512 |
| Worker bound, seconds | 1700 | 5400 |

The raw page target is16384bytes for new readers, reduced until UTF8/JSON wire
bounds fit. New default metadata reads allow8MiB; API response envelopes allow
32MiB and serialized stores102960448bytes. These dependent bounds prevent the
old1MiB/default or5MB/base64 readers from defeating the advertised source size.
Each bound remains enforced; not every maximum can be attained simultaneously
for heavily escaped data. API pagination/current100-changed-path validation,
issue/comment caps, account quotas, model selection, one-turn/tool restrictions,
full hash/receipt validation and no-replay remain unchanged.

The generated, NOT installed WORKFLOW has turn_timeout_ms5700000, hook timeout
900000, read timeout120000 and stall timeout900000. The worker retains its own
per-job bound; the supervisor buffer is not extra worker permission. A full
end-to-end prepared-environment90-minute run has NOT been executed here.
Owner instruction budgets for future source development are4hours with the
last30minutes reserved, and direct reviewer instructions90minutes with the
last15minutes reserved. Those planning budgets are distinct from actual worker
timers and do not retroactively extend old executions.

## Capacity and installation limits

Bytes are not model tokens. A16MiB source store is not a16MiB monolithic model
prompt. Prefer complete paged sources and deduplication; reject missing context
and respect actual provider context/tool limits. No backend metadata, access,
sandbox, TLS/OIDC650/1500ms deadlines, assertions, CI profiles, release gates,
installed units, production or DF Assistant was changed. --install-start remains
a fresh-install path, NOT an updater. Candidate installation must wait for
independent review, resolution of GH96 P1 and an admitted update/rollback path.

## Verification

Run `python3 -B -m unittest discover -s tests -v` here. The100existing regressions
are retained, plus21prospective-limit tests. The old-v1 test fixture additionally
removes the new limit-profile fields when constructing a genuinely pre-profile
journal; its assertions were not removed. Test/source/account/process doubles
are not model entitlement, backend capacity or native installation evidence.

Real cached PR75 public source objects reconstruct the identical1005922-byte
full packet (SHA256 b2ee0a1e61c235dc5c9bfd894f314396ffa4f85141d648fcfb6fd271dbc23e65):
legacy source_packet rejects it; the development profile accepts it without
truncation. Other tests exercise>500000-byte blobs,>2MiB stores, UTF8 boundaries,
new upper-limit refusals, restored contexts, unchanged legacy layouts/deadlines,
worker/finalizer snapshot tampering and actual proxy default-budget selection.

Historical failure evidence remains. Initial new tests failed on the unchanged
source. The first implementation passed119tests but a new direct-proxy regression
found an unresolved None default; one repair fixed dynamic budget selection and
made source installation metadata describe the new profile accurately. Full
121tests then passed; final exact-source results are recorded in GH87, not
inferred from this README. No real model call or protected/native action ran.

<details>
<summary>Preserved historical predecessor report (not current acceptance)</summary>

# GH87: immutable paged source review and schema-bound profiles

## Scope and status
Source candidate for PR90/GH87, not installed. This adapter admits source-only
review, not implementation, trusted CI, merge or deployment. The existing
--install-start command is NOT an updater. No installed files, credentials,
service model, permissions, budgets, old claims or DF Assistant were changed.

Independent GH93 accepted predecessor83c385053903160361706cb094121f491737d507.
That acceptance does not cover this subsequent profile-binding change.
Previous GH91/GH92 repairs and historical attempts remain preserved.

## Paged source contract
Opt-in snq-review/v2 adds context_sources pinned to head/base paths and blobs.
Before model reservation, collect both changed versions, scope documents,
documented HEAD spec-index groups and explicit context refs. Verify exact
repo/head/base/tree, full PR diff, hashes/path/mode; deduplicate identical blobs
with aliases. Unknown Markdown/URLs are not followed. Only
snq_source_read(source_id,page) is available: it serves preloaded immutable
bytes, not host filesystem/network/commands. All pages, store and final receipt
must match. Delivery alone does not prove the reviewer understood the source.

v1 retains MAX_PACKET650000/PROMPT670000. v2 source limits remain:
2MiB total,500000/blob,100000/index,8192/page response,400calls,4MiB results,
256documents/600aliases/64explicit refs. One model turn; no additional funds.
Paged include_mix_reference=true remains unsupported; v1 retains its behavior.

## Closed profile binding
review_profile(schema) selects a fresh code-owned record:

| Task format | Profile | Requested model | Effort | Tool |
|---|---|---|---|---|
| snq-review/v1 | snq-legacy-v1 | gpt-6.1-sol | low | none |
| snq-review/v2 | snq-paged-direct-v1 | gpt-5.5 | low | snq_source_read |

The source task cannot supply an arbitrary model/profile. The same canonical
record binds CLI settings, both native start requests, account/catalog probe,
protocol evidence and finalization. v2 saves it in task.json; the worker reloads
and checks it plus its saved auth evidence before starting. Old v1 journals need
no new field. Missing/altered/cross-schema profiles reject instead of falling
back to another model. No global MODEL mutation is used for per-task selection.

v2 also checks existing package.json version0.159.3 before probe and worker.
This is a metadata check, NOT a hash of the executable or a guarantee of account
catalog freshness. Probe model/list is NOT model entitlement or successful
inference; both are still reported NOT_TESTED/NOT_RUN. Missing model/auth/quota
prevents ready and turn reservation. --auth-paged adds only the fixed v2 probe
behind the existing service identity guard; it does not grant access or start a
turn. --auth keeps v1. Sandbox, disabled features and external write scope stay
unchanged. Reported model in protocol is the enforced requested binding, not an
independent attestation of which backend model served a request.

## Tests
From this directory:

    python3 -B -m unittest discover -s tests -v

91 supplied tests,0failures/errors/skips,exit0. Python3.10 grammar checked for all
8Python files; actual local execution Python3.13.5.22profile tests were added;
all69previous tests retained. One positive prepare fixture now supplies its own
required version metadata; its assertions were not removed. An initial full
run rejected that missing test fixture, preserved separately, before correction.

Initial18profile tests on unchanged83c:16failures,0errors,exit1. RED SHA256:
324002c03d656941625fa3ab5521b1716d1594f60cadc4fea8da8edc6474429a.
Final91test log SHA256:
7c64bbea972a460256ede642c62edd893d6aece92c6c658e98290e6192611ac6.
Candidate SHA256:
758d5f5be3591885dfdd9668bc03331ded96ad6daf57532c443c343e4ec3bacb.
The historical full queue and whole-product suites were not supplied/run.
Account,GitHub and selected process boundaries in unit tests are fixtures;
these are not real entitlement or production isolation evidence.

## Exact-candidate native component verification
Real scratch Codex0.159.3, fixed localhost Responses provider, empty HOME and
CODEX_HOME, no credentials or real model calls. Unlike the earlier control,
this run uses review_profile(v2) and passes it normally; no q.MODEL override.
The legacy global remains Sol. Existing Code Mode host/shell restrictions stay.

Full unchanged PR84source705d9c1f7c4033265fa2af7135aa70ffe68045ed:
24documents,928163raw bytes,238/238pages,238tool calls,239localhost requests,
1078508delivery bytes. Matching profile and source receipts; client/server EOF
true,child/helper exit0,no driver errors. One warning counted, not absence of
warnings. Result SHA256:
743e707f1079ab06b37891073d99c6cff97abf24f87e59bd816d2bb160a2e913.
Fixture SHA256:
ac62530b99f43cdb1e4b0443f485a254c6065ac19b67a242b51c1345cc6a1102.

This establishes component protocol compatibility, NOT an actual GPT-5.5
review, service-account entitlement, current model metadata, real scheduler
integration, trusted CI or installation. Remaining gates: fresh independent
source review, authorized service-account preflight/budget, controlled update
and rollback, real scheduler lifecycle and full independent PR84 review.
No earlier refused schema-generation/download/diagnostic operation is replayed.
Before those gates, leave the candidate unapplied; do not edit installed.json
merely to suppress verification or reuse old claims/review approvals.
EOF gating requires the upstream client to close its input after the final turn.

</details>
