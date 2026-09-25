# Explicit Elixir runtime build candidate

Status: source/configuration candidate. The image has **not** been built or run.
This packages the existing Symphony Elixir application. It does not implement or
certify the SymphonyNext control core, native tracker, Authentik, durable state,
runner isolation, admission or release features in SPECIFICATION.md.

## Incident and scope

Coolify application `rucuwj1b2zuzclbdmvspjehh` used Railpack against repository
root with no start command. The deployment of `4de77e7257bfc97d854fd54034e7496fcbe3205f`
reported no start command and built an image containing only system packages.
The application was stopped and auto-deploy disabled on 2026-09-25.

This candidate explicitly compiles `elixir/` and runs the existing CLI through
`mix run --no-start`. The CLI retains its acknowledgement and workflow checks;
the scheduler is not started before those checks. No example production workflow,
credentials, Codex, host mounts, published port or admission marker is supplied.
The default `runtime` target must exit nonzero when invoked without arguments.
Both targets have an explicit writable log root: `/var/lib/symphony`, producing
`/var/lib/symphony/log/symphony.log`. The application removes its console handler
after file logging starts; `docker logs` alone is not the application log.

The separate `smoke` target uses the real application, a memory tracker with no
issues, a loopback listener, and `/usr/bin/false` in place of an agent command.
It is a container packaging fixture, not an operational queue or production UI.
Never select it as the Coolify deployment target.

## Build inputs

- Context: a clean checkout of the reviewed full commit SHA, repository root.
- Dockerfile: `deploy/runtime/Dockerfile`; last/default target: `runtime`.
- `ELIXIR_IMAGE`: `docker.io/library/elixir:1.19.6-otp-28-slim@sha256:<64 lowercase hex>`.
  Resolve the official image digest on the builder and retain it in the evidence.
  No digest has been invented or accepted by this source change.
- `SOURCE_COMMIT`: full SHA of that clean checkout. The image label is a declaration,
  not independent proof of its source; retain the checkout identity and build log.
- Hex 2.2.1; Rebar3 3.25.1, SHA-256
  `924576737f0d3098e1fa4691e6f542bf61036d234c61ebdc18aafef8e2bccf67`.
- Elixir dependencies: unchanged `elixir/mix.lock`, fetched with `--check-locked`.
- Debian packages are resolved during the candidate build. Record their exact
  versions; snapshot/version pinning remains a release gate before OPS-02 acceptance.

Use an isolated builder without production credentials. Do not add Docker access
to the bootstrap service or verifier. Do not run this through WORK-01, its used
helpers, or the fixed PR11 verifier. GitHub Actions remain disabled.

After selecting a reviewed SHA and a verified base digest, build both targets:

```sh
docker build --progress=plain --target runtime \
  --build-arg ELIXIR_IMAGE="$SNV_ELIXIR_IMAGE" \
  --build-arg SOURCE_COMMIT="$SNV_SOURCE_COMMIT" \
  --tag "symphonynext-runtime-candidate:$SNV_SOURCE_COMMIT" \
  --file deploy/runtime/Dockerfile .
docker build --progress=plain --target smoke \
  --build-arg ELIXIR_IMAGE="$SNV_ELIXIR_IMAGE" \
  --tag "symphonynext-runtime-smoke:$SNV_SOURCE_COMMIT" \
  --file deploy/runtime/Dockerfile .
```

Keep UTC start/end, exit status, complete sanitized logs, image IDs, base digest,
package inventory and the exact SHA/tree. A build failure remains a failure.
Do not change the lockfile, drop compiler errors or replace the app with a web stub.

## Required isolated acceptance (not executed here)

Run only the new candidate images on the isolated builder. Use unique names and
preserve containers/logs after a failure. Bound each probe; no automatic retries,
no restart policy, no host networking, no published ports, no credentials or
mounted production directories. Suggested limits: read-only root, cap-drop ALL,
no-new-privileges, network none, 2 CPUs, 2 GiB memory, 256 PIDs, bounded tmpfs at
`/tmp` and `/var/lib/symphony` owned by UID/GID 10001.
Mount a **new test-only** durable log directory at `/var/lib/symphony/log`, writable
by UID/GID 10001. Retain it after both successful and failed exits. Do not mount
any existing bootstrap, verifier or production state. Bound storage on the isolated
builder. A stopped container does not preserve the contents of its tmpfs.

1. Inspect image config: UID/GID 10001; exec-form Mix entrypoint; no production
   workflow or secrets. Verify the default target does not inherit smoke CMD.
2. Run default `runtime` with no CLI arguments. Require exit 1 and the existing
   acknowledgement error; an executable/linker/Mix error is not an acceptable pass.
3. Run `runtime` with the acknowledgement and a nonexistent explicit workflow.
   Require exit 1 with `Workflow file not found`; no scheduler should start.
4. Run the `runtime` target once with the read-only `smoke.workflow.md` fixture
   mounted at an explicit path and pass that path plus the acknowledgement.
   Also exercise the `smoke` target once. Each probe has a 90-second total budget.
   Within that budget, GET
   `http://127.0.0.1:4327/api/v1/state` from inside that same container. Require a
   JSON object with no `error`, counts running=blocked=retrying=0 and empty lists.
   HTTP 200 alone is insufficient: the existing endpoint can return an error body.
5. Require GET `/` and the dashboard's referenced static assets to succeed. Verify
   no Codex process, tracker request, agent session, token usage or workspace job.
6. Capture the process list and file logs, then send SIGTERM once. Require exit
   within 15 seconds; capture actual exit status, Docker logs and durable file logs.
   A SIGKILL, OOM or timeout is not clean shutdown acceptance. On an earlier process
   failure, retain the durable log directory even if the HTTP probe never succeeded.
7. Retain the no-model evidence. Do not infer native tracker/SSO/product readiness.

If any assertion fails, preserve evidence and repair the candidate branch. Do not
turn on Coolify auto-deploy or change the stopped production application.

## Release gates and Coolify handoff

This branch is draft-only until real build/smoke evidence and independent exact-HEAD
review exist. The trusted check for PR11 does not validate it, and the used fixed
verifier must not be replayed. A separately reviewed trusted target is required.

Changing the production resource to a Dockerfile is a later configuration step.
Its current port 3000, public route and disabled health check do not match this
offline fixture. Bind addresses, authenticated routes, real workflow/admission,
resource limits and a functional health contract must be established for the
actual target product. Do not expose the stock unauthenticated dashboard as the
SymphonyNext production UI, or mount the historical bootstrap's state/credentials.

No restart/deploy, application config update, workflow admission, model launch or
marker reset is performed by this source change. Rollback has not been exercised;
there is no verified healthy predecessor to select automatically.

## Primary references

- Existing implementation: `elixir/mix.exs`, `elixir/lib/symphony_elixir/cli.ex`,
  `elixir/lib/symphony_elixir.ex`, `elixir/lib/symphony_elixir/tracker/memory.ex`.
- https://hub.docker.com/_/elixir
- https://hexdocs.pm/mix/Mix.Tasks.Run.html
- https://docs.docker.com/reference/dockerfile/#entrypoint
- https://docs.docker.com/build/concepts/context/#dockerignore-files
- https://github.com/hexpm/hex/releases/tag/v2.2.1
- https://github.com/erlang/rebar3/releases/tag/3.25.1
