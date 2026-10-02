# Domain identities — first implementation slice

References: GH32/GH33; AUTH-01/03 and SEC-01; TRK-01/03/07 from PR26
commit 85bb926f53028768400b67422cb60be1fb800cc1. Base code is main
2bf21950e0725bc9228b262e1495f5af5eeea1d6. This increment adds pure
Elixir value objects only. It does not activate any feature or complete
SN-004, SN-005 or SN-TRK-01; their integration prerequisites remain open.

## Tracker object identity

`SymphonyControl.Tracker.ObjectIdentity` has three explicit constructors:

- `native(installation_uuid, issue_uuid)`;
- `github(rest_database_issue_id)` for GitHub.com only;
- `linear(workspace_uuid, issue_uuid)`.

They return `{:ok, value}` or `{:error, :invalid_object_identity}`. UUID
text is normalized to lowercase; accepted GitHub IDs are positive Elixir
integers with no floating-point conversion. `key/1` returns a tagged tuple
of provider, namespace and object ID. These are typed keys, not an encoded
wire format, a database unique constraint or proof of an existing object.

GitHub input is the REST issue `id`, NOT `number` or GraphQL `node_id`.
A future adapter must select that exact field from an issue response and
exclude PR records. A repository ID is access scope, not part of this
instance-global database ID. Transfers/migrations that change an upstream
ID require explicit reconciliation; the constructor does not promise stable
upstream IDs across arbitrary provider operations or convert node IDs.

Linear workspace UUID is the object namespace; team and project IDs are
access/filter context, never alternate object identity. Native uses the
installation namespace. Local project IDs, credentials, binding generation,
display keys, URLs and filters are absent from all three value objects.
Thus they cannot split `key/1` for the same typed input, but exclusion of
concurrent execution owners still requires future transactional enforcement.

GH32 integration work remaining: a local TaskRef UUID bound to
(project_id, canonical object identity); stable UUID during rebind;
immutable per-run binding generation/snapshots; live scope reconciliation;
project ACL; and global active-claim exclusion independent of credentials
or generation. None of those constraints is claimed implemented here.

## Principal identity

`SymphonyControl.Auth.Principal` has `user/4`, `service/3` and `agent/3`.
All require exact issuer/subject and a local principal UUID; user additionally
requires a local user UUID. The other kinds cannot receive a user link through
these constructors. `key/1` is (kind, exact issuer, exact subject); local UUID
mapping does not alter that external key. Issuer path/case/trailing slash and
subject case/spacing are not silently canonicalized. UUID text is normalized.

The project accepts an HTTPS issuer URI without userinfo/query/fragment,
length at most 2048 bytes, and a nonempty printable ASCII subject of at most
255 bytes. URI components require well-formed percent escapes and path characters;
authority supports registered names and valid IPv6 literals, not IPvFuture/zone IDs.
The original encoded spelling is preserved. These are shape checks, not signature, discovery, issuer
allowlist, audience, expiry or nonce validation. Only constructor results
satisfy the opaque type; structs can be forged by code and are not authority.
No token, cookie, group, role, session or verified flag is stored. Inspect
redacts external/local identifiers; it does not protect deliberate field access.

A Principal is NOT an authenticated Actor. The next authentication slice must
verify issuer/subject, resolve local principal mapping and session freshness,
then obtain platform or resource-specific project permission server-side.
Runtime identity requires explicit `:runtime_identity_read`; a project role
alone is insufficient. Revocation/freshness <=60 seconds is required by the
existing specification, not implemented by these values. No changes were made
to RuntimeIdentity, controller/router, runtime config, Authentik or CI.

## Verification and integration

The added ExUnit files can run in fresh BEAM processes without Mix dependencies
or starting Symphony. They also live under normal `elixir/test` for a future
full Mix run. The first execution failed on missing modules; after implementing
them, 23 tests passed. Checks cover equality/namespace separation, integer
precision, input types/bounds, UUID normalization, exact issuer/sub semantics,
user versus service/agent distinction, redacted Inspect and fixed errors.

GH35 found missing percent-escape validation. On Elixir 1.19.6, the original
constructor accepted `%ZZ` and `%`; this was reproduced before changing code.
Three regressions were added (26 tests, two failures RED). Component grammar and
IPv6 literal validation now reject malformed escapes/authority/path while valid
encoded paths and IPv6 keep exact spelling: 26 tests, zero failures GREEN.

A planned private dependency-cache preparation plus full `mix test --cover`
invocation was rejected by the execution tool and did NOT run. It is not
replayed or delegated. Therefore repository-wide tests, configured coverage,
Dialyzer, packaged execution and protected verification are NOT_ATTESTED for
this increment. Source review is requested separately through the running
Symphony queue. No source acceptance is assumed in advance.

Next bounded steps: independent review of these five files; then TaskRef/binding
version types and server-side session/permission boundary, with tests and a new
review per changed commit. Do not treat these pure values as permission to
advance blocked CI, bypass integration dependencies or accept the product.

## Primary references checked 2026-10-02

- https://docs.github.com/en/rest/issues/issues — REST issue fields.
- https://linear.app/developers/graphql — model UUID versus shorthand identifier.
- https://openid.net/specs/openid-connect-core-1_0.html#IDToken — exact issuer/subject.
- https://openid.net/specs/openid-connect-core-1_0.html#ClaimStability — identity pair.
