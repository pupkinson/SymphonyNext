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

## Implementation evidence — 2026-10-02

ACCEPTED: one implementer, TRK-05 under specification/policy v0.5, exact seed
`170fdf9d9dc352b5359db5ae47805c3dd8444353`, branch
`feat/tracker-status-map-20261002`, existing draft PR41. The cloud checkout initially
had clean branch `work` at base `2bf21950e0725bc9228b262e1495f5af5eeea1d6`.
After fetching and verifying the feature seed, implementation used the separate
worktree `/workspace/SymphonyNext-status-map`; the original checkout was preserved.
Only the three allowed files changed.

Implemented `native/1`, `github/5` and `linear/2` as dependency-free functions with
public specs. Validation covers unused schema entries, malformed text and shapes,
byte/count limits, exact GitHub labels and normalized Linear UUID collisions.
Closed GitHub issues use their reason only after input/schema validation. Return
values are category/error tuples with no execution, admission or approval fields.

### Runtime and commands

Elixir/Mix were initially absent from PATH. A local runtime was unpacked under
`/tmp/status-map-tools`, without root, system installation or project dependencies.
Test runtime: Elixir **1.19.5**, Mix **1.19.5**, Erlang/OTP **28.1**, ERTS **16.1**.
Other tools: Git **2.52.0**, Python **3.12.14**, GitHub CLI **2.46.0**.
An initial OTP 28.0 version probe warned about regex recompilation; all test runs
used OTP 28.1 and the GREEN runs emitted no warnings.

Runtime downloads and observed SHA-256:

- `https://builds.hex.pm/builds/otp/amd64/ubuntu-22.04/OTP-28.1.tar.gz`:
  `60c1083df707642f20831c762a68db191984314fef1d4d80b05bb8caf70b70bf`
- `https://builds.hex.pm/builds/elixir/v1.19.5-otp-28.zip`:
  `ca481510feb6dabc875bba43e44b25c7abafa53bd7a103639851b7aeace8a022`

From the feature worktree's `elixir/` directory:

```sh
export PATH=/tmp/status-map-tools/elixir/bin:/tmp/status-map-tools/OTP-28.1/bin:$PATH

# Same command before and immediately after implementation. The wildcard allows
# ExUnit to execute every test while the production module does not yet exist.
elixir -e 'ExUnit.start(seed: 0); Enum.each(Path.wildcard("lib/symphony_control/tracker/status_map.ex"), &Code.require_file/1); Code.require_file("test/symphony_control/tracker/status_map_test.exs")'

# Final verification requires both files explicitly in a fresh process.
elixir -e 'ExUnit.start(seed: 0); Code.require_file("lib/symphony_control/tracker/status_map.ex"); Code.require_file("test/symphony_control/tracker/status_map_test.exs")'
```

| Run | Tests | Failures | Exit code | Observation |
| --- | ---: | ---: | ---: | --- |
| RED before implementation | 62 | 62 | 2 | UndefinedFunctionError: StatusMap was absent |
| GREEN after implementation | 62 | 0 | 0 | Same test file and command as RED |
| Final explicit-load GREEN | 62 | 0 | 0 | No warnings; 2026-10-02 13:22:43.871–13:22:44.504 UTC |

Formatting was checked from `/tmp` so no Mix application or dependencies start:

```sh
mix format --check-formatted --dot-formatter /workspace/SymphonyNext-status-map/elixir/.formatter.exs /workspace/SymphonyNext-status-map/elixir/lib/symphony_control/tracker/status_map.ex /workspace/SymphonyNext-status-map/elixir/test/symphony_control/tracker/status_map_test.exs
```

Formatting exit code: **0**. `git diff --check` and `git diff --cached --check`
also return **0** with the new files included.

### Evidence hashes and remaining gates

SHA-256 of the implementation and unchanged RED/GREEN test source:

- `elixir/lib/symphony_control/tracker/status_map.ex`:
  `e443fcd0c3fc5e455e0362986044fa61fe2e7d2e1ebaf3ecbb0ffc044317e717`
- `elixir/test/symphony_control/tracker/status_map_test.exs`:
  `499ed91641ba631e26784dc01c7366c103547934ced831f24b4cee9201fd650f`

Local logs are retained under `/tmp/status-map-evidence/` (not protected CI artifacts):

- `red.log`: `254d825f9c11aa9eabfa175c91596959f58b40bb7e355dcf0588dfd6adb989d7`
- `green.log`: `a4420736a4d7cadce1b9c0addcb04138b00168e0eee0091e46269660a5059f59`
- `final-green.log`: `47b96b4187a3619b552ae36ba9597f888801797e21603b3a38298e1a3f4006c1`

VERIFIED: the isolated 62-test contract subset and formatting/whitespace checks.
NOT_RUN: full suite, cache preparation, CI activation, external API/adapters,
product integration, merge and deploy. Independent exact-HEAD review through
Symphony and protected checks remain pending; this is implementer evidence only.
No task admission, execution success or release acceptance is granted. The final
commit/tree are recorded in the handoff, rather than self-referenced in this file.
Before merge, rollback is to withhold this feature commit; no runtime or schema
was changed and no unrelated work needs reverting.
