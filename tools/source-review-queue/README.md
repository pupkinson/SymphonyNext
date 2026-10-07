# GH87: immutable paged source-review candidate

## Current scope
Source candidate only; not installed. The existing source-review queue and
protected CI are separate components. Workpad GH87; PR90. Denis supplied the
original queue.py and authorised this repair. No service, credentials, frozen
CI, old claims, model/profile settings or DF Assistant resources are changed.

The format v1, its limits, no-replay journal and existing privileges remain.
Malformed legacy RPC sequences are now deliberately rejected; preserving a
known protocol defect is not backwards compatibility. The candidate still has
an old --install-start entry point, which is NOT an update/install instruction.

## Paged source contract
Opt-in snq-review/v2 adds context_sources pinned to head/base paths and blobs.
Before model reservation, collect both changed versions, scope documents,
documented HEAD spec-index groups and explicit context refs. Verify exact
repository/head/base/tree, complete PR diff, hashes/path/mode; deduplicate
identical blobs while retaining aliases. Unknown URLs/Markdown are not followed.
The only tool is snq_source_read(source_id,page), over a preloaded store, not
host filesystem, network or arbitrary commands. All required pages and the
matching final store/receipt are mandatory. Delivery does not prove understanding.

Legacy MAX_PACKET650000/PROMPT670000 remain. v2 bounds: source2MiB, blob500000,
index100000, page response8192, calls400, delivered result bodies4MiB,
documents256/aliases600/explicit refs64. No additional model turns or funds.
Paged include_mix_reference=true is explicitly unsupported; v1 retains it.

## GH91 source review and first repair
Independent GH91 review of bf1e8917f69652d81b8366966c5adc2ba26a3c0d found three
HIGH defects: unbound report messages; partial frame accepted on EOF; repeated
start responses able to replace thread/turn identities. Its verdict was
CHANGES_REQUIRED, not release approval. The full six supplied files were read.

Repair changes only Gate, proxy and completed() relative to that candidate:
- Report messages require current thread/turn and started/completed lifecycle.
- Request IDs have exact types/bounds and are unique; responses consume pending
  requests once. Thread/turn bindings and terminal phases cannot be overwritten.
- EOF or loop exit with an incomplete buffered frame records a protocol failure.
  Gate and persisted completion reject failure and non-clean proxy outcomes.
The two old positive protocol fixtures now include proper initialization and
message IDs/lifecycle. No regression was deleted. New negative tests cover all
three findings; valid clean v1 and paged v2 exchanges remain covered.

## Actual author verification
Run from this directory:

    python3 -B -m unittest discover -s tests -v

66 tests, zero failures/errors/skips, exit0, Python3.13.5. Python3.10 grammar
checked. The 14 new tests first ran against unchanged bf1e891 source:24 failing
assertions/subcases, exit1. After the repair all66 passed. Actual subprocess,
socketpair and pipe cases exercise clean and partial client/server EOF with a
FAKE Codex peer. GitHub/auth/quota boundaries are fixtures, not live acceptance.
The historical full queue suite was not supplied;66 is this package's suite.

Candidate SHA256 ad5e4eba5a1dedd3c141d634f5755348f2fc734b7ee985b6f2529a9376c6c07c.
Owner original SHA2567fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1.
RED log SHA2565c8cd4199c7a8ff5dc7777885724b6e3900f082d2682e9617e132e047c42e649.
GREEN log SHA2569bbf562520a05a133c0071e1a55c4cff6f9992ab274b7cf64c99df5785c4a504.
Original/RED artifacts remain in the user delivery; a source reviewer must not
claim independent execution or inspection of files not actually supplied.

## Remaining gates
Fresh independent source review of the repaired exact HEAD is required; GH91
cannot approve its successor. Native Codex0.159.3 lifecycle, installed state,
update procedure and complete PR84 review are NOT_RUN. Static reading of the
published protocol types is not a binary test. Previously refused operations
are not rerun or delegated. No installer, /opt mutation, policy/hash rewrite,
trusted status, merge/deploy or permission expansion is authorised by this file.
Before real installation, rollback is leaving the candidate unused.
