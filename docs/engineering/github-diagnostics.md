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

401 is an authentication rejection; a known inaccessible-resource message proves
a permission rejection without identifying which permission is missing. A bare
403 remains unknown. Rate-limit signals are distinct from permission rejection.
Expected missing branch/label GETs return 404; other 404s stop. Responses are
bounded to 2,000,001 bytes and malformed/oversized responses stop.

Only already authorized GETs retry, at most three attempts, with waits of 10
then 60 seconds. Valid Retry-After seconds or HTTP dates can increase the wait.
Each request and its retries share a 120-second monotonic deadline; later
cleanup/readback requests have their own budget. Transport timeout is capped
by remaining time. Socket timeout bounds
individual blocking operations, not a hard process watchdog. A late result is
rejected. The existing outer service deadline remains unchanged. New terminal
codes prevent the observer's legacy transport retry loop multiplying attempts.

Mutations never retry. Lost transport, 5xx, malformed/oversized mutation results
are `unknown_outcome`; callers must reconcile by the existing readback before
considering any further mutation. Diagnostics do not themselves grant replay
or infer successful mutation from a read permission check.

Tests use inert transports and virtual clocks. Integration compiles only the
built API definitions and binding; it never executes the launcher entry point.
The previous observer tests and assertions are preserved. Production access,
independent review and runtime acceptance are outside this candidate's evidence.
