# Tracker status mapping — independent implementation contract

## Purpose and status

Implement business-status mapping required by TRK-05 in the owner-approved
tracker-choice amendment PR26 (source accepted at
85bb926f53028768400b67422cb60be1fb800cc1). Base main is
2bf21950e0725bc9228b262e1495f5af5eeea1d6. This is independent of unfinished
TaskRef and SessionAccess. This document alone is NOT implementation.
A business status is neither execution success nor an admission/approval grant.

## Allowed files and boundaries

1. elixir/lib/symphony_control/tracker/status_map.ex (new module)
2. elixir/test/symphony_control/tracker/status_map_test.exs (new tests)
3. docs/engineering/tracker-status-map.md (contract and actual evidence)

Do not modify existing source/config/tests, CI, dependencies, services, credentials,
other branches or PRs. Do not perform PR37/38 malformed-struct repairs, access their
worktrees, repeat refused cache/full-suite or CI activation/profile operations,
contact the production server, or work around platform refusals. No merge/deploy.
This independent module does not call APIs, mutate issues, enqueue, approve runs,
or infer that tests/review passed. Adapter/registry integration is separate work.

## Interface

Module SymphonyControl.Tracker.StatusMap:
- native(category)
- github(state, state_reason, labels, mapping, default_category)
- linear(state_id, mapping)

Input categories, statuses and mapping keys are strings; never create input atoms.
Categories: triage, backlog, unstarted, started, review, completed, canceled.
Return {:ok, category_string} or {:error, reason_atom}. Fixed reasons:
invalid_input, invalid_mapping, unknown_status, ambiguous_status,
contradictory_status. Do not echo input or return admission/execution fields.
These functions consume extracted status fields, not entire provider responses.
API extraction/pagination, scope checks and persisted scheme versions are outside.

### Native

Accept exactly the seven category strings, without trimming or case folding.
Unknown nonempty strings return unknown_status; wrong type, empty string,
invalid UTF-8 or ASCII control characters return invalid_input.

### GitHub

state is open/closed; state_reason is nil or a nonempty valid UTF-8 string without
ASCII controls; labels is a list of label-name strings; mapping is a map of managed
label names to nonterminal categories; default_category is nonterminal. Nonterminal
means triage/backlog/unstarted/started/review. An empty mapping is allowed.
Validate the entire input and all mapping entries, including unused entries, before
classification. Wrong raw types/shapes return invalid_input. Invalid mapping/default
returns invalid_mapping. No contractual precedence is required when both are invalid.

Label/map keys must be nonempty valid UTF-8, at most 256 bytes, without ASCII control
characters. Match exactly. At most 256 labels and 256 map entries are allowed.
Duplicate occurrences of one label count once. Ignore unmanaged valid labels.

For open: reason nil/reopened is allowed; other valid reasons are contradictory_status.
When no managed label is present, use default_category. One distinct managed label
uses its category. Two distinct managed labels are ambiguous_status EVEN if they map
to the same category; never silently choose between competing workflow labels.

For closed: completed -> completed; not_planned -> canceled; nil/unknown reason ->
unknown_status; reopened -> contradictory_status. Nonterminal labels may remain after
closing: do not override the terminal result or cause ambiguity. Invalid label/mapping
shape must still be rejected. Unknown state string returns unknown_status.

### Linear

state_id is a UUID; mapping has UUID workflow-state keys and category-string values.
Accept hexadecimal text case and normalize UUIDs for matching. Do not map display
names, translated names, team issue keys or type aliases. Validate ALL mapping
entries (1..256) and reject duplicate normalized UUID keys as invalid_mapping, even
when their categories agree. All seven category targets are valid. Malformed
state_id -> invalid_input; well-formed unmapped ID -> unknown_status. No existence
or workspace/team/project permission is established by this pure function.

## Tests and handoff

Write ExUnit tests first and record genuine RED, then implement. Cover exact category
matching; bad types/UTF-8/control chars; unused malformed map entries; bounds; GitHub
default, single/duplicate/conflicting labels, same-target conflicts, terminal reason
handling and stale nonterminal labels; Linear UUID case and duplicate-normalized keys,
unknown ID and no display-name fallback. Verify results contain no execution admission.

Run only the new dependency-free subset in a fresh Elixir process (start ExUnit,
require the module and its test file). Do not rerun previously refused full-suite/cache
preparation. Record command, version, exit codes, RED/GREEN and git diff --check.
If runtime/tool access is missing, report the exact gap instead of claiming success
or using the production server. Do not change dependencies or test thresholds.

Commit only allowed files on this task branch, with [skip ci], leave PR draft.
The coordinator will request independent exact-HEAD review through the existing
Symphony AFTER implementation returns; no simultaneous writer or automatic merge.
Source review does not replace protected CI or product integration acceptance.
