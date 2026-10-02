# Tracker status mapping — independent implementation contract

## Purpose and status

Implement the business-status mapping required by TRK-05 in the owner-approved
tracker-choice amendment (PR26, source accepted at
85bb926f53028768400b67422cb60be1fb800cc1). This task starts from main
2bf21950e0725bc9228b262e1495f5af5eeea1d6 and does not use unfinished
TaskRef or SessionAccess code. This document alone is NOT implementation.

A tracker business status is not execution success or an admission grant.
No function in this increment may enqueue work, approve a run, infer successful
tests/review, mutate an issue, resolve credentials, or call a remote API.

## Allowed change

- elixir/lib/symphony_control/tracker/status_map.ex (new implementation)
- elixir/test/symphony_control/tracker/status_map_test.exs (new tests)
- docs/engineering/tracker-status-map.md (this contract and actual evidence)

Do not change existing source, requirements, test configuration, CI, dependencies,
service files, credentials, other branches or PRs. In particular, do not work on
PR37/38 malformed-struct repairs, their worktrees, previously refused cache/full
suite operations, the CI activation/profile transition, or the server runtime.
This is independent feature development, not an alternative execution of those
operations. Do not disable or work around platform refusals. Do not deploy/merge.

## Function contract

Module: SymphonyControl.Tracker.StatusMap. Provide explicit functions:

- native(category)
- github(state, state_reason, labels, mapping, default_category)
- linear(state_id, mapping)

All input status/category/map keys are strings. Never create atoms from input.
Valid category strings are exactly: triage, backlog, unstarted, started, review,
completed, canceled. Return {:ok, category_string} or {:error, reason_atom}.
The fixed reason atoms are invalid_input, invalid_mapping, unknown_status,
ambiguous_status, contradictory_status. Never return private input in errors.
Successful results contain no admitted/approved/execution_success fields.

These functions consume a provider adapter's extracted status fields, not
arbitrary GitHub/Linear API response envelopes. API extraction, complete
pagination, stable-ID readback, scoped authorization, and versioned scheme
persistence are explicitly separate integration work.

### Native

A category must be a valid category string, without trimming or case folding.
An unknown nonempty string returns unknown_status; a wrong type, empty string,
invalid UTF-8 or control-character input returns invalid_input.

### GitHub

Inputs: state string open/closed; state_reason nil or a string; labels is a list
of label-name strings; mapping is a map of managed label names to nonterminal
category strings; default_category is a nonterminal category. A mapping may be
empty. Nonterminal categories are the first five categories listed above.

Validate the entire input/mapping, including unused entries, before classifying.
Map keys and labels must be nonempty valid UTF-8, at most 256 bytes and contain
no ASCII control characters. Matching is exact; no downcasing/trimming.
Limit mapping and labels to at most 256 entries each. Duplicate occurrences
of the same label do not create ambiguity. Unknown, unmanaged labels are ignored.
Mapping values and default_category must be valid nonterminal categories.

For state=open, state_reason must be nil or reopened. Other reasons are
contradictory_status. No managed label uses default_category. Exactly one distinct
managed label uses its mapped category. Two distinct managed labels are
ambiguous_status even when they map to the same category: competing configured
workflow labels must not silently choose a winner.

For state=closed, completed maps to completed; not_planned maps to canceled.
Nil/unknown reasons return unknown_status, reopened is contradictory_status.
Still-present nonterminal labels are allowed and do not override terminal state;
closing an issue does not necessarily remove its workflow labels. Malformed
labels or mapping must still fail validation even on closed issues.

Unknown state string returns unknown_status. Wrong input types return
invalid_input; malformed mapping/default category returns invalid_mapping.

### Linear

Accept a canonical UUID state_id (case-insensitive hex accepted and normalized
for matching), and mapping from UUID workflow-state IDs to category strings.
Do not map display names, localized names, team issue identifiers or type aliases.
Validate all mapping entries (1..256 entries); reject duplicate canonical UUID
keys represented with differing text case as invalid_mapping rather than
silently overwrite. All seven categories are allowed as targets. A malformed
state_id returns invalid_input; a well-formed unmapped ID returns unknown_status.
Workspace/team/project authorization and actual workflow-state existence are
not established by these pure functions.

## Required tests and evidence

Write ExUnit tests first and show genuine RED before implementing the module.
Cover all categories and exact matching; bad types/UTF-8/control characters;
malformed and unused mapping entries; input size bounds; GitHub open default,
one label, duplicate identical label, conflicting labels (including same target),
closed completed/not_planned, stale nonterminal labels, unknown/reopened reasons;
Linear UUID case normalization, duplicate normalized keys, unknown state ID and
absence of display-name fallback. Assert no function grants execution admission.

Run only this new dependency-free subset in a fresh Elixir process; for example
start ExUnit, require the new module and its new test file. Do not rerun the
previously refused full-suite/cache preparation. Record exact commands/exits,
Elixir version, RED/GREEN evidence and git diff --check. If an Elixir runtime is
not present in the selected environment, report that specific gap rather than
claiming tests passed or accessing the production server for a workaround.

Commit only the allowed files to this task branch, include [skip ci] in the
commit message, and leave the PR draft. GitHub Actions are not to be enabled.
The coordinator will obtain a new exact-HEAD review through the already running
Symphony after the implementation is returned. Source review is not trusted CI
or a release approval. Registry/adapter integration remains a later stage.
