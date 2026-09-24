# GH-4 candidate diagnostics

The exact-source builder inlines the stdlib diagnostics and explicitly binds
`Api.request` to its adapter. The archival class, `validate_api`, credentials,
ownership, observer and launch guards remain intact. No candidate is installed
or launched by this change. This is independent maintenance, not BOOT-P01
admission or platform acceptance.

Records contain only method, allowlisted relative endpoint (query omitted),
status or fixed transport category, elapsed seconds, attempt, classification,
and grammar-checked request ID, permissions, rate-limit and Retry-After fields.
Provider messages are compared against fixed known signals but never emitted.
Bodies and credential/header values outside those grammars are not recorded.
Successful response data still reaches the existing caller and its validators.

Diagnostic delivery is separate from the HTTP outcome. An emitter exception
sets the sticky, bounded `api.github_diagnostics['delivery_failed']` flag and
cannot replace a successful response, authentication rejection or unknown write
outcome. Existing reconciliation and admission cleanup therefore still run.
Only the boolean is retained; exception text and failed records are not queued.
This flag is in-memory evidence for the caller, not a durable receipt or a claim
that output was delivered. Operator interruption (`BaseException`) propagates.

401 is an authentication rejection; a known inaccessible-resource message proves
a permission rejection without identifying which permission is missing. A bare
403 remains unknown. Rate-limit signals are distinct from permission rejection.
Expected missing branch/label GETs return 404; other 404s stop. Responses are
bounded to 2,000,001 bytes and malformed/oversized responses stop.

Only already authorized GETs retry, at most three attempts, with waits of 10
then 60 seconds. Valid Retry-After seconds or HTTP dates can increase the wait.
Each request and its retries share a 120-second monotonic deadline; later
cleanup/readback requests have their own budget. The absolute deadline is passed
into the actual HTTP transport, not merely checked after `response.read`.

The Linux single-threaded owner forks one disposable HTTP child per attempt.
Connection construction (including DNS/TLS), request, headers, body and connection
cleanup all happen there. The parent waits only until the remaining deadline;
at expiry or interruption it kills and reaps only its child. A
child-local kernel interval timer independently ends the child at the same
deadline even if the parent is paused or dies. No Python signal handler needs
to interrupt a blocking C call; the parent signal handlers remain unchanged.
Deadline enforcement is subject to OS scheduling, not a hard real-time promise.
After killing, the parent allows at most one additional second to verify reaping.
If termination cannot be verified, `transport_cleanup_unverified` latches on
that API instance and blocks subsequent HTTP attempts, including readbacks.

The parent reads its original signal mask before acquiring resources and enters
the restoration try before installing a temporary mask. Catchable signals remain
blocked continuously through fork, pidfd acquisition, observation, entry into
cleanup, bounded kill/reap and descriptor/mmap closure. There is no unblocked
transition into cleanup where another owner signal can escape. The original
mask is restored only after this region; original handlers then receive pending
signals. Handler definitions are never replaced.

While observing, the parent checks pending SIGINT/SIGTERM/SIGHUP between waits
of at most 50ms; the reap loop also checks them before each nonblocking wait.
A pending owner stop raises the normal stop synchronously while the mask still
protects cleanup. Signals already blocked by the caller are excluded from these
checks and retain their mask/pending state. No queued signal is consumed by the
adapter. Other catchable signals are deferred until the transport region exits;
this is deliberately limited to the existing single-threaded owner. Scheduling
and the bounded reap allowance still apply to stop latency.

Signalling uses the child's stable pidfd; it cannot target a recycled numeric
PID. Numeric signalling is used only if handle acquisition failed before any
wait/reap could release child ownership. A second wait reporting an already
reaped child preserves the original stop.

This adapter requires Linux fork/timer/pidfd support, a single Python thread and
the default SIGCHLD handler. Kernel pidfd availability is checked before forking.
Unsupported ownership context stops before forking;
there is no fallback to an unbounded request. The HTTP child runs no agent or
launcher. It changes no identity/permission, performs one request without retry,
and communicates through a capped anonymous memory mapping (about 4.1 MB).
There are no temporary response files, pipe-body reads, pickle messages or
inherited stdout flushes. Only fixed error categories cross the child boundary.
The existing per-socket timeout (at most 15 seconds) and outer service deadline
remain additional limits. Late responses are classified as deadline exhaustion
(or unknown mutation outcome) before diagnostics are emitted.

Mutations never retry. Lost transport, 5xx, malformed/oversized mutation results
are `unknown_outcome`; callers must reconcile by the existing readback before
considering any further mutation. Ending the local HTTP process cannot undo an
already accepted remote write. Diagnostics do not grant replay or infer write
permissions from a successful read. New terminal codes prevent the observer's
legacy retry loop from multiplying exhausted HTTP attempts.

Tests compile only the built API definitions and binding, never the launcher
entry point. Retry and classification fixtures use virtual clocks. Transport
regressions use real local child processes, real elapsed time and stdlib
HTTPResponse with an inert trickling stream; no GitHub or external socket is
contacted. They cover connection/request/header/body stalls, mutation ambiguity,
parent interruption, independent child expiry and verified reaping. Actual
owner SIGINT regressions cover both fork-return and post-reap transitions and
check that the original stop is preserved without a live untracked child or a
signal sent to a released numeric PID. R5 sends a second actual SIGINT at the
first cleanup line via a test trace, verifying live-child state after return.
It reproduces the same failure on the previous candidate without depending on
the number of private mask calls. The earlier independent mask-call-count
fixture and its RED evidence are preserved separately; they are not claimed
to pass unchanged after this redesign. Additional checks cover prompt stop for
all three owner signals, resource cleanup before original handler delivery,
and preservation of a caller-blocked pending signal. Existing
observer source/tests outside the two GH-4 test files remain unchanged.

The old independent slow-body reproduction used a virtual clock held in one
process. A fork copies that clock, so it cannot measure the repaired transport
from the parent. The new real-time test preserves the slow-body condition and
also checks earlier blocking stages. The two earlier sink reproductions retain
the same outcome/sequence assertions; their inert transport accepts the new
absolute-deadline keyword.

Targeted local tests and code review do not establish server integration,
installation readiness, trusted CI or release acceptance. Historical WORK-01
STOP, published history and consumed one-shot markers remain unchanged.

Transport design references: Python 3.10 [signal](https://docs.python.org/3.10/library/signal.html),
[http.client](https://docs.python.org/3.10/library/http.client.html) and
[mmap](https://docs.python.org/3.10/library/mmap.html). Fork inherits process
resources, so this adapter is intentionally restricted to the existing
single-threaded owner rather than being a general threaded HTTP library.
