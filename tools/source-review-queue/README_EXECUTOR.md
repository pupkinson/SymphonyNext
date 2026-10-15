# GH102: developer and independent reviewer in one Symphony

Source candidate for #102, stacked on PR90 exact
`60e4a6d4b9054dfdb5d55e0f2b76a9fc0b10e506`. Not installed, not a release
approval. #95/SPECIFICATION v0.5/PR79/82/84 and #33/PR99 are unchanged.
This implements a bounded execution profile, not the #100 DAG planner or a new
tracker. Existing Symphony still polls/schedules GitHub; its existing capacity
is not evidence that the installed server can run two developers safely.

## Code and selection

`candidate/queue.py` retains reviewer profile, permissions, native-tool denials,
source packets/pages, prompt integrity, claim and reservation logic. A strictly
parsed `snq-develop/v1` manifest routes to the sibling `execution.py`. Mentioning
that string in prose does not change a review's role. Existing v1/v2 reviews do
not need executor configuration. Unknown schemas/roles fail closed.

The developer has the same disabled native tools and read-only named model
permission profile. Three dynamic tools are exposed instead of a general shell:

| Tool | Enforced operation |
| --- | --- |
| `snq_dev_read` | Bounded base64 ranges from the exact repository snapshot or an admitted accepted input |
| `snq_dev_write` | UTF8 compare-and-swap writes to exact approved files in this attempt's workspace |
| `snq_dev_test` | Select a test ID from a root-owned fixed argv allowlist; no task-provided command/flags/env |

An owner-authored, labelled issue is necessary but insufficient for development.
`executor-policy.json` beside the installed queue must be a regular root-owned
file, without group/other write access or unsafe ancestors. It must contain an
enabled grant matching the issue title/body signature, repository ID, exact
base/tree and generation. The signature includes every instruction byte.
Root-owned configuration is an existing owner/operator responsibility; the model
cannot write it. No credentials, API scopes or OS permissions are provisioned.

An inert configuration, suitable for a reviewed update with execution disabled:

```json
{"schema":"snq-executor-policy/v1","enabled":false,"revision":"not-admitted","tasks":{}}
```

The issue manifest has exactly these fields (values below describe its shape,
not an actual task/admission):

```json
{
  "schema":"snq-develop/v1", "role":"developer",
  "repo":"pupkinson/SymphonyNext", "repo_id":1381693716,
  "head_sha":"<exact 40-hex base commit>",
  "base_sha":"<same exact base commit>",
  "tree_sha":"<exact tree>", "generation":1
}
```

Each `tasks["<issue number>"]` grant contains exactly `role`, `enabled`,
`generation`, `issue_signature`, `repo`, `repo_id`, `base_sha`, `tree_sha`,
`base_ref`, `writable_paths`, `tests`, `requirements`, `requires`, `deadline`,
`max_seconds`. `tests` maps stable IDs to fixed argv arrays; `requires` contains
`{issue, head}` references to accepted artifacts. Unknown fields are rejected.
There is no issue-controlled model, sandbox, API target or permission override.

## Complete repository input, including the upstream video

Developer materialization uses bounded raw Git blobs, verifies byte count and
Git object SHA, and retains every file. GitHub's raw blob media type is documented
at https://docs.github.com/en/rest/git/blobs#get-a-blob. Reviewer JSON transport
and its response limits are unchanged. The writable/read-tool file limit remains
4MiB; the complete workspace limit remains 32MiB and 4000 entries.

Only `.github/media/symphony-demo.mp4`, mode100644, blob
`32b1f857f45eb901905ea24355b599fb417f53c5`, exactly30446771bytes, gets the
larger immutable-input read limit. A different path/blob/mode/size is refused;
new upstream large assets require another reviewed pin. Snapshot verification
hashes this complete asset and refuses modification. It cannot become writable
or be read through the model's bounded file tool. There are no omitted files.
Publication starts from the exact original Git tree and emits only admitted
changes, preserving every untouched blob and mode, including the video.

`test_queue_real_repository.py` uses all199files/33232573bytes in the actual
e6fa3d22 base, never a replacement small repo. It also applies the emitted tree
delta through Git's index/tree implementation in a separate object directory
and checks all untouched object IDs. Local Git replaces HTTP in this fixture;
the separate raw HTTP tests check caps, hash/size, scope and HTTP errors. These
checks are not live model or target-service sandbox evidence.

## Isolation and actual command gate

Every developer receives `workspaces/GH-N/developer-gG`, a fresh native thread,
and branch `snq/gh-N/gG`. Before ready/model reservation the controller verifies
the exact base ref/commit/tree and every materialized blob, checks accepted
inputs, probes the existing pinned Codex metadata/auth/catalog, and creates the
owned remote branch. The repository is an API-materialized snapshot; Git
credentials and `.git` are not placed in the workspace. The model edits through
the broker, and the service publishes Git objects/commit/PR on its behalf.

