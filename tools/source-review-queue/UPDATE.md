# GH102 update and rollback contract

## GH60 receipt refresh — current correction, 16 October 2026

Owner24h extension6222244874 retains old cycles; corrective candidate3/3, same
writer/branch/PR103. New window16Oct18:34:56UTC to17Oct18:34:56UTC;
source cutoff17Oct18:04:56UTC, final30min handoff. Previous windows/cycles,
reviews, archives and nativeHOLDs remain history; no install/pilot admission.

The existing writer replaces a comment receipt after each unique-comment GET,
then reads labels. An interruption can preserve an older confirmed label receipt.
Both confirmations must follow their own immutable comment intent; they need
not follow one another. The updater now checks this partial order for mtime
AND ctime. It retains individual same-FD/nonfuture/single-link/device checks,
DELETE-intent-before-label. A retained hold requires BOTH comment and label
mtime AND ctime strictly newer than that hold, independently; equal/coarse
proofs HOLD even when all JSON times coincide. Unknown/missing proofs HOLD.

All316prior tests plus4corrective tests PASS (320total/0skips); prepared7REDs are
permanent, plus a historical Review refresh and negative borrowed-label/pending
DELETE/hold boundaries. Candidate2's independent review reproduced stale label
proof after a hold with equal JSON times; the4corrective tests were allRED.
Candidate2's native16cases remain history, not final-HEAD acceptance. Details:
[evidence/gh102-delivery-refresh.md](evidence/gh102-delivery-refresh.md).

Packaging requires five explicit exact-HEAD PASS conditions: receipt_refresh,
native_clock_domain,4285700019,4281361556,4281361568. No older review qualifies
this correction. Build a NEW archive/private root stage; keep e92b75bf and all
earlier packets/stages unchanged. Existing systemd identity, four-file7fa0ee
predecessor, state-preserving admission/drain/rollback and disabled policy stay
mandatory. New owner full-journal/native check may still HOLD at later gates;
source tests do not attest their convergence. No source-stage installation.
Earlier total intent->comment->label ordering descriptions below are history;
this section supersedes only that inter-confirmation ordering assumption.

## Native clock-domain repair — 16 October 2026

Owner admission6210951994 adds3candidates in the same writer/branch/PR103;
old cycles/windows/results/archives remain history. Start07:57:45UTC,
source cutoff09:27:45/handoff09:57:45UTC. Review≤90min/candidate; no install/pilot.

GH25 and actual installed-writer fixtures disproved application timestamp≤inode
mtime. The candidate checks JSON timestamps against one captured application
wall clock (integer microseconds, no float or tolerance) and other JSON times.
Same-FD inode mtime/ctime coherence/order and STRICT post-hold receipt replacement
remain mandatory. Equal/ambiguous proof still HOLDs; updater never retimes,
replays or fabricates delivery proof. All three label/DELETE/hold clauses covered.

301tests PASS/all285retained; native writer fixtures16direct and32extended
cases PASS,16unknown initial outcomes blocked before GET reconciliation without
duplicate POST/DELETE. These device2065fixtures are not runtime2050, a live agent,
or full service update/rollback. Detailed report/readback boundaries and matrix:
[evidence/gh102-clock-domains.md](evidence/gh102-clock-domains.md).

Packaging requires independent native_clock_domain and all three priorP1 PASS
verdicts on the new exact HEAD. A NEW archive/private root stage is required;
keep the efa75ed archive/root stage and all earlier blocked archives. Fresh
actual-predecessor/journal/filesystem/service checks remain mandatory. The
following15October history is preserved; its three cross-clock application
timestamp≤filemtime clauses are superseded by this section.

## Current controlled updater — 15 October 2026

### Corrective notification candidate after independent review

