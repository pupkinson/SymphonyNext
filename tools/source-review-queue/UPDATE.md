# GH102 update and rollback contract

## Current controlled updater — 15 October 2026

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
service. After confirmed stop/quiescence it replaces only queue.py,
execution.py, installed.json and an inert executor-policy.json. Workflow,
tmux, unit, service identity, credentials and state are retained. Payload and
durable control-record hashes are read back before start; dashboard and state
are checked after start. A failed start triggers exact static rollback; if
quiescence/known bytes cannot be established, it holds stopped rather than
overwriting unknown data. The backup record enables explicit rollback after
an interrupted static replacement. Repeated completed apply does not restart.

`rollback` requires idle/reconciled jobs and unchanged approved static bytes,
then restores the exact predecessor static files and removes the two previously
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
