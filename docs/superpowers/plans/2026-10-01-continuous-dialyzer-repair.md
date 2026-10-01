# Bounded worker diagnostics and Dialyzer preparation repair

ACCEPTED: one additional owner-authorized CI setup repair cycle, starting at
`8fd4edc25a4e3ddd5b690a4e269919cc88c73760`, on
`fix/continuous-dialyzer-preparation`. This authorization overrides the two-cycle
repair budget for this cycle only. It permits one independent read-only reviewer
at the exact new HEAD, and at most one native quality attempt for each locked
profile, main followed by sn004. The timer remains disabled. No trusted status,
merge, deploy, production access or additional agents are included.

Rules/specification baseline: v0.5 and the accepted composition in spec-index.
This bounded CI repair does not admit or complete SN-003, SN-030 or SN-015.

## Evidence and target

The previous main worker passed isolation, PostgreSQL setup, dependencies, build,
format, lint and coverage (305 tests, zero failures, six skips, 100.00%). It
emitted no result. Dialyzer's exit/timeout is unknown: the supervisor loses stage
output and exception classification when wait raises. Reproduce that defect
with real child processes before changing production code.

Preserve bounded output and emit a closed diagnostic without exception text.
Keep all quality thresholds, capabilities, resource limits and deadlines.
Inspect the immutable dependency image's project PLT without starting a
container. Reuse a verified warm image; only a missing PLT warrants a dependency
rebuild with `mix dialyzer --plt`. Full isolated Dialyzer analysis remains required.

## Allowed delta

- Worker and runner diagnostics; Dependency.Dockerfile PLT preparation.
- A single-use owner repair helper and focused regression tests.
- CI README and this plan.

Locked profile definitions, source trees, application code, scheduler,
controller, credentials and branch rules stay outside this delta.

## Execution and verification

1. Verify fresh source identity, project composition and disabled runtime.
2. RED: reproduce timeout/nonzero/spawn failures and lost output with real
   processes; verify closed runner diagnostics fail closed.
3. GREEN: implement bounded diagnostics and preserve original stage failure
   through PostgreSQL cleanup.
4. RED/GREEN: test PLT tar inspection, exact failure evidence, source-preserving
   package replacement, replay refusal and one attempt per profile.
5. Run the complete CI Python suite and compilation checks. Native Docker and
   Elixir acceptance remain owner-only, unrun during source development.
6. Publish a separate draft PR based on the exact accepted base; verify every
   changed blob and obtain one independent read-only exact-HEAD conclusion.
7. Stage the byte-identical reviewed helper for an owner hash-pinned command.
   Archive failed source/logs, installation, policy and status before replacement.
   Refuse drift/replay/active units. Main failure stops before sn004.

No automatic rollback after a partially consumed attempt. Backups and receipts
remain preserved; any further repair requires a new bounded owner decision.
