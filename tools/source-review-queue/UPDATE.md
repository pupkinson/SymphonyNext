# GH102 update and rollback contract

Status: **SOURCE_CANDIDATE / NOT_INSTALLED / LIVE_NOT_RUN**.
This is an update preparation contract, not an admitted server command or a
working updater. The old `--install-start` is not used to update an existing
installation. No service, installed file, root permission or credential changed.

## Currently blocked evidence

DF Desktop 1c-db returned `Connection timed out` for hostname/id/pwd and
get_config, then `-32603 Internal error` for a second minimal host check. Host,
allowed directories, current service identity, installed code/workflow and
rollback predecessor are UNKNOWN. Earlier denied `/opt`, native dependency and
compound-source operations are not retried through another route.

The minimal next owner action is to restore the existing DF Desktop 1c-db
connection. Verification is a successful hostname/id/pwd read identifying
`1c-db`/`rdc`, followed by allowedDirectories and permitted service/source
metadata reads. No command is supplied for an unverified path. A restored
connection is not permission to replay an earlier denied operation.

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

Actual service update/rollback, 90-minute native capacity and independent
runtime readback are **NOT_RUN**. Installed-predecessor compatibility is UNKNOWN.

## Bounded live pilot, only after those gates

Admit exactly two independent synthetic developer issues with non-overlapping
file scopes and distinct branch/workspace/thread, run them simultaneously,
observe real changes and actual permitted tests, and verify two separate exact
reviews. Also exercise stop/timeout/restart without duplicate model turns, PRs
or review tasks. Preserve failed attempts and costs. Do not label the MVP graph
or all backlog for launch. Unit/process/protocol fixtures are not this pilot.
