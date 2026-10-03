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
reads verified source through direct JSON `snci_source.read_source` only. All
changed file versions must be read. `agents.enabled=false` and both multi-agent
features disable model-forced agent tools. The code-mode host stays disabled.
Codex 0.155.1's bundled gpt-6-astra catalog forces code_mode_only despite the
code_mode feature flag. A dedicated direct_only_tool_namespaces entry keeps
source available directly and excludes it from the nested JavaScript surface.
The model still sees inert exec/wait entrypoints, whose host-disabled refusal
is tested. Request-user-input callbacks are denied by the client guard.
With a direct-tool catalog, built-in skills remain advertised: their catalog
is tested empty and arbitrary packages unavailable. Other requests/events stop
the attempt. No model or native binary upgrade is part of this transport fix.
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

The original controller baseline ran 44 tests with one native UID-capability
test skipped in a workspace lacking SETUID/SETGID capabilities. Subsequent
repairs add their own regression fixtures. Run the complete suite for each
reviewed revision:
`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s ci/continuous/tests -v`.
The original five offline scenarios used an unknown fixture model and did not
exercise model-forced wrappers. After a live gpt-6-astra review held with zero
source reads, the same server binary reproduced `code-mode host is disabled`.
The corrected nine offline scenarios cover both direct and bundled gpt-6-astra
catalogs, both wire inventory layouts, complete head/base reads, unread-READY
refusal, outside-path refusal, empty/unavailable skills and disabled code-mode
execution. Both catalogs read two source versions; no collaboration or shell
tool is advertised and no private canary reaches model input. These are fake
localhost provider tests with fresh unauthenticated homes, not live reviews.
Native exit0/log SHA256:
`64d021089635b3453eb756ae7ccea342f64a15524f48acf331d0badd62fa27c4`.
Binary SHA256:
`0753dfe1d8b87a52436deb13eb1c549661ef4c84fee2c5aa688385eebeccb761`.
Source tests: 182 tests, 181 passed, one existing native isolation skip, exit0.
The installed package remains 38ead317 and stopped; this source change neither
installs itself nor replays the immutable held attempt. A separately reviewed
owner transition and subsequent trusted exact-HEAD check remain required.

**Runtime gates:** protected owner installation/login/preparation, real
PostgreSQL/Elixir worker acceptance, live model review and trusted check
publication/readback. Source readiness does not establish runtime acceptance.
`prepare` performs the native worker/isolation checks and remains disabled.
`activate` requires recent successful preparation and login. First live PR
verification must still succeed after activation. SN-003/SN-030 completion,
SN-015 scheduler implementation and production readiness are not claimed.

## Owner maintenance after the zero-read review hold

`snci/repair_review.py` is single-use for the exact activated-policy digest,
installed38ead317 package and saved PR14 review-only hold. Its source base is
the independently accepted direct-source PR53 commit0d0f619. The owner reviews
this separate maintenance candidate before executing it from a clean,
root-owned exact-HEAD checkout in the existing root tmux session on1c-db.
The agent obtains no root/Docker scope and does not write protected server paths.

The helper requires inactive/dead service and disabled/inactive timer, no live
worker or pending attempt, exact installed/source bytes and manifests, bounded
Git ancestry/package delta, current sole eligible PR14/head/base, unchanged
rules/native binary and both fresh successful preparation receipts/images.
It verifies the exact saved zero-read HOLD and retains every journal row,
receipt byte and timestamp. One staged offline native probe runs as existing
snci-review in fresh unauthenticated homes. This probe spends no model tokens.

Before replacement it archives the private old policy and entire old package,
records a durable intent and rechecks all inputs/staged bytes. It changes only
installed_revision in the already-enabled policy: enabled=true is preserved
while timer/service remain stopped. A byte-bound completion/readback is required.
Terminal marker: `REVIEW_TRANSPORT_INSTALLED_PAUSED <reviewed-head>`.
No old installer/refresh, image build/reprepare, model/profile switch, journal
reset, automatic rollback, timer enablement, check publication or service start
occurs in this helper. Failure/interruption after claim requires reconciliation;
preserve the claim, partial stage and backups rather than invoking it again.

