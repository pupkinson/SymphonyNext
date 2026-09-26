# Continuous verifier implementation plan

> Native execution in this session; one independent whole-branch reviewer.

Goal: implement repeatable, repository-scoped review → tests → trusted check.
Architecture and constraints: see ../specs/2026-09-26-continuous-verifier-design.md.
Stack: Python 3 stdlib, Codex app-server 0.155.1, Docker, systemd, SQLite.

1. Write RED tests for source/policy validation and durable publication journal.
   Implement ci/continuous/{common,source,state,github}.py; verify with unittest.
2. Write RED tests for restricted reviewer RPC and verdict source coverage.
   Implement reviewer.py with environments=[] and read_source only.
3. Write RED tests for orchestrator crash/stale/reconciliation behavior and
   container command constraints. Implement controller.py, worker.py and units.
4. Add owner-operated installation/preflight/profile preparation tools and usage.
   Run full suite, compileall and shell/systemd static checks. Package a stopped
   installation; never infer native checks from mocks.
5. Publish isolated branch/PR, independent exact-HEAD review, bounded fixes.
   Produce concrete owner handoff; activation remains separate.

Review focus: unknown POST vs retry, base changes with same HEAD, reviewer tool
availability drift, disk-full cleanup, changed acceptance-policy self-approval.

Ledger: initial plan recorded. Two repair cycles maximum after first full
candidate; no model call, root/Docker mutation or production action admitted here.
