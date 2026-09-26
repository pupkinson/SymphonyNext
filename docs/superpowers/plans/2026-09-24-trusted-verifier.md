# PR #11 Trusted Verifier Implementation Plan

> For agentic workers: implement natively in this session using executing-plans; obtain an independent read-only review after the complete candidate. Owner explicitly requested the package and owner instructions.

**Goal:** Deliver a checked, owner-installable verifier for the exact PR #11 commit.
**Architecture:** Fixed owner CLI, transient isolated systemd test worker, separate GitHub App publication.
**Tech Stack:** Python 3.10 stdlib, systemd 249, Git, curl, OpenSSL, pinned binary wheels.
**Spec:** docs/superpowers/specs/2026-09-24-trusted-verifier.md

## Global constraints
No edits to reviewed PR #11; branch from c3c8bce. No model/WORK-01/Actions/merge/deploy. Never publish trusted status with writer credentials. No server writes by the preparing agent.

## Review focus
- Attempt reuse or crash before/after publication: durable intent prevents rerun or duplicate POST.
- Invalid test reports: wrong SHA, missing/duplicate IDs, skips/errors cannot pass.
- Root trust boundary: writable/symlinked config or package cannot run.
- Unknown network mutation: preserve intent and require readback, never blind retry.
- systemd isolation differs from mocks: native acceptance remains pending until owner execution.

## Task 1: Locked acceptance and worker
Files: bootstrap/trusted_verifier/contract.py, worker.py, target.json, tests/test_contract.py, tests/test_worker.py.
- [x] Run contract/worker tests RED before implementation.
- [x] Implement strict report and source manifest validation; actual unittest execution with full test IDs and an explicit no-skip requirement.
- [x] Run tests GREEN; retain commands and actual exits.

## Task 2: Operator/controller and GitHub integration
Files: bootstrap/trusted_verifier/verifier.py, github_api.py, askpass.py, tests/test_verifier.py, tests/test_github_api.py.
- [x] Test path trust, attempt locking, no repeated publication and API readback RED.
- [x] Implement bounded fixed-purpose install/configure/run/status commands and credential-isolated transport.
- [x] Test worker command arguments and process failure handling with boundary doubles; label native integration NOT_RUN.

## Task 3: Dependencies and handoff
Files: bootstrap/trusted_verifier/requirements.lock, README.md, package manifest; documentation paths in this plan.
- [x] Pin wheel hashes from authoritative release metadata; avoid sdists.
- [x] Document exact GitHub App and owner steps, expected outputs, preservation and rollback limitations.
- [x] Verify diff/scope, compile and applicable project tests; report known missing-jsonschema baseline separately.
- [ ] Obtain follow-up independent review after R1 corrections and publish draft PR with exact SHA and limitations.

R1 found worker traversal permissions under umask 077 and PrivateTmp/tmpfs precedence defects. Added regression tests, observed RED, corrected both and observed 27 package tests GREEN. Native systemd and GitHub execution remain NOT_RUN.
