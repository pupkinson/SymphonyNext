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
