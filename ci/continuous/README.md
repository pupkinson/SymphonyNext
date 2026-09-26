# Continuous trusted PR verification

First implementation for `pupkinson/SymphonyNext`: independent Codex review,
isolated Elixir quality stages, then GitHub App check
`symphony-next/verified-tests`. No GitHub Actions, merge or deploy calls.
The source PR does **not** install, activate, or certify itself.

## Behaviour

A disabled-by-default systemd timer polls every two minutes. One controller,
one reviewer and one worker at a time; maximum four new attempts per UTC day.
Only same-repository open PRs into `main` qualify. Drafts require `snv:verify`.
Every attempt binds exact PR/HEAD/base/policy. New HEAD creates a new attempt.
A held attempt is never silently replayed. Evidence lives under the private
`/var/lib/symphony-next-ci/attempts/<attempt-key>` directory. The trusted check
contains the evidence digest, not raw source, model output or credentials.

The reviewer uses a **dedicated ChatGPT login**, not an OpenAI API key.
The pinned native Codex binary has no execution environment; its dynamic tool
reads verified source only. All changed file versions must be read. Native
Codex still advertises `skills.list`, `skills.read`, `request_user_input`:
all built-in skills are disabled and their catalog is tested empty. Arbitrary
skill-package reads are denied. Other app-server requests stop the attempt.
A separate service identity, empty working directory and fresh ephemeral
thread exclude author history and GitHub credentials. Model review remains
probabilistic; a READY verdict is not a proof that arbitrary code is safe.

The installed worker supervisor runs as container root with only
CHOWN/SETUID/SETGID/KILL. Candidate commands run as UID 10001 with **zero**
effective capabilities, checked before every run. They cannot signal the
supervisor or replace its root-owned logs. The container has no network,
credentials or Docker socket, a read-only root, private tmpfs, CPU/RAM/PID limits
and a pinned image. PostgreSQL is disposable and listens on a Unix socket only.
Stages: build, format, lint, test coverage, Dialyzer. Success requires every
numeric exit code, source hashes before/after, test-count floor, skip ceiling,
100% **configured** coverage, zero Dialyzer errors, and PostgreSQL cleanup.
Configured coverage excludes modules listed in the pinned mix.exs; this does
not claim full repository coverage or packaged/live-provider E2E acceptance.

The pre-existing `.github/media/symphony-demo.mp4` is omitted from source
materialization and review input, with its path/mode/size/Git blob hash pinned
in installed code (`32b1f857f45eb901905ea24355b599fb417f53c5`, 30,446,771 bytes).
Both head and base must contain that exact inert asset; change/deletion holds.
All other size limits stay enforced. Evidence and the reviewer prompt disclose
this omission; this is not a claim that video content was read or tested.

Quality profiles pin existing tests, config, Mix tasks and dependency locks.
New tests are allowed; newly introduced quality-control configuration or Mix
tasks are rejected, including previously absent Credo files. Changes to pinned
files need an owner-reviewed profile
migration. CI, policies, AGENTS and bootstrap changes also require an exact
owner exception. This intentionally does not auto-approve policy changes.

Before publication, HEAD/base, policy and ruleset revision are checked again.
A durable journal entry precedes the single POST. Lost responses cause only
read-only paginated reconciliation, never another POST. A stale HEAD cannot
receive a successful attempt on the new HEAD. A race after POST may leave a
historical check on the old commit; it is never carried forward.

## Current evidence and remaining gates

Local: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s ci/continuous/tests -v`
passes 44 tests with one native UID-capability test skipped because this workspace
lacks SETUID/SETGID capabilities. Python compilation passes.
On server 1c-db, the pinned Codex 0.155.1 native executable passed five offline
fixture scenarios: final response, permitted source, denied outside source,
empty skills catalog, denied private fixture file. No real model request or
existing credentials were used. Binary SHA256:
`0753dfe1d8b87a52436deb13eb1c549661ef4c84fee2c5aa688385eebeccb761`.

**Not yet run:** owner installation, ChatGPT login, dependency-image build,
real PostgreSQL/Elixir worker acceptance, live model review and new trusted
check publication/readback. Installation readiness is not runtime acceptance.
`prepare` performs the native worker/isolation checks and remains disabled.
`activate` requires recent successful preparation and login. First live PR
verification must still succeed after activation. SN-003/SN-030 completion,
SN-015 scheduler implementation and production readiness are not claimed.

## Owner installation (new service only)

Review and independently approve this source revision first. Use a clean,
owner-controlled checkout of that **exact commit** on 1c-db. The commands below
are for the existing owner administrative session; the agent does not obtain
root/Docker access. They never restart or reuse the consumed PR13 verifier.

```sh
python3 -I ci/continuous/owner.py install --reviewed-head EXACT_REVIEWED_COMMIT
```

`EXACT_REVIEWED_COMMIT` is the final independently reviewed commit from this PR;
the installer checks it against `git rev-parse HEAD` and refuses a dirty checkout
or existing installation. It creates only `/opt/symphony-next-ci`,
`/etc/symphony-next-ci`, `/var/lib/symphony-next-ci`, the dedicated reviewer home
and the two new units. Existing private App config/key are validated in place,
never copied to the reviewer or worker. Units remain stopped and disabled.

Complete ChatGPT device login yourself (do not send tokens or auth.json):

```sh
runuser -u snci-review -- env -i PATH=/usr/bin:/bin HOME=/var/lib/symphony-next-ci-review CODEX_HOME=/var/lib/symphony-next-ci-review /usr/lib/node_modules/@openai/codex/node_modules/@openai/codex-linux-x64/vendor/x86_64-unknown-linux-musl/bin/codex login --device-auth
python3 -I /opt/symphony-next-ci/owner.py prepare main
python3 -I /opt/symphony-next-ci/owner.py prepare sn004
```

`main` is pinned to `2bf21950e0725bc9228b262e1495f5af5eeea1d6` (305-test floor).
`sn004` is pinned to `2a779abecaf9dce57b3a9e06435a9ece04a80b3b` (328-test floor).
Each prepares a new reviewed dependency image, validates a full worker run and
writes private acceptance evidence. Image build has network for package fetches;
PR execution never has network. A failed setup directory is retained for owner
inspection, never automatically removed/replayed. No installed policy is
weakened to make a failing profile pass.

Inspect the acceptance JSON and logs. Within 24 hours, activation is a separate
owner action:

```sh
python3 -I /opt/symphony-next-ci/owner.py activate
systemctl status symphony-next-ci.timer
journalctl -u symphony-next-ci.service --no-pager -n 30
```

A missing login, changed Codex binary, App scope mismatch, ruleset change,
profile mismatch or failed native evidence stops activation/work. Model rate
limits and authentication expiry hold that attempt; owner investigation is
required, no automatic repeated model spending. Four attempts is a count cap,
not a monetary or token guarantee.

## Stop and rollback

```sh
systemctl disable --now symphony-next-ci.timer
systemctl stop symphony-next-ci.service
```

Preserve the journal and evidence. A controller interrupted by system shutdown
cleans its deterministic owned container on the next tick, even while policy is
disabled. For an immediate permanent stop, owner checks/removes only containers
named `snci-<journal-key>` with the matching `snci.attempt` label. Do not delete
state to retry an unknown GitHub POST. Do not reuse PR13 state or alter branch
rules to bypass a hold. No application deployment needs rollback: this increment
does not deploy SymphonyNext or touch DF Assistant.
