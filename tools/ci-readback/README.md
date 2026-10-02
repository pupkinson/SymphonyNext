# GH24: read-only snapshot of the installed CI state

This is a diagnostic input for the existing PR14 verification task, not another
verifier, an installer, or an alternative release path. It never starts/stops a
service, invokes Docker/Codex, sends network requests, imports installed Python
code, modifies a policy, resets a claim, or publishes a trusted status.

## Exact scope

Only six fixed files are read: installed revision, published profile definitions,
installed manifest (hash and entry count only), protected policy, and the existing
prepare-main / prepare-sn004 acceptance receipts. Policy output is a whitelist;
credentials, key paths, raw exception messages, arbitrary strings and logs are
not output. No auth.json, private key, runtime.env, journal or other project is
read. Manifest entries are not traversed. Individual file reads reject symlinks,
nonregular files, non-root ownership, unsafe file modes, oversize and read races.
The two fixed subprocess calls are `systemctl show` on the CI service and timer.
The persistent Symphony queue is not queried or modified by this script.

A SHA256 is a fingerprint of bytes observed, not proof that those bytes were
reviewed or accepted. `reviewed_target_matches` compares only PR14 head/tree and
one changed test lock; it does NOT attest all locks, thresholds or policy. Quality
numbers are recorded receipt fields, not independently re-executed tests. The
snapshot is not transactionally atomic across files. Every output retains
`readiness=NOT_ATTESTED`; absent or unreadable inputs remain explicit.

## Owner use

Copy only snci_snapshot.py to `/root/snci_snapshot.py` on `1c-db`. Inspect and
verify its delivered checksum, then run `python3 -I -B /root/snci_snapshot.py
--read`. It prints a sanitized JSON document. No installation or task admission
occurs. `SNCI_SNAPSHOT_COLLECTED` means all six inputs were collected;
`SNCI_SNAPSHOT_PARTIAL` preserves readable results and identifies missing,
unreadable or invalid files. Neither status means CI is ready. Unlike execution
and repair helpers, repeating this read does not reset or consume a job attempt.
Do not run any previous one-shot prepare/repair command merely because a receipt
is absent or a profile is old.

## Offline checks

Run `python3 -B -m unittest discover -s tools/ci-readback -p 'test_*.py' -v`.
Tests use fixture files, mocked systemctl, and injected readers only. They do not
read real CI files, credentials, use network/model access or start services.
Native owner readback and independent protected PR14 execution remain separate.
No source/runtime changes are made to PR14, its accepted review, or PR19's CI
implementation and its uninstalled profile candidate.
