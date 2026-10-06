# Continuous trusted PR verification

First implementation for `pupkinson/SymphonyNext`: independent Codex review,
isolated Elixir quality stages, then GitHub App check
`symphony-next/verified-tests`. No GitHub Actions, merge or deploy calls.
The source PR does **not** install, activate, or certify itself.

## Behaviour

A disabled-by-default systemd timer polls every two minutes. One controller,
one reviewer and one worker at a time. Explicit `daily_attempts: null` removes
the UTC daily attempt ceiling; finite integer values from 1 through 4 remain
supported, and initial installation defaults to 4. Missing fields, booleans,
strings, floats and other values are rejected. Unlimited admission keeps all
attempt accounting, per-attempt bounds and existing review/quality gates.
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

## Owner-requested removal of the daily ceiling

The owner requested unlimited daily CI admission after four terminal review
holds on 2026-10-03. This changes the daily count policy, not the terminal
reviews, per-attempt execution bounds or the separate source repair budgets.
The historical finite-budget statements above describe their original runs.

`snci/daily_limit.py` installs the exact independently reviewed five-file
increment above revision `344ea8d5129b7815c212d8a16c207b937dd825a5`. It binds the
old installed package/policy and latest PR14 terminal hold, inputs and review
bytes. It refuses active units, an enabled timer, pending journal rows, drift,
unrelated source changes or a previously claimed transition. A failed oneshot
with both MainPID and ControlPID zero is idle; its failure is not reset.

The transition changes only `daily_attempts` to JSON `null` and
`installed_revision` to the reviewed commit. It preserves every journal row,
old attempt artifact, receipt and retention reference, captures predecessor
transition metadata and retains an exact package and private policy backup.
It starts no units, models or workers; it performs no Docker operation or
GitHub check write. Unchanged native binary bytes are checked without execution.
The controller lock, single-use private claim, staged byte verification,
durable commit intent and policy/package/history readback protect installation.

Run once from the clean root-owned exact reviewed checkout in owner tmux on
`1c-db`, with the timer already disabled:

```sh
/usr/bin/python3 -I ci/continuous/snci/daily_limit.py --reviewed-head "$REVIEWED_HEAD"
```

Success prints `DAILY_LIMIT_REMOVED_PAUSED HEAD` and `VERIFIED_PAUSED` with
`daily_attempts: null`, the new policy digest and a count with `remaining: null`.
This certifies the paused policy/package transition, not a successful PR check.
The latest PR14 `CHANGES_REQUESTED` review remains intact. A policy digest change
creates new input identities; do not immediately rerun that unchanged rejected
head or enable the timer. Correct the two high-severity findings first, then
admit a new source increment through the normal independent review and quality
gates. Unlimited daily admission never erases or overwrites a held tuple.

If policy writing fails before replacement, the old package is restored and
the candidate stage plus claim remain for diagnosis. If policy replacement
succeeded before an error, its matching new package, predecessor and durable
intent remain paused; no completion is claimed. Preserve evidence and reconcile
the actual state before any new action. Never delete a claim to replay it,
rewrite the journal or use a historical recovery completion after adding rows.
The new completion audit checks preserved rows as an immutable subset, so later
legitimate attempts do not invalidate the installation's original history.

## Closed PR75 profile transition

The installed unlimited-admission revision `2f40275cd7f2f6a2f2147c195acfab79e434cfa6`
with policy digest `8438cf3f0b6854b2659b9375757fb58483d8baeb085730dec6a3e89b75d278e4`
can be advanced only by the separately reviewed CI-owner helper `snci/pr75_profile.py`.
The source approval is recorded in GH33 comment5993885820, following design5993826196.
This source approval does not execute native preparation, installation or a trusted check.

`profiles-pr75.json` binds product head `be5371e71db363d5a07c7109d6dd010a6ceca7ef`,
tree `b0f828141ca90851f6e037d6f1741aaaa28496de`, four reviewed dependency/helper/CoreTest
blob advances and all68 quality/test inputs. It retains name `sn004` for the existing
private PostgreSQL fixture. Native quality requires at least462 tests, at most6 skips,
zero failures, configured coverage100%, all protected stage exits0, Dialyzer0 and
verified cleanup/source before-and-after. The `main` profile remains identical.
The existing worker, dependency Docker recipe, container capabilities, offline quality,
resources, GitHub App and branch ruleset are unchanged.