After successful installation, the owner may start only
`symphony-next-ci.service` **once**, leaving the timer disabled. This starts one
real paid source review and isolated PR14 quality run; it may take many minutes.
The changed verifier revision produces a new immutable policy tuple under the
unchanged global daily_attempts<=4; the old hold remains immutable. No automatic
additional attempt/model spending follows a failed or unknown result. Read the
sanitized controller result, saved evidence and exact protected GitHub check/App
identity before enabling polling or considering merge. Unit success alone is
insufficient. Protected installation and corrective live CI are not claimed by
source tests. Preserve old package/policy for owner reconciliation; rollback
does not remove consumed attempts or magically revalidate old policy readiness.

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

## Repair of the local seed reference

Owner preparation on 1c-db reached Docker build but failed before any RUN stage:
BuildKit interpreted the bare `sha256:a93a…` image ID in FROM as a Docker Hub
repository reference. The seed now receives an owner-controlled local tag
`localhost/symphony-next-ci-seed:<full-image-id>`. Setup requires the default
Docker driver, verifies the immutable seed ID before/after tagging and after
build, uses `--pull=false`, and checks that the resulting image retains the
exact seed filesystem layers. An existing tag pointing elsewhere holds setup.
An absent seed holds setup; it is never pulled or replaced automatically.

`snci/repair_seed.py` is a single owner operation for the observed failure on
installed revision `8794bfd42e29580c00978015a46969c7642f56dc`. Use the supplied
hash-pinned command only after independent review of the repair commit.
It requires disabled/inactive units, no preparation process, an unchanged
installation/policy with no accepted profiles, complete unchanged main source,
and the exact pre-RUN metadata-resolution failure. The GitHub App validates
the incoming commit and its complete source delta against that base; only the
five repair files are allowed. The source SHA, not a branch name, is recorded.

The operation keeps the original source-only archive, archives the failed
build under `/var/lib/symphony-next-ci/repair-local-seed-<head>/failed-build`,
and keeps the prior package at `/opt/symphony-next-ci-before-seed-<head>`.
The old private policy is retained in `policy-before.json`. Installation
revision is the only changed policy field. App keys, reviewer login, units,
locked profile definitions and the CI attempt journal are retained.
No merge, deployment, trusted check or timer activation is performed.
Interrupted/failed repair is held for owner inspection; it is not replayed.

A private tmux driver prepares main and sn004 once. Its private `prepare.log`
retains exceptions. Root-owned `/opt/symphony-next-ci/preparation-status.json`
contains a closed projection: phase, revision, PID/time and successful native
test counts, skips, configured coverage and Dialyzer counts. It contains no
source, exception messages, credentials or log contents. `hold` is a failure;
`all_profiles_prepared_disabled` requires both successful profile receipts and
a disabled policy. A stale preparing status with a missing PID is UNKNOWN.
This file is preparation telemetry, not the GitHub required trusted check.

The repair's local regression and package checks are source evidence. The
first actual build using the local tag, PostgreSQL/Elixir acceptance, and live
review/check publication remain owner/runtime gates. Activation remains a
separate owner action after successful recent acceptance.

