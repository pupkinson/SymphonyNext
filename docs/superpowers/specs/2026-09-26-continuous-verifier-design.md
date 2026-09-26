# Continuous trusted verification, first increment

Owner approved implementation on 2026-09-26 and selected ChatGPT authentication
for the independent reviewer. Scope is pupkinson/SymphonyNext only; no merge,
deployment, Actions, existing worker restart, or DF Assistant access.

ACCEPTED: spec v0.5 + existing composition, policy symphony-next-policy/v1,
base 2bf21950e0725bc9228b262e1495f5af5eeea1d6, base tree
f228f3a5743317138de89a849cbbe13dee092835. Isolated source overlay:
ci_service_candidate; branch feat/continuous-trusted-verifier. Allowed delta:
ci/continuous/** and this design/implementation plan. One author and one
read-only reviewer; implementation native in this session. No activation.

## Architecture

A root-owned, fixed Python controller runs from a systemd timer every 120 seconds.
It polls complete GitHub PR pages using the existing repository-scoped GitHub App
5069157. A root-owned SQLite journal and flock serialize attempts. Queue identity
is repository + PR + HEAD + base + installed policy digest. Fresh work is limited
to non-draft same-repository PRs into main; a draft requires label snv:verify.
At most one attempt per timer tick, four new attempts per UTC day, maximum
45 minutes each. Paused/disabled service does not claim new work.

The controller obtains trees and blobs through the GitHub API, checks their
Git hashes, rejects symlinks/submodules/unsafe paths and oversized input, and
materializes only verified regular files. One existing inert 30 MB demo video
is omitted with exact path/mode/size/Git blob metadata pinned in installed code;
its change/deletion holds both profile preparation and PR attempts. This omission
is disclosed in evidence and reviewer input. No repository program runs on the host.

Codex 0.155.1 runs as a separate service identity, using its own ChatGPT login.
thread/start and turn/start explicitly set environments=[]; shell, apps, MCP,
plugins, browser, computer use and multi-agent capabilities are disabled. Its
only dynamic tool is read_source(path, revision), served from already verified
head/base bytes. The controller rejects all other server requests and forbidden
tool events. Codex 0.155.1 still advertises skills and request_user_input;
all bundled skills are disabled. Native acceptance verifies an empty catalog and
rejects arbitrary package reads; no execution tools are advertised. Every changed file must be read before READY is accepted. A fresh
thread returns a schema-bound exact-HEAD verdict; no implementation history or
author-supplied approval is trusted. Authentication credentials are consumed by
the Codex harness, never included in model-visible source or tool output.

Test code executes as UID 10001 with zero effective capabilities in a disposable
no-network, read-only-root Docker container with CPU/memory/PID/time limits, private tmpfs, no Docker socket and
no credentials. A reviewed dependency image is pinned by immutable image ID.
The installed root supervisor has only CHOWN/SETUID/SETGID/KILL capabilities to
prepare disposable files, drop child identity, and terminate child processes.
Candidate processes cannot signal it or rewrite its root-owned logs; a native
assertion checks this before every run. No candidate code runs as root.
The installed worker supplies explicit stage commands, a fresh Unix-socket-only
PostgreSQL fixture and cleanup. Quality profiles pin test configuration and lock
files outside the candidate; changing them requires an explicit policy update.
Protected CI/policy changes require a root-owned exact-target exception and do
not update the running verifier. Existing acceptance tests cannot be removed or
modified under the normal profile. New tests are allowed. Profile migrations
are exceptional bootstrap work, not per-PR installation.

After READY and all successful stages, fresh PR HEAD/base/policy checks precede
publication. Durable publish_intent is committed before POST. Any unknown POST
outcome enters reconciliation-only state; all check pages are read and exactly
one matching app/name/HEAD/external_id/body is required. Zero or multiple matches
never cause another POST. A changed HEAD/base invalidates the attempt. Success
is recorded only after authoritative check readback. Controller crashes before
publication hold the attempt, stop its owned container, and never silently
relaunch a model or test. A new HEAD creates a new independent attempt.

## Trust and initial deployment

Existing one-shot PR13 controller remains untouched. This service cannot certify
or install its own revision. Package installation is owner-operated, creates a
new identity and unit, and leaves enabled=false and the timer disabled. A
separate owner activation requires pinned dependency image, authenticated Codex,
fresh protected policy, offline tests and native sandbox/negative-path evidence.
The narrow App may omit bypass actors: pin a full owner-observed ruleset snapshot
and compare its updated_at/projection on every attempt; a change holds the queue.
No privilege or API-scope expansion is silently performed.

## Acceptance

Tests must cover malicious paths and blob substitution, stale HEAD/base, profile
or locked-suite weakening, duplicate workers, daily budget, crash recovery,
unknown POST and paginated reconciliation, reviewer tool escape/forged verdict,
missing file coverage, stage failure/timeouts and cleanup. Native acceptance
must additionally prove no environment tools exposed, model login, Docker
isolation, real PostgreSQL stages and GitHub publication/readback. Mock tests do
not satisfy native acceptance. Product SN-003/SN-030 completion is not claimed.