The owner request is closed to PR75 in repository1381693716, exact head/ref above and
base `233dda1878533a425574074b8d34344b50d41cf7` on
`docs/sn005-authentik-project-access-20261004`, with explicit draft admission. While
installed it selects only that target; changed head/base/ref/tree/repository or request
shape holds. Labels cannot enlarge its scope. Without this root-installed request the
original main-only/draft-label policy applies. No branch is retargeted, and this check
will not certify a later main integration or any other HEAD/base tuple.

The concrete reviewed owner handoff must provide the CI package commit before using:

```sh
/usr/bin/python3 -I <clean-reviewed-checkout>/ci/continuous/snci/pr75_profile.py prepare --reviewed-head <ci-package-sha>
/usr/bin/python3 -I <clean-reviewed-checkout>/ci/continuous/snci/pr75_profile.py install --reviewed-head <ci-package-sha>
/usr/bin/python3 -I <clean-reviewed-checkout>/ci/continuous/snci/pr75_profile.py verify --reviewed-head <ci-package-sha>
```

These are three distinct owner actions, not a shell chain or native admission. The first
claims a new private `refresh-<ci-package-sha>` directory, snapshots predecessor artifacts,
stages exact CI bytes, probes the dedicated native transport and builds/retains a new
image. `PREPARED.json` means IMAGE_PREPARED_ONLY: it has no quality receipt or installation
acceptance. The second freshly rechecks stopped units, policy/package/source, old terminal
journal, receipts/images/keepers, seed and daemon, then claims quality exactly once. Only
actual protected quality can produce the new receipt, atomic allowed policy/package delta
and matching `COMPLETE.json`. The third reads that completion while units remain paused.
The completion audit rehashes every manifest-listed file in both the current installed
package and its predecessor. A changed current worker is rejected even when `installed.json`
and `revision` remain unchanged; the saved completion, policy and historical evidence are
preserved. This regression and fixup are admitted separately in GH33 comment5994649363.
Each native leaf has a whole-process1800s deadline and shortened subprocess timeouts with
120s reserved for cleanup/readback. Run owner leaves under their own tmux/log/exit receipts.

Old attempt/source/receipt/transition bytes and journal rows remain immutable; newly
publishing check rows can still be reconciled read-only. Existing source directories are
0755 within private0700 state and are hashed without falsely requiring every source file
be0600. Missing images/keepers/seed, busy units, drift, existing claims or failed quality
hold and preserve evidence. A response lost after policy replacement preserves the matching
new package and durable intent; there is no automatic write replay or inferred completion.
The controller requires the installed-policy/package-bound completion before admitting
this owner request. Repeated preparation or quality is rejected.

The transition retains unlimited daily admission, enabled policy and a disabled timer.
It never starts the service, enables scheduling, changes product auth, merges or deploys.
A protected one-shot is a later concrete owner handoff and must freshly read back its exact
inputs/review/result/check identities. The owner-reserved retention namespace and original
Docker concurrency limitations still apply; the helper does not repair unavailable history.

## Bounded source pages and preserved PR75 preparation

The owner-reported PR75 attempt under policy
`f50569540724f2be86dd77b529e6d0eb73d2ae0c8b6b23de27d354b859a2f414`
held because the independent reviewer could not see the changed middle of both
CoreTest versions. A source read counted by the coordinator does not establish
that the native model received the entire tool output. The precise native
truncation mechanism remains unverified by this source-only repair.

`snci_source.read_source` now requires exactly `path`, `revision` and integer
`page`, starting at zero. Each `snci-source-page/v1` response identifies the
Git blob, full-source SHA256 and byte length, page index/count, byte offsets,
page SHA256, content and `next_page`. Text is strict UTF-8 and preserves original
newlines and bytes when reconstructed. Even an empty file has one page. The
complete serialized contentItems result stays at most8192 bytes, including
JSON escaping; partitioning additionally reserves256 bytes for the RPC wrapper.
A long line is split at character boundaries. Binary input holds.

