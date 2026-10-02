# SessionAccess: server-side read authorization decision

Implementation follows AUTH-01/03/04/06/07 and the GH33 contract. Parent PR34
(6fbef09) supplies Principal values; the existing RuntimeIdentity/configuration
is not modified. This is executable decision logic, not a deployed SSO login.

`SessionAccess.authorize(principal, session, permissions, action, now_ms)` returns
only :ok or {:error, :forbidden}. It supports browser user principals, explicit
platform runtime_identity_read, and project task_read. Unknown actions, other
principal kinds and malformed data fail closed. Project roles cannot imply
platform permission; platform access does not imply project membership.

ALL inputs must come from the trusted server authentication/authorization boundary,
not request JSON, query parameters or a cookie. Principal construction validates
shape, not OIDC signature or identity. A malicious caller who can fabricate the
server snapshots is outside this function's trust boundary. No public endpoint
exposes these arguments and no fixture authorizer is installed.

Session snapshot fields: principal_id, user_id, exact issuer/subject, state,
checked_at_ms and expires_at_ms. Permission snapshot fields: principal_id, state,
checked_at_ms, expires_at_ms and grants. Only state=:active is accepted. Grants
are {:platform, :runtime_identity_read} or {:project, canonical_project_uuid,
:task_read}. The action's project UUID must be resolved server-side from the
resource, never accepted as proof that a caller owns the resource. Unrelated
role/group/superuser fields are ignored and do not grant anything.

Each snapshot is checked INDEPENDENTLY: checked_at <= now; age <60000ms; now <
expires_at. At exactly 60000ms or expiry the decision denies. This is a strict
60-second freshness bound, including permission revocation, only when the input
source genuinely satisfies the contract. These are integer MONOTONIC milliseconds
from one server clock domain; negative values are valid. The OIDC/session adapter
must map external expiry to that domain and stamp the verified source's freshness,
not the time it read an old cache. Cache fallback after known lookup failure or
revocation is prohibited. After VM/clock epoch restart, discard old snapshots and
revalidate; persisted wall timestamps must never be mixed with monotonic ones.

The following remain separate work: OIDC verification, local principal/session
store, source lookup timeouts, genuine revocation propagation, logout/back-channel
signals, server resource resolution, HTTP/LiveView enforcement and test fixtures
against installed Authentik. A pure decision over forged, replayed or incorrectly
timestamped input does not enforce those obligations by itself. Current default
deny and running services are unchanged; no endpoint is made public by this code.

Verification: 15 new ExUnit cases plus 26 parent cases in a fresh BEAM process.
Missing implementation first failed; positive/negative permissions, cross-project
isolation, mismatched identity, revoked/unavailable/expired/stale/future snapshots,
clock boundaries and all missing fields are now covered. No dependency cache,
full Mix suite, database, provider or runtime operation was launched. This domain
subset is not full CI/coverage/Dialyzer or live SSO acceptance.
