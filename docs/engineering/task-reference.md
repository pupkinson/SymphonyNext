# TaskRef: stable reference and versioned attachment

Implementation follows GH32 and TRK-03/08/10 from PR26 (85bb926).
Parent implementation is PR34 (6fbef09). Neither prerequisite PR is merged;
this branch is an independently reviewed increment, not milestone acceptance.

`TaskRef.new(id, project_id, object_identity, binding_id, generation)` validates
UUIDs, source identity and a positive integer generation. The caller supplies
UUIDs allocated by the future registry. A reference has no credentials, display
key, URL, approval or execution-success field.

`key/1` = (local project UUID, credential-independent source identity). The registry
must enforce one TaskRef per key and must not reuse an existing UUID for another
object. `ownership_key/1` omits local project, binding and generation: the future
transactional claim store must use this key to exclude duplicate active execution
across overlapping bindings/projects. Returning a key does NOT implement a lock.

`rebind(ref, expected_generation, binding_id, next_generation)` returns a candidate
reference preserving id, project and object. It rejects an unexpected version
or non-increasing epoch with conflict; malformed values return invalid_task_ref.
Generation is a project-wide attachment epoch, not a counter reset when a binding
is replaced. The caller must allocate it from authoritative state. An old value
is immutable in memory. `snapshot/1` returns only its exact reference pin, not task
content or a tamper-proof persistent record. `current?/2` rejects stale/foreign
pins and unknown fields. No command is executed by these functions.

Storage integration remains required: pause/drain, resolve unknown writes, scope
and ACL checks, atomic expected-version update, immutable stored run snapshots,
unique registry and global active claim. Calling rebind on a stale in-memory
value cannot detect that the database changed; compare-and-swap must occur in
the same storage transaction as publication. A duplicate call on the original
value is a pure deterministic calculation, not a second external mutation.
Changing provider object requires a NEW reference plus explicit provenance
mapping; rebind deliberately has no argument for replacing object/project/id.

Validation of ObjectIdentity checks shape by its existing provider constructors;
it does not attest the existence, provider scope or permissions of the source.
Getters accept the opaque constructor-produced type. Neither structs nor pins
are authentication/authorization capabilities. Inspect hides local/source IDs.

Verification: 14 new ExUnit tests plus 26 parent tests in a fresh BEAM process.
Tests first failed on missing module; implementation passes. No database,
HTTP router, IdP, tracker credentials, running queue or protected CI is changed.
The suite is the domain subset only, not repository-wide Mix/coverage/Dialyzer
or deployment acceptance. Earlier refused cache/full-suite operations are not
replayed. Registry persistence/atomic concurrency/real cutover remain untested.