Follow `next_page` to null and read every page of both available changed versions.
Any unchanged context version whose reading begins must also be finished.
Missing middle pages, repeated last pages and incomplete page sets cannot
establish completion. After every page has been read, order does not affect
completion. Known added/deleted absent versions retain the explicit
`missing_revision` response and supply no coverage. Invalid pages/arguments or
unknown paths are sanitized fatal denials. The unchanged400-request/2MiB served
source/900-second review limits count duplicate pages and actual served bytes;
`read_pages` records successful page identities. All role, capability, target,
verdict and publication gates remain in force.

The offline native probe retains all11 earlier direct and gpt-6-astra catalog
cases and adds six: exact legacy whole-file characterization, large paged
head/base reconstruction from actual captured provider requests, and missing
middle-page rejection, for each catalog. Its fixture contains start/middle/end,
Unicode, escaping and long-line content. `--baseline-package` is mandatory and
pins the old e7 reviewer blob `4c95bbda74aea0541c54e0c3524ed2eb64bf5ca7`.
The helper supplies the original still-installed package only after verifying
its full manifest. Local decoder tests exercise complete, truncated, missing
and altered captured pages; they do not run the canonical native Codex binary.
The previous generic preparation commands are historical routes, not routes
for this paging candidate: their probe invocation lacks this baseline binding.

`snci/repair_review_paging.py` is a separate single-use owner maintenance leaf
above exact CI source `e7f87ede8b4e93fd7ae2d83b8b19ab58dbb93207`. It requires
the exact reported policy, complete original PR75 preparation, image/keeper and
receipt bindings, original2f predecessor, unchanged rules/native binary,
current PR75 identity and immutable terminal journal. Its14-path source delta
includes only the admitted reviewer/maintenance/test/docs/manifest paths.
No product, owner installer, profile definition, locks or worker path is allowed.
Service must be inactive/dead or failed/failed with both PIDs zero; timer must
be disabled/inactive/dead, workers absent and no publication pending.

After independent source review and a separate concrete owner admission, this
leaf may be invoked from its clean root-owned exact-SHA checkout on1c-db:

```sh
/usr/bin/python3 -I <clean-reviewed-checkout>/ci/continuous/snci/repair_review_paging.py install --reviewed-head <ci-package-sha>
```

It claims `review-paging-<sha>` once, stages the closed package, runs the17-case
probe as existing snci-review with fresh unauthenticated homes, and requires
provider-byte acceptance on the unchanged pinned binary. It then rechecks all
inputs, archives e7 at `symphony-next-ci-before-review-paging-<sha>`, records
durable intent and changes **only** `installed_revision` in policy. Both profiles,
receipt pointers/bytes/timestamps, unlimited budget accounting and owner request
are preserved. No image build, quality rerun, login change or model switch occurs.

Read-only completion validates current and archived package bytes, the original
e7 completion against the archive and its original2f predecessor, all historical
rows/files, exact HOLD101338df/input/review digests and the full native probe log.
The controller requires this new completion before attempting the unchanged
product tuple. New publishing rows may be reconciled without changing old rows.
`COMPLETE.json` alone cannot hide actual package mutation. A failed/unknown write
retains claim, intent and evidence for investigation; no replay is admitted.
`verify --reviewed-head <ci-package-sha>` is a separate paused readback action.

Source admission6002349621 does not execute that leaf. Native characterization,
paged delivery, owner installation and a new trusted exact-HEAD check remain
NOT_RUN. The old HOLD101338df remains immutable. Timer, service, production auth,
Task2–5, merge and deploy remain outside this source-only repair.


## Closed PR75 successor admission

The df9db5b installation pins PR75 to be5371e. Its sn004 profile also pins the
OIDC test file, so the repaired 8c5828b cannot be checked by merely restarting
the old controller. `repair_pr75_target.py` proposes one paused transition from
that exact installation to the reviewed 8c5828b/tree496889 successor request.
It retains the dependency image and all67 other locks, keeps the historical
profile file and receipts unchanged, and adds a separate successor definition
with only the OIDC test lock advanced and minimum_tests raised462→464. The
maximum6 skips and coverage100/stage/source/cleanup assertions remain.

