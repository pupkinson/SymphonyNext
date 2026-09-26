# Agent entry point — Symphony Next

Read PROJECT_RULES.md first, then SPECIFICATION.md and the exact assigned task in planning/backlog.json. The only explicit operational exception is BOOT-P01: read bootstrap/PILOT.json and bootstrap/PILOT_TASK.md for that issue. It is not completion of SN-001 and does not bypass its blocker. Do not work from chat memory or an earlier specification.

Planning also requires planning/spec-index.json when present. Verify its source hashes and load its required additions and task refinement; baseline v0.5 alone is not the complete MCP scope. For SN-031 and affected dependencies, read planning/mcp-execution.json and its implementation plan. SN-031 is an aggregate, never a second executable job alongside its children. If the planning importer cannot represent the refinement, stop with unsupported_task_refinement; never silently drop the full-parity acceptance barrier. A planning source or draft branch does not grant scheduler admission or claim implementation.

For every run publish one ACCEPTED record with task, spec/policy versions, exact source base, branch/worktree and allowed delta before changing files. Find existing workpad/branch/PR first. Do not discard another attempt's unfinished work.

Roles are planner, implementer, independent read-only reviewer and release verifier. The bootstrap has one writer. Never start extra agents or promote generated subtasks without scheduler admission, except for the owner's standing reviewer authorization below. Use already approved skills only; SKILLS_POLICY.md controls provenance and trust.

## Standing owner authorization for independent PR review

On 2026-09-26 the owner authorized one independent read-only reviewer per subsequent pull request in `pupkinson/SymphonyNext`, including re-review after a HEAD change. This authorization remains effective until the owner revokes it and replaces scheduler admission only for the reviewer role. Record each review's exact HEAD; a changed HEAD requires a new review before its result can satisfy the review gate. The reviewer must be independent of the implementation and may only read source and evidence.

This authorization does not permit the reviewer to change code, launch additional agents, access secrets or production, publish trusted statuses, merge, or deploy. It grants no admission to planners, implementers, release verifiers, or generated subtasks. Existing trusted-check and release requirements remain in force. Record this owner authorization and the exact review scope in the run's ACCEPTED record.

Ordinary delegated releases in this new project are allowed after exact-SHA gates, through PR/merge and the normal Coolify webhook. The running DF Assistant, its repository, credentials and runtime are excluded.

The rejected server validator and owner-install command writes described in bootstrap/STATUS.json must not be replayed or delegated to evade the platform refusal. No readiness is claimed for this blocked operation. Continue only independent authorised work.

Report VERIFIED / INFERRED / UNKNOWN / BLOCKED explicitly. Final handoff contains test commands and actual exit codes, evidence hashes, exact head/tree/base, known effects, rollback state and the next bounded action. Do not call an unrun command PASS.
