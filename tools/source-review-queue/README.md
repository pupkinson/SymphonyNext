# GH87: immutable paged source-review candidate

## Status and ownership
This is a source-only candidate, not an installed queue update. The existing
source-review queue and protected CI are different components. Workpad: GH87.
Denis supplied the original queue.py and authorised its repair and continuation.
The existing v1 queue can review this bounded package; v2 is not yet activated.

## Contract
Preserve v1 behaviour, the existing API write scope, claim/reserve journal,
model and reasoning settings, one thread/turn, workflow, service, and installer.
Opt-in snq-review/v2 adds context_sources pinned to head/base paths and blob IDs.
Before model reservation, collect both changed source versions, the five scope
documents, the documented HEAD spec-index groups and explicit context sources.
Verify source identities, hashes, path/mode and complete PR diff; deduplicate
identical blobs while retaining all aliases. Unknown external references are not
followed. This is a closed input set, not a recursive arbitrary Markdown reader.

The single snq_source_read(source_id,page) tool serves only this preloaded store.
No shell, approval, host filesystem or network tool is granted. Exact thread,
turn, call and request bindings and started/responded/completed lifecycle gate
the response. All required pages and a matching final store/receipt are needed
for source-review completion. Delivery is not proof of model understanding.

Legacy MAX_PACKET=650000 and PROMPT_LIMIT=670000 are unchanged. v2 limits:
unique source 2 MiB; per blob 500000 bytes; index 100000 bytes; page response
8192 bytes; 400 calls; delivered result bodies 4 MiB; 256 documents; 600 aliases;
64 explicit refs. These source bounds do not grant extra model turns or funds.
Paged include_mix_reference=true is explicitly unsupported; v1 keeps that mode.

## Verification and provenance
Run from this directory:

    python3 -B -m unittest discover -s tests -v

52 tests passed, zero failures/errors/skips, exit 0, Python 3.13.5. These are the
complete supplied regression tests, not the unavailable historical queue suite.
The subprocess/socketpair/pipe case uses a FAKE Codex peer, not a real model.
The preparation test replaces GitHub, auth probe and quota boundaries; the
source builder itself is real. Synthetic large-source reproduction is not PR84
live acceptance. Neither native compatibility nor full product acceptance is
certified by these tests.

Original owner file: 53204 bytes, SHA256
7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1.
Candidate: 75296 bytes, SHA256
a464d16cad3c2178536b6f63944c3c5f1fa1ef45c3bfd23c877970e22bfa60a2.
Fresh test log SHA256:
09c06bd5cc49071ce820a78071f266e790cad18ecc510c3bd8d3faeeb37eb091.
Author AST comparison against the uploaded original found changes only to Gate,
proxy, parse_task, prepare_task, finish_task, main and added paging functions.
The original and prior RED logs remain in the delivered archive, not this PR;
an independent reviewer must not claim to have executed or inspected them here.

Official Codex rust-v0.159.3 resolves to commit
01fc69f4026735edfdf6789820549727a4867b11. The published DynamicToolCallParams and
app-server response decoder agree with the selected field names. This limited
static comparison is not a full lifecycle, model entitlement or binary test.
The denied native schema generation and later denied scratch public-source
fetch were not replayed or delegated. Native compatibility remains NOT_RUN.

## Release boundary
Do not use --install-start as an updater, replace /opt files directly, rewrite
installed.json to suppress a mismatch, replay GH85/GH86, or publish trusted CI
status. Installation needs independently reviewed source and actual authorised
native compatibility/installed-state evidence. No new administrative access,
service restart, changed frozen CI profile, merge/deploy or DF Assistant action
is included. Before installation, rollback means leaving this draft unused.

## Independent review focus
Inspect the complete candidate and all four tests. Check lossless source
coverage, budgets before reservation, malformed input and JSON/UTF-8 handling,
protocol sequencing, stale target/store/receipts, no-replay preservation, and
whether tests support the stated guarantees. Return concrete source findings
with exact HEAD and file:line. Do not equate source-only acceptance with native
verification; do not require unimplemented whole-product features for this fix.