The separately authorized owner install runs protected quality against that
exact candidate using the retained image before issuing a new receipt or
committing the package/policy. A byte-bound COMPLETE links the current package,
actual df9 archive, original paging/profile/probe evidence, new quality receipt
and both immutable HOLD histories. The successor controller requires this
completion before claiming a check, including during read-only publication
reconciliation. A partial claim or unknown write never permits replay.

This owner leaf leaves the timer disabled and the service idle. It neither
starts CI nor publishes a trusted check; those need a separate exact-target
owner leaf. Generic `owner.py activate` is not the successor activation path.
No new native paging probe is claimed: unchanged reviewer bytes retain the
archived exact probe evidence; a new native review/check remains NOT_RUN.
The historical request remains valid only for historical proofs or a separately
installed historical policy; a label cannot widen either closed request.


## Closed PR75 dependency-context admission

CI source b7561f97 and its installed successor policy still pin 8c5828b.
`repair_pr75_context.py` proposes a separate paused transition to exact PR75
HEAD6925de7e291d8cb36f83493d254679527a83c34d,
TREEb10931da9fa383bb5f22ca36f5f89e0038385e25, on the existing stacked base.
The immutable `profiles-pr75-context.json` advances only the OIDC fixture and
OIDC test blobs among68 locks; the other66 stay byte-pinned. The sn004 floor
rises464→507 while maximum6 skips, coverage100, zero failures and every
stage/source/cleanup assertion remain unchanged. Historical definitions and
requests, main profile, owner/reviewer/runner/worker/unit bytes and scopes stay
unchanged.

This is a source proposal. A separate concrete owner admission and independent
exact-source review are required before native installation. The single-use
owner leaf requires a clean reviewed checkout, paused disabled timer, idle
service (including failed/failed with both PIDs zero), absent workers, exact
installed policy/package/COMPLETE and retained-image/keeper/ruleset readback.
It binds all historical journal rows and prior state artifacts, including
paging/target inputs, intents, completions, source and logs. The latest
HOLD7cd15ad and older HOLD101338df/ff24dced remain terminal and immutable.

The retained sn004 image is
`sha256:13173082884c7fbe5bd03fc9db16a1deb0ec7af56d0dd71b4b391a252352c975`.
Image reuse requires a fresh exact-target protected507+ run before a new
acceptance receipt or installation. Author evidence and old native quality
receipts cannot supply that result. The operation freezes inputs again after
quality, stages only its closed nine-path delta, and records durable intent
before archiving b756 and replacing package/policy. Failure before policy write
restores the predecessor; unknown successful writes preserve matching package,
archive, intent and claim for inspection. Neither outcome permits replay.

Completion rehashes the current package, actual b756 archive and every older
archive through the original paging/profile proof chain. It requires exact
installed policy bytes, the new definition/request, fresh quality receipt,
predecessor completion/native-probe bindings and unchanged history. The
controller uses this context completion before claim or publication. New
publishing rows remain reconcilable while every prior row stays unchanged.

The future owner command, only after that separate native admission, is:

```sh
/usr/bin/python3 -I <clean-reviewed-checkout>/ci/continuous/snci/repair_pr75_context.py install --reviewed-head <ci-package-sha>
```

`verify --reviewed-head <ci-package-sha>` is a separate paused readback action.
The timer remains disabled; installation, protected native quality, paid
review/check, activation, production auth, Task2–5, merge and deployment are
NOT_RUN by this source stage. Historical stages and consumed budgets are not
reopened. Local tests exercise native boundaries with fixtures and certify
only these source contracts.


### PR80 preflight and failed-completion evidence fixup

The context preflight validates the predecessor sn004 target receipt through
its exact original completion/profile/paging chain. Its `pr75-target-<sha>`
pointer is not passed to the shared refresh reader; main keeps that reader and
its original closed grammar. Real-preflight source fixtures exercise actual
package, archive, receipt and proof validators. Incorrect pointers/digests,
identity, time, native-probe/quality evidence and predecessor proofs refuse
before a claim or protected quality run.

After package/policy commit, a failed COMPLETE file fsync, directory fsync or
completion validation preserves any created COMPLETE bytes with the durable
intent, receipt, package and archive. No success is reported. The single-use
claim prevents replay, and the controller continues to reject incomplete or
invalid completion. This fixup changes no profile, target, threshold, shared
receipt grammar or native guard; native execution remains NOT_RUN.
