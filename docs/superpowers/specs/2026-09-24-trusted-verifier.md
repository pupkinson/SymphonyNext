# PR #11 trusted verifier — bootstrap design

Owner instruction: «сделай это и напиши что нужно сделать мне — я сделаю».
Preparation and testing are authorized; the owner installs the reviewed package and registers the GitHub App. This is a new scoped verifier, not replay of WORK-01/PUP-179 or implementation/admission of all SN-030.

## Goal and acceptance
Close the dependency-complete Python test gate for reviewed commit 78d60bd77a5c9667e1241ca64f3429a3123d86df, tree 836ea7df791bd658baed074daf7b26c1851619a9, base c3c8bce82d148c3e558481644eb5d0a4072fdb6f. Require the exact 126 test IDs with no failures/errors/skips. A separate owner-controlled GitHub App publishes the result. No model, scheduler, deploy, merge, Actions or old marker access.

## Design
A root-owned, fixed-purpose operator CLI installs only /opt/symphony-next-verifier, /var/lib/symphony-next-verifier and the new /etc/systemd/system/symphony-next-verifier-controller.service. It does not start or enable the service. The owner then starts verification of one approved target. No arbitrary shell argument is accepted. The controller holds the App key; a transient systemd service executes tests as DynamicUser in a separate RootDirectory. Bind only /usr, necessary lib/bin links, immutable source, immutable venv and the locked worker. PrivateNetwork, PrivateDevices, PrivateIPC, no capabilities, readonly source, bounded CPU/memory/PIDs/time. Use a distinct writable /worktmp tmpfs capped at 512 MiB and mask /tmp and /var/tmp to avoid implied PrivateTmp precedence. Worker verifies the effective tmpfs bound and inaccessible host temporary paths before testing. Chroot and worker directories are explicitly chmod 0755 even under umask 077; controller/key/job parents remain private. No Docker socket or shared Symphony paths.

The target manifest is fixed and SHA-bound, owned by root; accepting a new target is a separate reviewed manifest update. This initial package has no open webhook, timer, arbitrary branch dispatch or automatic new-HEAD admission. A scheduled caller could later submit already-approved targets; that generalized integration is not claimed here.

GitHub App: selected repository pupkinson/SymphonyNext only, Contents read, Pull requests read, Checks write. Webhooks disabled for this bootstrap. Fetch/PR readback validates repository ID 1381693716, branch and exact HEAD. Auth material stays out of argv/logs; checkout uses an ephemeral root-private askpass token file, removed after fetch. No GitHub token enters the test unit. All network commands have deadlines, bounded output and no automatic mutation retry.

The controller persists intent before publication, never reruns a begun target automatically, and retains logs/status after any failure. A check is created only after sandbox execution and evidence validation, then read back for app ID/SHA/conclusion/external ID. An ambiguous write remains UNKNOWN and cannot trigger another POST. The bootstrap never converts local mocks into trusted PASS.

## Owner steps and trust
Owner verifies the package commit/hash, installs OS prerequisites if absent, runs the fixed installer, creates the GitHub App and installs it only on this repository, places its private key in the new root-private directory and configures non-secret IDs. Owner invokes the fixed verification command. Branch protection is configured to require the resulting check from that exact App; only then is spoof resistance accepted. Tokens must never be pasted into chat.

## Verification
Test pure acceptance against wrong SHA/app/count/test IDs/skips, malformed JSON and duplicate tests. Test persistence refusal for existing attempts and unsafe paths. Test worker with actual temporary unittest modules for pass/fail/skip. Test controller boundaries using fake HTTP/process adapters; real systemd/GitHub acceptance remains owner-run and explicitly NOT_RUN in delivered evidence. No sandbox claim from mocked process execution.

## Constraints and failure behavior
Python 3.10 on Linux/systemd 249 target; package code stdlib + /usr/bin/openssl, /usr/bin/git, /usr/bin/curl. Pinned wheel-only jsonschema and dependencies in its private venv. Resource proposal: 2 CPU, 2 GiB memory, 128 PIDs, test runtime 600 seconds, bounded logs 16 MiB; allocation occurs only by owner's fixed install/run. STOP preserves this verifier's artifacts; old artifacts are never touched. Partial installation cannot be silently reused as successful installation. Root-owned parent chains and regular files must be checked before reading config, keys, manifests or launching.
