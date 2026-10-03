# Recover prepared images and retain them — implementation plan

> Agentic execution: superpowers:executing-plans, one native writer and one
> existing independently authorised read-only SOURCE reviewer after verification.

**Goal:** recover both lost dependency images, prove fresh quality and install
the accepted direct-source transport while dedicated CI units remain paused.

**Architecture:** a new single-use owner helper, based on accepted PR55, reuses
the unchanged builder/worker/staging contracts. Two restricted signal-wait
containers retain the images against ordinary pruning. Fresh receipts replace
only the profile image/preparation bindings; historical evidence stays immutable.

**Tech stack:** existing Python3.10+ / Docker classic daemon / pinned Codex0.155.1.
**Spec:** PROJECT_RULES.md v0.5, planning/spec-index.json composition
0.5+MCP-SN031-r2; operational ACCEPTED GH24#5965451706.

## Global constraints

- Source base10fc787a2b03c0dbd602f35991dd9aacd36718ab,
  tree812fe91fc7fe9154229f2e4ecad475b98da5250e; installed38ead317... .
- Exact activated old policye1ab900a... and exact saved zero-read HOLD9ab88b... .
- Only new recover_retention.py, focused tests, README and this plan may change.
- Accepted reviewer/probe/repair_review, owner/refresh/controller/worker/journal,
  recipe/locked profiles/thresholds, units/models/binary/app/rules remain fixed.
- Initial plus max2 source repairs; no model/profile escalation. No old claim
  replay/deletion, fake timestamp freshness, CI check or global pruning changes.
- Owner-only execution in existing root tmux on1c-db; agent gains no root,
  Docker socket or credential access. No production/DF resource intersection.

## Review focus

- Cached rebuild IDs may differ: old receipt never authorises a new image.
- Docker image/container/system pruning: running references, not tags alone;
  no promise against forced deletion or daemon data loss.
- Unknown create/start/tag/build outcome: preserve claim/resources; no replay.
- Drift after expensive work: old package/policy/hold/receipts/daemon and both
  image/keeper identities must be rechecked before commit intent.
- Partial install/policy/proof writes: retain backups, remove incomplete proof,
  keep timer/service paused; reconciliation required, no automatic rollback.

## One independently reviewable increment

Files: NEW ci/continuous/snci/recover_retention.py and
ci/continuous/tests/test_retention_recovery.py; MODIFY CI README.
Consumes unchanged Source, refresh, repair_review history checks, owner builder,
runner.run/validate_result, accepted native probe. Produces perform(owner,head,
api,source) and completed(state,policy,raw,owner), plus paused completion proof.

- [x] RED: absent-helper tests on real temp package/policy/journal/receipt files;
      name exact failed assertions, capture actual exit/hash.
- [x] GREEN preflight: exact source trees/deltas/ancestry, prior activation,
      policy/old receipt/known hold, target/rules/binary, stopped units,
      no pending worker, two missing images/tags, unchanged seed/daemon.
- [ ] Claim once, stage exact Git blobs, run one accepted offline native probe.
- [ ] Build each pinned source/recipe once. Create restricted running keepers:
      nonroot10001, networknone, readonly, no mounts/caps/secrets/socket,
      no-new-privileges, 0.05CPU/32MiB/16PIDs, restartunless-stopped.
- [ ] Full locked worker quality once per rebuilt image, fresh receipts and
      timestamps. Preserve all old receipts/journal/policy/package bytes.
- [ ] Recheck old snapshot and new image/keeper/staged bytes, archive predecessor,
      record intent; change only revision and image/preparation profile fields.
- [ ] Proof/readback bound to policy, manifest, old history, native log and
      fresh quality receipts/keepers; stop units remain disabled/inactive.
- [ ] Full source suite, grammar/diff checks, real owner-identity refusal;
      independent exact-HEAD SOURCE review before protected execution.
- [ ] Hash-pinned owner handoff once. Only after COMPLETE readback, dedicated
      CI service once under unchanged daily<=4. Actual protected check gates
      merge/deploy; timer remains disabled and no repeated model turn.

Deletion actor UNKNOWN. Owner verified missing main/sn004 IDs and tags, surviving
seed, unchanged policy/package and no PR55 claim/stage/backup. Official semantics:
https://docs.docker.com/reference/cli/docker/image/prune/ and
https://docs.docker.com/reference/cli/docker/system/prune/ .


Author verification: focused genuine RED10 failures for absent helper,exit1,
logSHA256c0dc593d03d6b5d2f66c599ed8398f77115224ece6c7704cf493c33578f8bd99.
A prior run also collected15 imported fixture tests; import corrected before
focused RED. Additional inherited-healthcheck regression produced one real
failure (Hold not raised),exit1/log0f0dd2601df26750efbbcbf23a4309babd2f4c0daed41fca234640d0c6433979;
fixed by disabling/checking healthcheck so only the signal wait can execute.
Full CI source suite213 tests,212passed,one existing native isolation skip,
0failures/errors,exit0; captured-and-fsynced logSHA256
0209e133f92ea046ac88683fb7b50cf2e41ba1487156f089f18aef7b81215374.
Grammar Python3.10 and diff-check exit0. Actual helper entry outside owner
environment: HOLD retention_owner_identity,expected exit1. No protected
Docker/native transition/quality/live model/check execution by this source work.
