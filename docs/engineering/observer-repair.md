# Issue #7 — bootstrap observer repair

Base: `30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8` (main).
Legacy launcher SHA256: `b5e58bb18b46330792b4922d6349bf25dd3f8b6c008efcb1e769b2484b12d518`.
Admission wrapper SHA256: `322c05426b643a2595530c26771351462765506edbac034806c875d41ba9f075`.

## Scope accepted by owner continuation

Repair the already diagnosed observer, not rerun BOOT-P01. This local workspace is
an isolated patch-development checkout, not the server worker or a full upstream build.
No host writes, model calls, credential reads, service starts, new task admission,
DF Assistant changes, merge or deploy. Existing BOOT-P01 results and one-shot markers
remain immutable. The reason for the historical missing after_run hook is UNKNOWN.

## Plan and rulings

1. Reproduce original interruption/idle bugs on local fixtures. Add failing tests
   for durable state, stale/wrong invocation, bounded idle reconciliation, and progress.
2. Implement a stdlib-only observer plus exact-SHA, build-only integration of the
   supplied launcher. Keep the old session/launch guards and cleanup ownership.
3. Verify real local filesystem atomicity, competing writers, subprocess signals,
   forced subprocess death and replay; test the built candidate without host/model calls.
4. Publish a separate PR for independent review. Do not install or run the candidate.

Ruling: idle is not success. Idle after a witnessed session can terminate observation
with an explicit missing-hook/unattested-exit reason; artifact and admission readback
are recorded separately. A marker alone never proves a successful model turn.
Ruling: the caller owns durable observation state before start, so an interrupted
callee cannot reset history to `not_started`. Unknown historical telemetry stays unknown.
Ruling: startup, retry, idle and wall limits are finite; old invocation/snapshot data
cannot satisfy the current operation. No dependency outage causes model escalation.
Ruling: the previous v1/v2 launch is consumed. The patch builder produces a review
candidate only; it cannot install, start, resume or reset a launch marker.

## Traceability

Issue #7 remains open until independent review and any applicable authorized host
acceptance. BOOT-P01's tool/Git/PR result is already preserved in PR #6 and must not
be recreated to repair its reporting. No product backlog task is closed by this patch.

## Tool boundary

The attempted pre-work issue comment was refused by the platform before a result.
It was not repeated using another tool or identity. This offline source repair is
a separate authorized operation; it does not implement any previously refused helper.

## Delivered source and verification

`bootstrap/pilot_observer.py` is the durable, action-free state machine.
`bootstrap/build_observer_candidate.py` integrates it into an exact copy of the
SHA-pinned old driver. The old driver is stored as an inert `.txt` regression
fixture, not as a runnable installation entry point. The builder never imports,
executes or installs the supplied launcher; the generated source is reviewed
and tested using fake host adapters.

Run the offline suite in a writable, disposable checkout:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_*observer*.py' -v
```

To inspect the patched source without installing or running it:

```sh
python3 -B bootstrap/build_observer_candidate.py \
  --source tests/fixtures/boot_p01_launcher_v1.txt \
  --out /tmp/new-observer-candidate.py
```

The output must not already exist. Building a candidate does not authorize its
execution. In particular, **do not execute it against the consumed BOOT-P01
installation**. No command to clear markers or change the v2 wrapper pin is
included. The existing admission-recovery v2 wrapper remains pinned to the old
driver and is not deployed or replaced by this PR. Future integration requires
an explicit new operation binding, exact-source review and separate operator
launch warning; old operations cannot be relabelled as a fresh model session.

The targeted suite has 55 checks: 36 observer tests, five builder tests and
14 integration/signal tests. The latter include three real local child-process
cases (SIGINT, SIGTERM, SIGKILL); fake clocks are used for long timeout cases.
Tests execute the candidate's actual observation/finalization control flow with
inert systemd/GitHub/file-ownership adapters. No model or service is started.
The root cause of the historic missing hook is not inferred from these tests.

Persistence uses a private owner directory, an exclusive lock, a new temporary
file, file fsync, atomic replacement and directory fsync. A persistence failure
propagates to finalization rather than being retried as a network problem.
The final checkpoint contains observations only, not secrets, raw responses,
model output, a verified bill or a fabricated normal-turn signal. SIGKILL keeps
the last completed checkpoint; it cannot run cleanup or save an in-flight event.

## Independent review and remaining acceptance

Review the exact source and test scope in this PR against issue #7. In particular:

- Check stale/inconsistent snapshots and changed service invocation fail closed.
- Confirm missing hooks and idle slots do not claim normal model completion.
- Verify interruption/persistence errors retain prior observations and enter cleanup.
- Check the legacy launch guards, admission policy, model profile and sandbox
  are not expanded; original v1/v2 files and result.json stay unchanged.
- Confirm no host target can be selected for the build-only output, including
  a path containing `..`; no supplied launcher is executed by the builder.

Independent review has not run. These tests are not trusted CI, native service
acceptance, a Python 3.10 runtime test, or the full product suite. Syntax was
parsed with Python 3.10 grammar; tests ran on the coordinator's Linux/Python
runtime. Production install/restart, automatic cleanup on the actual host,
full model/session attestation and acceptance of a future run remain separate.
No completed BOOT-P01 evidence is rewritten, and issue #7 is not closed by the
local green test result.