Candidate1bd418f3 was independently rejected, report
[6200332301](https://github.com/pupkinson/SymphonyNext/pull/103#issuecomment-6200332301):
4285700019 FAIL; both older P1 preservation checks PASS. The actual queue's
hold-then-fallback path can update label proof while leaving a stale comment
receipt. Its280GREEN is historical and does not establish acceptance.

The sole permitted corrective candidate checks both content and the existing
canonical file-write evidence. Bytes and fstat come from the same nofollow FD.
Intent, comment receipt and label proof must have coherent nonfuture mtime/ctime
order on the same filesystem, with one link each. A retained delivery hold
requires a strictly newer COMMENT receipt and subsequent label confirmation;
a later label marker alone never resolves it. Equal or anomalous order HOLD.
The existing queue's actual successful GET reconciliation rewrites that receipt
without replaying POST/DELETE, and passes the gate with its hold retained.

This contract applies to trusted queue-written live journals produced by the
existing new-temp-inode/fsync/atomic-replace save/once. Operator copied/retimed
confirmations do not establish that provenance. Metadata is supporting
filesystem evidence, not a new journal field or a signature. Coherent clock and
adequate resolution are required; ambiguous metadata blocks transition and is
never rewritten by updater. Fresh1c-db filesystem/service attestation remains
UNKNOWN while DF transport is unavailable. No queue/execution change is needed.

Corrective suite285PASS/0skips (all244+36main+5corrective), including actual
candidate/predecessor stale-receipt RED→GREEN and actual recovery. All named
intake/drain/review/application/artifact regressions remain. A new independent
exact-HEAD verdict is still required before packaging; older failure reports,
budgets, cycles and REVIEW_BLOCKED archives are retained. Source cutoff and
handoff deadline below are unchanged; no install/pilot is included.

### Notification-journal source stage, P1 4285700019

Owner admission: #102 comment6199784094. New stage starts18:45:52UTC,
source cutoff22:15:52UTC, final handoff22:45:52UTC on15October2026.
All old2/2 plus additional2/2 cycles and their evidence remain history.
This grant allows one main candidate and at most one review-driven corrective
candidate; a cycle means a candidate handed to independent review, not a local
commit/test. Each exact-HEAD independent review has a90minute ceiling and
must explicitly assess4285700019 plus preservation of4281361556/4281361568.
Installation and pilot104/105 are outside this admission.

The complete before-patch contract inventory and the before-publication
self-check matrix are in [evidence/gh102-notification-journals.md](evidence/gh102-notification-journals.md).
`queue.py` and `execution.py` are read, never changed by this stage. No new
journal schema, notification sender or recovery engine is introduced.

`quiet` now verifies actual root legacy/linked-review delivery and every
developer attempt1..current, including every existing historical state notice.
Each attempt requires a terminal final and its matching complete notification.
Superseded Review notices bind their own candidate, not the later disposition.
A candidate alone does not prove a superseded Review notice was ever created;
the queue has no immutable prior-final history. Every extant Review directory
is nevertheless inspected. No missing terminal notification is compatible.

Comment intent must have its actual body schema, exact source formatter or
developer issue/generation/state/revision/result binding, and a positive integer
readback ID. Confirmed label absence needs its own correctly typed marker and
timezone-aware timestamp, later than any DELETE intent or delivery hold;
retained holds also require a strictly later comment receipt file replacement. A
root developer marker (`confirmed:false`) is only predecessor compatibility;
it cannot replace any nested delivery receipt. Legacy has no nested contract:
its ROOT final and ROOT delivery proofs are mandatory. Missing/corrupt/duplicate
or contradictory records and unknown POST/DELETE outcomes HOLD, even in old
generations. A stale delivery-hold may remain only after confirmed recovery.
Known `.record.json.PID` pre-replace leftovers are retained but are neither
API intents nor outcome receipts; they cannot replace canonical records.

The updater never re-POSTs comments, re-DELETEs labels, erases history or writes
fake delivery proof. Recovery remains the existing queue's responsibility.
Before-stop HOLD preserves a running service and releases only its verified
owned pause, including a pause from a prior interrupted operator invocation.
Stopped HOLD keeps the known closed gate and its receipt for explicit recovery.
An unowned pause or changed directory identity is never reopened. `check` stays
read-only apart from the existing exclusive updater lock.

Local qualification: all244 previous regressions retained plus36 notification
tests,280PASS/0skips. Both prepared REDs are permanent; unknown POST/DELETE
recovery is exercised through unchanged queue notify/deliver with API doubles,
not external writes. The complete actual-repository/video/unchanged-Git-object
regression remains included. Independent acceptance and package hashes are
recorded in the handoff manifest; these author tests are not a real-agent pilot.

Current DF Desktop read-only connectivity returned -32603 and then UNAVAILABLE
network timeout after three bounded attempts. Last actual installed predecessor
attestation below remains historical, not a fresh server verification. Source
development and offline packaging continue; server transfer/readback and root
execution are not claimed. Preserve old702 and15ec REVIEW_BLOCKED archives.

### Additional bounded source repair of review5531017643

Owner admission: #102 comment6196086808. Start 2026-10-15T15:41:29Z;
source cutoff19:11:29Z, handoff deadline19:41:29Z. At most two additional
repair cycles; d7fd134 used cycle1; this final candidate uses cycle2/2. Its
ordinary-rdc fixture avoids invoking root-only demotion, JSON generations are
type-exact, and outbox receipts must have their actual known outcome schema.
The production gate pins the existing995 UID/GID; no permissions are added.
The previous two cycles and all
earlier results remain history. Independent review has its own 90-minute
window starting with the new exact-HEAD request. Installation and #104/#105
are outside this source admission. The old7020615 review-blocked archive is
retained unchanged; its manifest must continue to refuse installation.

`update_queue.py` is now the owner-run updater, with commands `check`, `apply`
and `rollback`. CLI host, unit and installation/state paths are fixed. It does
not install dependencies, widen systemd/OS/API access, read credentials, label
issues, admit workers or restore old journals. `--install-start` is never used.
The prior contract below is historical; its UNKNOWN installed/native facts
have been superseded by #102 comment6188369467 and the fresh readback below.

The current service is source-review-only. Its verified static predecessor is:

| File | SHA256 |
| --- | --- |
| queue.py | 7fa0ee5624132253e487cf8093af5b1bd90fe5680c682d9672114cdbeccd33d1 |
| WORKFLOW.md | 863dcc07d8120597786370f7d43a8df7645b91940cf5ffc03fd08e674a4bc3e5 |
| tmux.conf | efbb1c10814140d8b2be96cc9e02cab29d15814f5e00b36ddb2821c46a1864ee |
| installed.json | b96964a5a184d6670628f9cf925a87dfbccedffcf219d870aa5662c5c1ce8b57 |

Bubblewrap0.6.1 and the six owner-run native prerequisite checks have passed;
they are not repeated by this updater. DF Desktop permits static readback in
/opt/symphony-next-queue-v1. PID854 and idle dashboard were unchanged by source
work. Root updater execution, installed PR103 and the live pilot remain NOT_RUN.

### Package and owner boundary

The handoff archive contains the reviewed updater, manifest, four payload files
and non-secret qualification evidence. The manifest binds exact commit/tree,
independent review URL/result, updater SHA, candidate hashes and the predecessor
above. Its review record is an auditable coordinator receipt, not a cryptographic
GitHub signature; the operator can verify its linked exact-HEAD bot result.
No package is admitted before completed independent review of the final bytes.
The owner receives the exact archive SHA and verified server path. The archive
must be copied, hash-checked and unpacked into a new private root directory
before executing Python with `-I -B`. Root owns the package and all payload files.

`check` verifies static hashes, disabled policy, retained legacy metadata,
unchanged unit identity/command, empty dashboard arrays and retired/reconciled
journals. An unknown outbox or an unfinished developer blocks transition.
It reads no runtime environment/auth files and changes no service or queue state.
The CLI takes only a local exclusive updater lock in the installation directory.

`apply` saves a verified root-private predecessor under
`/opt/symphony-next-queue-v1/.rollback/<exact-head>/` before stopping the same
service. **Admission is actually revoked before draining or stopping.**
The installed7fa0ee predecessor's `prepare_task` first calls `claim`, whose
atomic `mkdir(jobs/GH-issue)` precedes API/auth/model/budget operations.
The updater requires the ordinary service-owned0700 `jobs` directory and
temporarily removes its write bit (0500). Existing job directories and their
contents retain all their original permissions. Thus accepted workers can
finish; a newly dispatched issue cannot become an accepted task. No ignored
pause-file/dispatcher lock or unsupported runtime API is assumed. Pending
outer Symphony dispatches do not bypass this durable admission boundary.

The service UID/GID and all current cgroup process UIDs/zero effective
capabilities are checked. A real mkdir attempt after dropping to that UID/GID
must receive EACCES; a missing acknowledgement refuses the transition. The
gate remains held while the updater waits up to30s for empty dashboard arrays
and terminal, fully reconciled journals, and through confirmed service stop.
A task admitted during backup either finishes before stop or causes HOLD;
no accepted worker is killed to make the queue idle. A task arriving later
is denied before a model turn. These filesystem permissions only revoke
admission temporarily; root/sudo/API/capability/unit permissions never expand.
The candidate's developer policy must remain the exact disabled package
policy, so a new generation in an existing developer root is also not admitted.

Only after that handshake and confirmed stop does it replace queue.py,
execution.py, installed.json and an inert executor-policy.json. Workflow,
tmux, unit, service identity, credentials and state are retained. Payload and
durable control-record hashes are read back before start; dashboard and state
are checked after start. A failed start triggers exact static rollback; if
quiescence/known bytes cannot be established, it holds stopped rather than
overwriting unknown data. The backup record enables explicit rollback after
an interrupted static replacement. Repeated completed apply does not restart.

The durable, root-private `intake.json` receipt is written before chmod and
binds the exact head and original directory device/inode/UID/GID/mode; its
phase events are retained. A caught pre-stop interruption restores only that
owned gate and leaves the original service running. SIGKILL/power loss may
leave admission closed. Re-run the same package's `rollback` to adopt that
receipt, verify/drain, restore known static bytes and reopen admission after
healthy startup. It never reopens an unowned0500 directory or changed inode.
An interrupted/unknown static state remains HOLD with admission closed until
reconciled. Neither a kill signal nor an ordinary stop is used as a drain.

`rollback` requires idle/reconciled jobs and unchanged approved static bytes,
then uses the same effective admission gate/drain before stopping. Before
restoring7fa0ee it checks **every** historical `review-links/GH-*.json`:
exact source final and link hashes in `linked-review-applied.json`, matching
issue/generation/HEAD/base candidate, and identical expected acceptance/final.
The latest accepted-artifact pointer must equal the entire newest accepted
disposition for that issue. Later Rework may legitimately retain an older
accepted artifact; an old review cannot accept a new generation or HEAD.
Missing application, missing artifact, self review, duplicate/orphan linkage,
malformed receipt or unknown write all block rollback without deleting or
repairing journals. `review-links` is included in the transition seal.

It then restores the exact predecessor static files and removes the two previously
absent developer files. It never restores an old copy of state. If pilot policy
was enabled or jobs/outboxes remain pending, reconcile/revoke them first under
their existing admission; this script will not silently terminate paid work or
remove GitHub labels. Repeated completed rollback does not restart.

Qualification uses real temporary files and a systemd test double, including
failed startup, interrupted replacement, stale/author review, unknown outbox,
active work, symlinks and repeated calls. Actual7fa0ee predecessor recovery was
also exercised on owned retired/developer journals: no API/model call or state
change; it skips the preserved developer roots. These checks are not a real
service update or live rollback. Their exact logs/seals accompany the package.
The permanent suite contains the two unchanged original P1 reproductions and
the exact installed predecessor source (SHA pinned above). A separate real
kernel test executes that predecessor under an unprivileged process against
owned temporary journals: new admission is denied while an existing job
finishes. Local Work's single-UID namespace uses a child with all capabilities
dropped after exec; 1c-db uses ordinary rdc. No extra UID mapping, sandbox
relaxation, native model turn or live service change is used for qualification.

After owner-authorized apply, independently read back installed hashes, service,
policy and dashboard. Then update the existing #104/#105 base bindings and
grant/label those two tasks only after their separate live admission. This
package leaves their dispatch disabled and creates no duplicate issue.

<details>
<summary>Historical preparation-only contract, superseded where noted above</summary>

Status: **SOURCE_CANDIDATE / NOT_INSTALLED / LIVE_NOT_RUN**.
This is an update preparation contract, not an admitted server command or a
working updater. The old `--install-start` is not used to update an existing
installation. No service, installed file, root permission or credential changed.

## Currently blocked evidence

Initial DF Desktop 1c-db reads failed with timeout/-32603. Connectivity then
recovered: fresh hostname=1c-db, uid/gid=997(rdc), cwd=/srv/rdc-workspace and
allowedDirectories=[/srv/rdc-workspace]. Source checkout is clean at60e4a6d.
Service metadata confirms active/running/enabled, MainPID854, NRestarts0,
User/Group=symphony-next and the expected queue WorkingDirectory/ExecStart.
This supersedes the initial connectivity blocker, not the installed-version
gate. Installed /opt and /var/lib are outside permitted filesystem access;
their code/workflow hashes and rollback predecessor remain UNKNOWN.

The missing input is an authorized, non-secret attestation of the actual
installed predecessor, bound to the running service. An existing permitted
attestation/export mechanism can provide it in the allowed workspace. No such
fresh receipt was obtained, and no unverified owner command or expanded scope
is proposed. Earlier denied /opt, native dependency and compound-source
operations are not retried or delegated through another route. Restored
connectivity alone does not authorize them.

## Candidate package after independent exact-HEAD source review

The update has two runtime files: `queue.py` and its sibling `execution.py`.
Retain the existing WORKFLOW, tmux config, unit, identity, model installation,
credentials and state roots unless the independently reviewed predecessor
comparison proves a specific required change. No second Symphony is installed.

The existing `installed.json` retains its prior fields, updates
`script_sha256` for the exact queue, and adds:

```json
{
  "execution_schema":"snq-execution-install/v1",
  "execution_sha256":"<SHA256 of the independently reviewed execution.py>"
}
```

Installed execution refuses an absent/mismatched sibling pin. Pinning is a
trusted service-owned consistency check, not a signature against coherent root
rewriting. Install the inert disabled policy from README_EXECUTOR first. Merely
editing metadata is never verification of the installed bytes.

## Minimum controlled transition

1. Obtain independent acceptance for the exact candidate. Restore authorized
   read access; verify host, current code+workflow hashes, identity, unit, actual
   task state, native binary and existing resource limits. Compare all changes
   against that exact installed predecessor. Do not infer it from PR90.
2. Freeze intake and drain/stop owned running workers through the existing
   permitted lifecycle. Confirm no active model/test worker and reconcile every
   unknown outbox. Preserve all claims, reservations, task snapshots, results,
   legacy layouts, attempts and budgets. Record state counts/hashes.
3. Save a verified read-only predecessor copy of code, workflow/tmux, unit and
   metadata without credentials. Stage/hash candidate bytes off-line. With the
   service confirmed stopped and owner update admission, replace only reviewed
   static files and metadata; keep executor policy disabled. Do not expand unit
   permissions or repair system isolation by disabling restrictions.
4. Verify installed hashes/readback before starting the same service. Confirm
   controller-only readiness and unchanged historical state; no task labels are
   granted by startup. Reconcile rather than replay interrupted attempts.
5. Under the existing service identity, verify the actual sandbox, Codex
   protocol/auth/quota, bounded tests, scoped GitHub publication and stop. If a
   capability is absent, classify it and hold; do not provision privilege or
   copy another account's login. Only then admit a limited owner-approved pilot.

## Rollback that must be verified on the actual predecessor

Stop intake and owned workers first. Remove developer/review pilot admission
labels and reconcile uncertain writes; ensure no in-flight operation can finish
after restore. Preserve the new journal/evidence as well as old state. Restore
the verified predecessor static bytes and metadata only, compare hashes and
start it with execution disabled. No destructive DB or journal restore.

New developer roots contain a scoped `label-removed.json` compatibility marker
so the published PR90 predecessor's recovery skips them. The new controller
recognizes `execution.json` before that marker and still reconciles new attempts.
Tests verify this ordering and immutable legacy behavior; this is not proof
that an unknown installed predecessor implements the same recovery contract.
If that predecessor cannot safely ignore preserved developer journals, rollback
must remain stopped until a reviewed compatibility route is available.

Linked reviews have a separate downstream-applied marker: retirement of their
queue label is not proof that the developer disposition was applied. Recovery
reconciles a missing marker first. An immutable acceptance record converges the
terminal result and accepted-artifact pointer, including a crash between those
writes. An uncertain preparation branch is authoritatively read back without
another POST; the interrupted attempt then stops without replaying a model.

Actual service update/rollback, 90-minute native capacity and independent
runtime readback are **NOT_RUN**. Installed-predecessor compatibility is UNKNOWN.

## Bounded live pilot, only after those gates

Admit exactly two independent synthetic developer issues with non-overlapping
file scopes and distinct branch/workspace/thread, run them simultaneously,
observe real changes and actual permitted tests, and verify two separate exact
reviews. Also exercise stop/timeout/restart without duplicate model turns, PRs
or review tasks. Preserve failed attempts and costs. Do not label the MVP graph
or all backlog for launch. Unit/process/protocol fixtures are not this pilot.

</details>
