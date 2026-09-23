# PR8 delta: persistence failure must not veto a proven safe stop

Reviewed parent: `c02eee60ffcc98afd3f94839f6666164545d3dcf`.
Owner-supplied independent review SHA256:
`483bf723244c84f56ed673648d815752af434368ad81c7203da7ac0e8e526d47`.
Scope: the P1 in `bootstrap/start_ownership.py`, not a new BOOT-P01 launch.

## Confirmed failure and correction

The original ownership reconciliation called `service_started()` and `_save()`
before returning the verified invocation. A permanent checkpoint `OSError`
prevented the caller from reaching stop; an `ObserverError` escaped the narrow
stop handler and skipped the remaining cleanup. The new fault cases reproduce
both paths on the exact generated launch/finally code with inert host adapters.

Ownership reconciliation now performs only bounded reads and in-memory state
updates. It retains every existing ticket/witness/nonce, boot/time, driver,
drop-in and invocation check. `record_reconciled_start()` is a separate diagnostic
step. On the normal path a diagnostic failure ends observation and enters
cleanup. During cleanup its `OSError`/`ObserverError` is contained and marked as
`observer_checkpoint_failed`; it cannot veto a stop authorized by the verified
return value. The final live InvocationID read is still required before stop.

This is not blanket error suppression: identity/readback failures still refuse
stop. A storage error is never evidence of ownership. Foreign, replaced and
missing-witness invocations remain unconfirmed and are not stopped. Existing
manager-side lifetime bounds and the documented non-atomic compare/stop race
with an uncoordinated administrator are unchanged.

Other cleanup actions continue after a checkpoint failure. The report remains
STOP with `persistence_error=true`, not a synthetic PASS. If the final result
file also cannot be written, cleanup has already run; bounded JSON is printed
with `result_persistence_failed`. That stdout fallback is not durable storage
and is not guaranteed to survive a closed terminal or host failure. Old evidence
is never rewritten to claim a successful historical run.

## Verification

Baseline: the relevant inputs were matched to the published blob SHAs, and all
63 existing observer tests passed before changes. Ten added tests cover:
permanent ENOSPC/ObserverError before start confirmation and after an observed
session; lost start acknowledgement; interrupted start; foreign or replaced
invocation; missing witness; and a separate final-report write failure.

Before the code fix, eight new tests failed with the expected still-active
service or escaping persistence exception; two safety controls already passed.
After the fix, all ten new tests and all 63 existing tests pass (73 total).
The eight original start-boundary assertions are retained; their shared fixture
was extended with latched storage faults and observation of cleanup effects.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s tests -p 'test_*observer*.py' -v
```

These are coordinator-local tests, including the existing real local signal
subprocess cases. systemd, GitHub and identity/ownership adapters are inert in
lifecycle tests; ENOSPC is injected rather than filling the host disk. No model,
service, installation, credential read, dependency installation or production
mutation occurs. Python 3.10 grammar is checked, not a native Python 3.10 runtime.

## Remaining gates

Independent delta review of this exact new source, and separately authorized
native integration remain outstanding. PR9's positive review is unaffected.
No second full PR9 review is requested. Old v1/v2 launchers, workspaces, results,
one-shot markers, admission logic, model profile and sandbox remain unchanged.
The historical missing-hook cause remains unknown. Do not run the generated
candidate against the consumed BOOT-P01 or clear its markers. No new launcher
command is provided by this patch; future runtime work still requires explicit
advance notice and tmux for the operator.