Docker reference: [image tagging](https://docs.docker.com/reference/cli/docker/image/tag/),
[Docker driver](https://docs.docker.com/build/builders/drivers/docker/).

## Owner repair of capability spelling

The container inspector previously compared four allowed capability names with
the bare spellings. Docker can report those same rights with `CAP_` prefixes.
The comparison now accepts either exact spelling, in any order, while requiring
exactly CHOWN, KILL, SETGID and SETUID. Missing, repeated, extra, nested-prefix,
lowercase or malformed entries remain a hold. All other isolation checks,
resource limits, mounts, worker identity and locked quality profiles are retained.

`snci/repair_caps.py` is the second bounded native setup code repair, based on
reviewed revision `151fc2eb53189bca42b0775e26a231fb837e7899`. It requires the
unchanged disabled installation, stopped processes, no accepted profiles and
the protected diagnostic evidence identifying only the capability spelling
difference. The exact five-file incoming source delta and bounded commit
ancestry are checked. A complete unchanged 180-file main source, successful
seed-image provenance and the initial inspection failure must be preserved;
worker logs or acceptance evidence refuse this repair.

The owner operation preserves the failed main preparation, previous package,
private policy, public status and attempt journal. Installation revision is the
only immediate policy change. A private one-time tmux driver materializes a new
main source from verified cached blobs and reuses the immutable already built
image, with a fresh seed identity/layer check, rules check and offline reviewer
probe. It then executes the full locked worker suite once. There is no main
dependency rebuild, quality reduction, credential replacement or retry of the
consumed one-shot verifier.

Only successful fresh main acceptance updates its profile. The driver then
prepares sn004 once using the normal owner procedure. Both profiles must succeed
while policy remains disabled before metadata reports
`all_profiles_prepared_disabled`. Raw diagnostics, source, logs and exception
messages stay private; the existing closed metadata projection is retained.

Partial writes, launch uncertainty or another native failure preserve their
claim/evidence and require inspection; this operation cannot be replayed.
This repair does not enable the timer, publish a trusted check, merge or deploy.
Native repaired acceptance and live check publication remain separate gates.

## Additional bounded repair: worker diagnostics and PLT preparation

The owner authorized one additional setup repair beyond the original two-cycle
budget. It starts from `8fd4edc25a4e3ddd5b690a4e269919cc88c73760` and permits
one native main attempt followed, only on success, by one sn004 attempt. The
previous worker passed stages through coverage; Dialyzer's failure reason is
unknown because timeout/spawn exceptions discarded its output.

The supervisor now preserves bounded output on failures and emits one closed
`SNCI_FAILURE` record containing stage, failure kind, exit/cleanup codes,
deadline, elapsed time and log size/truncation. Exception messages are excluded.
The runner retains the private worker log and projects validated diagnostics
to stable hold codes, such as `worker_timeout_dialyzer`. Malformed, duplicate,
extra-field or arbitrary diagnostics remain generic `worker_failed`; these
records cannot create successful acceptance.

`snci/repair_dialyzer.py` requires the exact protected failed log, complete
unchanged main source, disabled policy, stopped units/processes and exact
reviewed source delta. A durable single-use claim precedes mutations. It copies
the immutable image's dev cache from an inert, never-started, credential-free
container and inspects the bounded tar without host extraction. Cache files
are hashed and tied to the image and locked source identity. Traversal, linked,
empty or duplicate project PLTs hold the operation.

A verified warm main image is reused. Only an absent project PLT causes a main
dependency rebuild with `mix dialyzer --plt`; sn004 receives its own prepared
image. Both require a nonempty project PLT, the fresh offline native probe and
the complete isolated quality suite, including full Dialyzer analysis. The
600-second Dialyzer and 1500-second worker deadlines, resource limits, profile
hashes, test floors, skip ceiling and coverage requirement are retained.

The operation preserves failed source/logs, previous package, private policy,
public preparation status and attempt journal. Only installed revision changes
immediately; accepted profiles update only after fresh quality success. The
timer stays disabled. Replay, partial writes, launch uncertainty or a new native
failure hold for inspection. No trusted status, merge, deployment or production
readiness is established by this source repair.

## Additional bounded repair: application cache transfer

This separate owner-authorized cycle starts at
`4662fbb392f531c59cb3ac07b4753ad353423a9f`. The worker previously copied the
entire dependency `_build` before deleting the application, so its colocated
JavaScript link to absent `assets/node_modules` could stop setup first.
Source fixtures prove the defect; they do not identify the first native
exception. The worker now excludes `symphony_elixir` before copying from both
`dev`/`test` `lib` and `phoenix-colocated`. Project PLT/hash files and dependency
bytes are retained, the application is rebuilt, and dangling dependency links
still fail. No global suppression of missing links is enabled.

Setup failures add an optional closed `setup_step` to `SNCI_FAILURE`.
For example, `worker_io_error_setup_home_cache` and
`worker_io_error_setup_build_cache` distinguish the two cache transfers without
exception text, paths or secrets. Unknown steps, extra fields and steps on
non-setup stages remain generic failures and cannot create acceptance.

`snci/repair_cache.py` is a new single-use operation, not a replay of a consumed
repair. It requires this exact installed base, its complete unchanged package,
an unaccepted closed setup failure, stopped units/processes and disabled policy.
The allowed source delta excludes dependency recipes, locked profiles,
capabilities, thresholds and deadlines. The protected archive, PLT claim and
receipt bind a nonempty project cache to the existing image and source.
Private hashes cover every preceding artifact and are checked again after
staging, together with the source, installed package, policy and status.

The operation preserves the entire failed attempt, prior package, policy,
status and journal. It reuses the existing preparation driver with a fresh
claim and exact revision: main reuses its warm image, runs a fresh offline
native probe and the complete isolated quality suite once. SN004 starts only
after main has a successful acceptance receipt. Failure, partial writes or
uncertain launch remain held for inspection. The timer remains disabled;
trusted status publication, activation, merge and deployment are outside this
repair. Local source tests do not certify native acceptance.

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
# Refresh successful preparations (GH24)

The original `prepare` command is a first-use operation: it creates fixed
directories and cannot renew completed preparations. `snci/refresh.py` is a
separate, one-shot owner transition from installed revision
`10b56bc96f764dabdf498aef3c1ed869f3845fb8` with both main and sn004 already successful.
It is not a failed-cache repair. Never remove a claim, edit receipt timestamps,
overwrite the old `prepare-*` directories or rerun the old repair helpers.

The transition preserves all old receipts and the old installed package. It
reuses only the same immutable image IDs recorded by successful preparation,
after checking local availability, unchanged dependency/configuration inputs and
the dependency-image recipe. It executes the existing isolated runner again,
including all five quality stages, native offline Codex probe and cleanup.
There are no live model calls, image builds/pulls or changed container limits.

Main keeps every locked file and minimum305/max-skips6. sn004 advances only to
PR14 `21ce4282e7ef8330cc1155bcb7b94fbf132032a8`, tree
`29fe41a2873a3db13ac2c0dc74b7f149391c9eeb`, minimum331/max-skips6 and the reviewed
runtime_config_test blob `5ca85121e627a8e085083fc2ea25b404c2fcd9c7`.
No other suite or policy limit changes. Published `profiles.json` stays the
historical seed definition; the protected runtime policy carries the transition.

## Owner procedure after exact-source review

Use a clean, root-owned checkout under `/root` of the exact accepted refresh
commit. Do not execute a moving branch, an unreviewed SHA, or an agent-controlled
directory. The helper verifies Git HEAD/cleanliness, GitHub linear ancestry/scope,
installed manifest and file bytes, disabled service/timer, controller lock,
pending journal entries, leftover worker containers, historical receipts and
current target identities before doing native work. Missing/stale inputs hold.
Ancestry is bounded to the initial commit plus at most two review repair commits
above the installed baseline; merges and unrelated history are rejected. The
aggregate change must still contain exactly the same four permitted paths.

From that checkout, with `REVIEWED_SHA` set to the exact independently accepted
refresh commit (the coordinator supplies it in the PR evidence):

```sh
python3 -I ci/continuous/snci/refresh.py --reviewed-head "$REVIEWED_SHA"
```

Run this long command in the owner's existing terminal/tmux session and retain
its output. Each profile can take up to the existing1500-second runner deadline
plus the180-second offline probe. No scheduler or service is started by this
command. The new evidence directory is
`/var/lib/symphony-next-ci/refresh-<reviewed-sha>/`.

Only after both profiles pass does the helper stage the reviewed package and
recheck all inputs. It journals commit intent, retains the predecessor at
`/opt/symphony-next-ci-before-refresh-<reviewed-sha>`, installs the new package,
and atomically commits one disabled policy containing both immutable receipt
pointers/digests. `COMPLETE.json` and `REFRESHED_DISABLED` mean this transition
finished; they are not a trusted PR check or deployment approval.

Review the fresh evidence, then activation remains a distinct owner operation:

```sh
python3 -I /opt/symphony-next-ci/owner.py activate
```

Activation requires matching `commit-intent.json` and `COMPLETE.json` records
bound to the installed revision and SHA256 of the exact installed disabled-policy
bytes, including whitespace and key order. Activation reads and decodes that same
protected byte snapshot; refresh verifies byte-exact publication readback. Both
receipt pointers must refer to that same refresh. Missing, partial or mismatching
completion proof holds before login checks or timer changes. It also verifies
package revision/integrity, all receipt identities/hashes,
age<86400s, complete quality, ruleset and dedicated reviewer login. Only then
does the existing timer start. Draft PRs need the existing `snv:verify` label;
request one exact target after authoritative state readback. A final trusted
check still comes only from the protected controller's own review and execution.

## Failure and recovery

Any claimed attempt is single-use, even after a failure. Do not delete/reset it.
Before installation, a failure leaves the original package and policy in place.
If the package rename fails, the predecessor is restored. If directory sync fails
after a successful rename, both packages remain for owner reconciliation; no
rollback into the now-occupied install path is attempted. A crash/error after
`commit-intent.json` requires owner reconciliation of revision, policy digest and
`COMPLETE.json`; never blindly retry or activate. If policy publication fails
after package replacement, activation rejects a mismatching installed revision
or missing completion proof even when policy replacement itself already happened.
The old policy bytes are preserved privately as `policy-before.json`, and both
old preparation directories remain untouched. Rollback is owner-operated while
disabled: reconcile actual state before restoring the preserved package/policy;
never reuse a partially completed attempt or fabricate a fresh receipt.

Local tests exercise real temporary files and injected GitHub/native boundaries.
They do not attest host1c-db, Docker, native Elixir or protected check publication.
This transition must receive an independent exact-source review before owner use.

## Rebuild the two missing preparation images (GH24)

Owner readback on 2026-10-02 confirmed that both accepted profile image IDs were
absent while the pinned toolchain seed remained available. The reuse-only refresh
correctly held before claiming an attempt or modifying the installed package.
The current Docker store uses overlay2; image deletion versus an unlocated older
store is not established. This separate recovery does not reconfigure Docker.

`snci/rebuild_missing.py` handles only this observed state: installed revision
`10b56bc96f764dabdf498aef3c1ed869f3845fb8`, disabled CI, unchanged successful
historical preparations, main image `sha256:b6ef7528c8e8435208c0856698d50158e545c2e4fc7624ca6bda49f585a392c0`
and sn004 image `sha256:9233988cb5fbbf405a565fc1d0bb92e9296e189b90f3381c50221463801a1172`
both absent, and original seed `sha256:a93a7c8e7a2d292c924f461d06a27986b1a95818c1be1fbb5b68b290b409256c`
present with filesystem layers matching both protected historical seed receipts.
A daemon/auth error is not classified as an absent image. Any different binding,
missing seed, existing output tag, active service/worker or pending journal holds.

Source approval is separate from the older refresh review: the recovery candidate
must be a bounded linear descendant (initial commit plus at most two repairs) of
accepted source `716d3b5b6f22e6ebe005d09820ed8806667a287b`, with changes limited to
`snci/refresh.py`, `snci/rebuild_missing.py`, `tests/test_rebuild_missing.py` and
this README. Package scope is also checked against the installed predecessor.
The existing owner, worker, runner, dependency recipe, seed, profile assertions,
controller and service configuration are unchanged.

After independent exact-source review, use a clean root-owned checkout of that
new accepted revision on 1c-db. In the owner's terminal/tmux session:

```sh
python3 -I ci/continuous/snci/rebuild_missing.py --reviewed-head "$REVIEWED_SHA"
```

The shared controller lock and `refresh-<reviewed-sha>` claim protect the whole
transition. For each exact target, the helper materializes a new source tree,
copies the unchanged dependency recipe and calls the existing owner image build.
Build has the existing dependency-fetch network and 1800-second deadline; this
is not an offline operation. The pinned base is never pulled or substituted.
The build remains bound to its seed layers and source locks. New image IDs are
recorded in new evidence; historical image IDs and acceptance bytes are preserved.

Each new image receives a local tag
`localhost/symphony-next-ci-prepared:<reviewed-sha>-<profile>` before quality runs.
The owner must reserve this tag namespace exclusively for these owner workflows.
All supported refresh/rebuild writers hold the same `controller.lock` for the
whole transition. Conflicts visible at inspection hold. Docker's tag operation
has no compare-and-set: a separate administrator, process or Docker API client
that ignores this lock can create a conflicting tag between inspection and tag
creation, and Docker can overwrite it without a detectable failure. This helper
does not provide no-overwrite protection against such external concurrent writers.
Do not schedule another writer to this namespace while recovery is running.
Tags prevent the images from being untagged; they are not backups and do not
protect against removal of all unused images by an external administrator.
`retention.json`, `image.id`, `seed.json` and `build.log` remain in the new private
profile directory. No image archive or registry upload is performed.

Both profiles must pass the unchanged offline Codex probe and isolated worker
(including PostgreSQL, all five quality stages and cleanup). Main keeps its
305-test floor; sn004 uses the already reviewed target/minimum331/test lock.
After both pass, final checks verify source, old package/policy/receipt bytes,
seed and historical seed receipts, new build/retention records and live image
identities/layers. Only then does the existing package-swap and atomic disabled
policy commit execute. Byte-exact completion gates and crash handling are shared
with the accepted refresh; activation remains a separate owner action.

`REBUILD_IMAGE_START`, `REFRESH_QUALITY_START` and final `REFRESHED_DISABLED` are
progress/completion messages, not trusted PR checks. Each profile may take up to
1800 seconds for build, 180 seconds for probe and 1500 seconds for quality.
On any failure, retain both old preparations and all new partial evidence/images.
Do not delete claims or rerun old prepare/repair helpers. A claimed recovery is
single-use; interruption requires inspection and reconciliation, not blind retry.
This helper neither restarts Docker nor activates CI, merges or deploys.


### Recover recurrent image loss and retain running references

The owner observed both prepared images and retention tags missing again,
while seed, activated38 policy and saved zero-read review remained intact.
PR55 claim/stage/backup were absent. Tagged images are still eligible for
`docker image prune -a`; stopped anchors are eligible for container/system
prune. The deletion actor is UNKNOWN. No shared cleanup configuration changes.

Use only an independently accepted exact candidate above PR55 HEAD
10fc787a2b03c0dbd602f35991dd9aacd36718ab/tree812fe91fc7fe9154229f2e4ecad475b98da5250e.
New helper `snci/recover_retention.py` validates bounded candidate delta,
exact paused activated policy, old package/manifest, prior activation,
immutable held attempt and historical receipts, current PR14/quality-source
bindings, native binary/seed/daemon/rules and stopped units/no live workers.
Its new claim is private refresh-HEAD; all prior claims/receipts remain intact.
Do not invoke the consumed38 rebuild or replay PR55's rejected preflight.

The staged exact candidate runs the accepted9-case offline fake-provider
native probe once as existing snci-review in fresh unauthenticated homes.
Both dependency images are built once from unchanged locked sources/recipe
and pinned local seed. Build IDs may differ: each image receives a fresh
full locked worker quality run and receipt with actual timestamp/results.
Historical receipts are checked as history, never reset to confer freshness.

Two names `snci-retain-HEAD-{main,sn004}` run only a Python signal wait,
with inherited healthcheck disabled, UID/GID10001, networknone, readonly,
no mounts/secrets/socket/caps, no-new-privileges, 0.05CPU/32MiB/16PIDs each
and restartunless-stopped. Exact inspected identity/isolation/running state
binds each image. These references protect against ordinary Docker
image/container/system prune; forced deletion, keeper termination and daemon
data loss remain outside that guarantee and cause HOLD. They are retention
resources, not model/quality workers, and spend no model calls.

Before commit, recheck old package/policy/history/target/rules/binary/seed/daemon,
fresh receipts, both keepers/images/tags and staged bytes. Preserve predecessor
package/private policy; atomically change only installed_revision and image/
preparation fields in both profiles. All heads/trees/locks/thresholds/models/
budgets/exceptions and enabled=true remain fixed. Dedicated timer/service
remain disabled/stopped; do not invoke activate or enable the timer.

Run once in existing owner root tmux on1c-db from a clean root-owned checkout:

```sh
/usr/bin/python3 -I ci/continuous/snci/recover_retention.py --reviewed-head "$REVIEWED_HEAD"
```

Success is `RECOVERED_REVIEW_TRANSPORT_PAUSED HEAD`, with private byte-bound
commit-intent/COMPLETE proof and full readback. An interruption/partial/unknown
write retains claim, backups and owned keeper/build evidence for reconciliation;
no automatic deletion, replay or rollback. Only after completion verification
may the owner start the dedicated CI service once under unchanged daily<=4.
Actual exact-HEAD review/quality/check gates still apply; no CI success or
release is implied by source tests or this maintenance transition.

Author source tests:213 total,212passed,one existing native isolation skip,
0failures/errors,exit0; log SHA256
0209e133f92ea046ac88683fb7b50cf2e41ba1487156f089f18aef7b81215374.
Protected native recovery/build/keepers/quality/install/live model/check
NOT_RUN during source work. Current actor/runtime availability UNKNOWN.

### Exact source paths and absent added/deleted versions

The owner-installed06 launch ended in terminal `review_source_only` before
review.json/result.json. Its rejected argument and read counters are UNKNOWN.
Separately reproduced: a base read of an added file, or head read of a deleted
file, used to abort the whole review. This is not proof of the live cause.

`read_source` now advertises the exact verified path union and head/base aliases.
A union-known path absent in that revision returns success=false with explicit
`missing_revision` and available aliases. It reads no blob and satisfies no
coverage; all available changed versions still require actual reads for READY.
Missing requests consume the existing400-call budget. Successful read_count and
total request_count are separate. Unknown/unsafe paths and invalid arguments
still cause fatal HOLD. Typed source denials retain only category, argument hash,
valid revision alias and counters in the new hold row; raw argument values are
not persisted. Other security/identity/quality/publication gates are unchanged.

`snci/repair_source.py` is a single-use paused transition above exact06. It checks
the recovery proof against the original journal plus exactly the new terminal
source-only hold, byte-bound inputs, retained images/tags/keepers, unchanged fresh
receipts, binary/daemon/seed/rules and source/package bytes. Old recovery COMPLETE
is an immutable pre-run proof; do not call its unchanged completed() after a CI
row was added or rewrite its history hash to make it current.

The helper stages only the independently accepted bounded delta and runs11
offline native fake-provider cases as the existing reviewer account. It changes
only installed_revision, keeps enabled=true and all image/preparation pointers,
preserves every old claim/proof/row/receipt and creates a new private claim and
package backup. It never builds, runs quality, starts units or publishes checks.
Run once from the clean root-owned exact reviewed checkout in owner tmux on1c-db:

```sh
/usr/bin/python3 -I ci/continuous/snci/repair_source.py --reviewed-head "$REVIEWED_HEAD"
```

Success is `SOURCE_CONTRACT_INSTALLED_PAUSED HEAD`. Verify its new completion
proof and remaining daily budget before one corrective live CI launch. The
timer remains disabled. A terminal hold consumes this final bounded transport
source repair (2/2); preserve diagnostics and stop instead of replaying it.
Native fixture evidence:11 cases, actual exit0, unchanged Codex binary SHA256
0753dfe1d8b87a52436deb13eb1c549661ef4c84fee2c5aa688385eebeccb761;
probe log SHA256 d33688c0c5271a655643aa27510f08b8413d428ab0358c1fe45b6f19fd90a707.
Author source suite:233 tests,232 passed,one existing native-isolation skip,
zero failures/errors,actual exit0; log SHA256
c493e0ce9278ae1400902f592bc82c9c795cbe9fc9c2c15bf1c21c4a23e490dd.
This is transport evidence; privileged installation/live model/trusted check
are NOT_RUN by the source writer and remain separate acceptance gates.
