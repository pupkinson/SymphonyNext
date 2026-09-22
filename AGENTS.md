# Agent entry point — Symphony Next

Read PROJECT_RULES.md first, then SPECIFICATION.md and the exact assigned task in planning/backlog.json. The only explicit operational exception is BOOT-P01: read bootstrap/PILOT.json and bootstrap/PILOT_TASK.md for that issue. It is not completion of SN-001 and does not bypass its blocker. Do not work from chat memory or an earlier specification.

For every run publish one ACCEPTED record with task, spec/policy versions, exact source base, branch/worktree and allowed delta before changing files. Find existing workpad/branch/PR first. Do not discard another attempt's unfinished work.

Roles are planner, implementer, independent read-only reviewer and release verifier. The bootstrap has one writer. Never start extra agents or promote generated subtasks without scheduler admission. Use already approved skills only; SKILLS_POLICY.md controls provenance and trust.

Ordinary delegated releases in this new project are allowed after exact-SHA gates, through PR/merge and the normal Coolify webhook. The running DF Assistant, its repository, credentials and runtime are excluded.

The rejected server validator and owner-install command writes described in bootstrap/STATUS.json must not be replayed or delegated to evade the platform refusal. No readiness is claimed for this blocked operation. Continue only independent authorised work.

Report VERIFIED / INFERRED / UNKNOWN / BLOCKED explicitly. Final handoff contains test commands and actual exit codes, evidence hashes, exact head/tree/base, known effects, rollback state and the next bounded action. Do not call an unrun command PASS.
