# GH87: paged source-review queue candidate

Status: SOURCE CANDIDATE, NOT INSTALLED. This directory is inert source/test
material; it does not register hooks, launch workers or replace an installed queue.
The complete candidate is self-contained Python 3.10+ with standard-library tests.

## Scope and provenance

Owner Denis supplied queue.py (53,204 bytes), SHA256
7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1.
The previous delivered candidate was a464d16cad3c2178536b6f63944c3c5f1fa1ef45c3bfd23c877970e22bfa60a2.
This published candidate is 09bd1c19697fe9ad2ddc6fbb6ae9b52a3c8fa5f97b48935edff6c38079a6aa66.
During source transfer a local constant assignment in parse_task moved before
its type guard and one blank separator was added. Both differences are preserved
explicitly; the published bytes were reproduced locally, Git blob hashes matched,
and all 52 tests were rerun against these bytes. No test or behavioral limit changed.
The original archive and earlier evidence remain unchanged; old hashes are not
attributed to this publication.

## Behavior

Legacy snq-review/v1 remains. Explicit v2 tasks add pinned context_sources.
Full changed base/head versions, required composition groups and explicit source
references are fetched and hash-checked before auth probing or paid reservation.
Duplicate blobs share storage while revision/path/mode aliases are retained.
An index replaces the duplicated diff/full-text payload. A single dynamic tool,
snq_source_read(source_id, page), returns only preloaded source data, never host
files, network, shell, credentials or writes. Complete source delivery and a
matching immutable-store/page receipt are required before a completed review.
Delivery is not a proof of model comprehension or product correctness.

Unchanged legacy packet/prompt caps: 650000/670000 bytes. Opt-in v2 bounds:
2 MiB unique source, 500000 bytes/blob, 256 documents, 600 aliases, 64 explicit
references, 100000-byte index, 8192-byte response, 400 source calls, 4 MiB result
budget. One thread/turn, model/effort, 1700-second worker wall, daily 100 and quota
ceiling 100 stay unchanged. include_mix_reference=true is unsupported in v2.
The original owner installer is retained as source, NOT an update mechanism.
Existing claims, reservations and uncertain-write reconciliation are not reset.

## Reproduce the available test suite

From this directory:

```sh
python3 -B -m unittest discover -s tests -v
```

52 tests passed on the publication bytes. GitHub is FakeGit; the pipe/socketpair
integration launches a fake Codex peer, not a model. It covers source overflow,
missing context, hashes/aliases, source and call budgets, missing/duplicate pages,
request IDs, lifecycle, immutable store, no-replay and the legacy protocol.
The historical installed-queue suite was not supplied and is not certified.
The large fixture is synthetic, NOT a complete PR84 export. Full live PR84 review,
service-identity isolation and actual Codex dynamic-tool compatibility are NOT_RUN.

## Acceptance and operating boundary

A separate source reviewer must inspect all candidate and test files. This PR
cannot issue trusted CI, accept itself or authorize installation. Repo main,
existing policy/CI/units, installed.json, credentials and DF Assistant are untouched.
Read-only review of this code can use the existing v1 queue: it need not activate
v2 or replay GH85/GH86. Native checking, a controlled drained update, installed
checksum verification and a new exact-source PR84 review remain separate gates.
Previously refused schema-generation and remote read operations are not replayed.
Do not execute --install-start on an existing installation or replace the live file
from this source candidate without those gates.