Tests require `/usr/bin/bwrap` with usable user/PID/network namespaces under the
existing service restrictions. The sandbox starts from an empty mount tree,
unshares all namespaces, clears env, mounts system runtimes read-only and the
repository read-only, and permits writes only through individual approved file
binds. Accepted inputs are mounted read-only at `/inputs`; temporary files stay
in private `/tmp`. Host homes, service journals, model/Git credentials, sockets,
other workspaces and production are absent. Native model command/file tools
remain disabled. No fallback to unsandboxed execution exists.

The actual sandbox preflight checks a distinct network namespace, absent host
state/home and a non-writable repository parent before a model may start. A
missing binary, unsupported namespaces or service confinement failure blocks the
task before auth/model launch. This source does not alter kernel, systemd,
sudo, Docker, credentials or capabilities to make that check pass.

Source scope is rechecked before publication, including modes, symlinks, newly
created and deleted files. Root rules/spec/policy/planning/bootstrap/skills and
GitHub Actions paths cannot become writable. Shell interpreters, sudo, Docker
and env dispatchers cannot be test executables. Commands are still untrusted
code: the OS sandbox, rather than their names or the prompt, enforces isolation.

## Durable lifecycle and evidence

Per-issue flock and exclusive attempt directories enforce one owner. The native
proxy's exclusive `model-session.claim` permits one paid session per attempt.
Polling/restart never replays that session. A new admitted generation can follow
a terminal attempt only, with at most two repairs and no extension of the first
absolute deadline. Initial outer execution is at most 12600 seconds, reserving
30 minutes inside the owner's four-hour window; an individual model worker is
at most 5400 seconds. Existing daily reservations count both roles, including
generation-specific developer reservations. No historical budget is reset.

Local monotonic and absolute deadlines, durable stop file, current generation,
root policy and issue admission are checked during execution. A blocking issue
read is followed by another stop/deadline/policy check before acting. Command
timeouts terminate only the owned process group before its leader is reaped;
stdout is bounded. Every file write invalidates prior test evidence.

Test evidence records actual argv/exit, exact complete source-input digest,
output hash, elapsed time and sandbox. Missing, failed or stale tests prevent
publication. Model prose is not test evidence. Preparation/prompt/profile pins
and an actual full-forwarding receipt are checked again at finalization.

The service creates one draft PR and one separate `snq-review/v2` issue with exact
HEAD/base/tree, approved requirements, test evidence and the source manifest.
Each external mutation has a durable intent and authoritative readback. An
ambiguous write is reconciled by its exact content/branch/marker; without a
readback it holds rather than repeating POST. Unlocatable orphan tree/commit
outcomes require reconciliation, not another commit. Recovery only reconciles
publication/results and never launches a replacement model.

Review delivery and downstream acceptance have separate durable completion
markers. An immutable acceptance record can rebuild a missing accepted-artifact
pointer after a crash. A preparation branch with an uncertain POST outcome is
read back against its exact expected revision; a confirmed interrupted
preparation stops without a model replay. An absent/mismatched branch never
permits a second blind POST or a fabricated receipt.

The developer issue loses dispatch admission when its result is published.
Only the newly created review issue receives the existing reviewer label, after
its owner/body/link are verified. Coordinator maps #95/#101 receive no labels.

## Independent acceptance and descendant inputs

The reviewer runs the existing source-only profile in a different GH workspace
and fresh thread, with no developer tools or writable author history. Its exact
source report must finish with one `snq-verdict` JSON fence:

```json
{"head_sha":"<reviewed HEAD>","base_sha":"<reviewed base>","verdict":"accepted"}
```

`rework` and `blocked` are the other allowed dispositions. A complete source
transport alone is not a positive verdict. Missing/incomplete review blocks;
findings yield Rework. Author/reviewer thread equality, same issue, changed
HEAD/base, revoked admission or an older generation cannot produce acceptance.
A new commit requires its own review. The author has no acceptance tool.

Successful author tests plus a valid independent source verdict produce
`AcceptedSource`, never automatic release/Done. The service stores a concrete
repository/commit/tree/PR artifact and review provenance. A dependent grant must
name that exact accepted HEAD; the controller verifies the current generation
and PR HEAD and materializes the complete accepted bytes as immutable inputs.
A status string alone never releases a dependency.

## Verification boundary

Run from repository root:

```sh
python3 -B -m unittest discover -s tools/source-review-queue/tests -v
```

The tests include real files, real pipes, real Python fixture execution,
competing process claims, timeout/group cleanup and synthetic GitHub/model peers.
Where bwrap is replaced by a fixture command runner, evidence is explicitly
`TEST_DOUBLE_NOT_NATIVE`. This does not qualify native isolation, model
entitlement, the installed service, a live GitHub publication by this runner,
two concurrent real agents or release readiness.

The author's separate local bwrap preflight failed with NETLINK_ROUTE
`Operation not permitted`; it was not bypassed to launch an agent. Server
connectivity/installed revision and native isolation remain separate gates in
[UPDATE.md](UPDATE.md). Preserve all historical source/native refusals.
