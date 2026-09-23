# PR8 — reconciliation of an uncertain start (review follow-up)

Input review: `38c3dcf935e50d61aecf8d1bbeae19c2c95033be`, report SHA256
`154ae22e36420d9f450fc93a169417dd9a5be2dd90aecccfcbb7acde5a405272`.
The P1 describes a real gap: systemctl may start the service before the caller
receives its return value or saves InvocationID. A timeout/signal then caused
cleanup to refuse stopping an invocation it could not correlate.

## Correction, not another pilot

The build-only candidate adds a fixed ExecStartPre witness under the existing
UID/GID995. Before ExecStart it writes systemd's non-secret INVOCATION_ID,
a fresh operation nonce, exact driver/window hashes, boot ID and monotonic time.
The owner saves the matching ticket before its only start request. No root
process, privilege prefix, Docker access, credential export or model call is
added to ExecStartPre. The witness is exclusive: it cannot overwrite a consumed
record. Existing BOOT-P01/v1/v2 paths and one-shot guards remain unchanged.

After an uncertain acknowledgement, cleanup performs at most three reads over
a 15-second reconciliation budget. It requires the receipt to match the ticket,
time window, source, loaded drop-in and current InvocationID; then it can stop
that operation even if the original start call never returned. A different
invocation or unproven ownership is not stopped. Identity is checked again just
before the stop request. The same dedicated-UID/trusted-operator assumptions as
the bootstrap apply; this is not a proof against a malicious process sharing
UID995 or an uncoordinated root administrator racing systemctl. There is no
atomic compare-and-stop primitive in this implementation.

A verified manager-side deadline is now a prerequisite to issuing start:
Type simple/exec, Restart=no, RuntimeMaxSec<=1800, TimeoutStartSec<=45,
TimeoutStopSec<=45, KillMode=control-group, SendSIGKILL=yes. The drop-in supplies
these limits and the code reads the effective settings. Thus loss of the caller
does not remove the configured service-manager limit. These are separate
activation/runtime/stop limits, not a promise that all three take 1800 seconds
in total. If receipt/state is unavailable, cleanup reports uncertainty and
retains the bounded configuration; it does not infer ownership or restart.
The old installation already specified RuntimeMaxSec=1800: the finding does
not prove that it had no systemd deadline, only that caller cleanup was flawed.

## Evidence and limitations

Eight new inert lifecycle tests reproduce the old failure and cover interruption
or timeout after real-start simulation, interrupted first identity read, delayed
witness, missing witness, foreign invocation and rejected unbounded manager
configuration. The existing lifecycle fixtures now emulate the added manager
metadata and witness; their assertions were retained, not marked skipped.
The exact-source AST change allowlist now also includes dropin_text. Original
session guards, API scope, admission function, model args and sandbox are still
checked as unchanged. The baseline 55 checks and eight additions pass locally.

This is source-only/offline evidence, not native systemd, UID995 or deployment
acceptance. The historical missing after_run marker remains unexplained. Neither
old result.json nor the server installation is modified. A new exact-HEAD review
is required. The old v2 admission wrapper is not silently repinned, and no
command is supplied to launch the used BOOT-P01. Future integration must retain
v2 admission recovery and verify the real native lifetime/witness behavior.

References used for the fixed interface (systemd v249, not a latest-version claim):
- https://raw.githubusercontent.com/systemd/systemd/v249/man/systemd.exec.xml (INVOCATION_ID)
- https://raw.githubusercontent.com/systemd/systemd/v249/man/systemd.service.xml (ExecStartPre/timeouts)
- https://raw.githubusercontent.com/systemd/systemd/v249/man/systemd.kill.xml (control-group/SendSIGKILL)
