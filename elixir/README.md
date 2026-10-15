## PR99 freshness-contract stage — saved, mandatory gates blocked

Owner-approved49999ms interpretation: observation must still be <50000ms at the
actual final decision. Exact49999/50000/50001 product-predicate tests, measured
real HTTPS49000 cache hit/no renewal and held49999 crossing denial are retained.
Canonical design/plan are unchanged; this is explicit owner-approved test scope.
Admission: https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6153858886

Current combined148/0; exact related446/1 (unchanged login-begin positive refusal,
cause UNKNOWN). Standard make NOT_RUN while related is RED; no current full
coverage/Dialyzer or all-gates claim. Code/source/patch/evidence saved, NO_NEW_HEAD.
Authdisabled/activationfalse; independent review NOT_RUN, findings still OPEN.
See docs/engineering/authentik-project-access.md for exact inputs, first failures,
budget lineage and cleanup limits. All preceding report text is retained as history.

---

> PR99 integration continuation: mandatory gates remain **NOT GREEN**; no new HEAD was published. Exact back-channel status regressions, raw key metadata and initial Repo handoff controls are retained. Current failures, UNKNOWN standard-make interruption and cleanup limits are in [the engineering report](../docs/engineering/authentik-project-access.md). Auth activation remains false; independent review is NOT_RUN. Previous reports below remain dated history.

> Task4 T4-R1–R6 repair candidate: auth stays disabled; mandatory gates and independent verdict are pending.
> Local session/credential bounds now accompany current Store reads through final protected response and callback cookie decisions.
> Signed logout retains exact millisecond/native bounds inside the existing atomic transaction; invalid handler requests use400.
> Cache capacity includes in-flight reservations, and a lifecycle owner preserves prior authorizers across Access restarts.
> LOGIN still returns to `/`; post-logout keeps the separate exact operator HTTPS URI, including non-root paths.
> See [the current repair evidence and limitations](../docs/engineering/authentik-project-access.md).

# Symphony Elixir

This directory contains the current Elixir/OTP implementation of Symphony, based on
[`SPEC.md`](../SPEC.md) at the repository root.

> [!WARNING]
> Symphony Elixir is prototype software intended for evaluation only and is presented as-is.
> We recommend implementing your own hardened version based on `SPEC.md`.

## Screenshot

![Symphony Elixir screenshot](../.github/media/elixir-screenshot.png)

## How it works

1. Polls the configured tracker for candidate work (included adapters: Linear, GitHub Issues, Jira
   Cloud, Asana, and GitLab)
2. Creates a workspace per issue
3. Launches Codex in [App Server mode](https://developers.openai.com/codex/app-server/) inside the
   workspace
4. Sends a workflow prompt to Codex
5. Keeps Codex working on the issue until the work is done

During app-server sessions, the selected tracker adapter may advertise provider-native tools. The
Linear serves `linear_graphql`, GitHub Issues serves `github_api`, Jira Cloud serves
`jira_rest`, Asana serves `asana_api`, and GitLab serves `gitlab_api`. Symphony executes those
tools with configured host-side auth and removes declared tracker-token environment variables from
the Codex child, so the agent does not need a second tracker login.

If a claimed issue moves to a terminal state (`Done`, `Closed`, `Cancelled`, or `Duplicate`),
Symphony stops the active agent for that issue and cleans up matching workspaces.

If Codex reports that operator input, approval, or MCP elicitation is required, Symphony keeps the
issue claimed and exposes it as blocked in the runtime state, JSON API, and dashboard. Blocked
entries are in memory only; restarting the orchestrator clears that blocked map, so any still-active
tracker issue can become a dispatch candidate again after restart.

## Control auth Task4 (source only)

Protected project reads use the current server session and local membership.
Runtime identity needs its own `runtime_identity_read` grant. IdP claims grant
neither permission. Production auth stays disabled pending Task5 evidence.

A complete explicit control configuration supervises Eligibility before Access.
The production observation adapter is closed. An admitted adapter must return an
actual client-scoped observation matching exact issuer, subject, sid, client,
application, provider, resource, generation, version and evidence reference.
Fixture observers are injected only by test supervisor options, never env strings.
Freshness is strictly below 50 seconds; failed reads never renew success. All auth
work carries the original handler-entry deadline of at most five seconds.

On successful Task4 login the browser receives a separate Secure/SameSite=Strict
`__Host-symphony-csrf` cookie. Send its value as `X-CSRF-Token` with the normal
HttpOnly session cookie to `POST /auth/logout`; the exact Origin is required.
Session rotation invalidates the old CSRF token. Local revocation commits before
redirecting the user agent to the configured OP logout endpoint. The redirect uses
client_id and the exact post_logout_redirect_uri, including non-root paths; no IdP
token appears in the URL. Without id_token_hint, the standard OP confirmation step
and provider compatibility must be verified by Task5.

The configured back-channel POST accepts one bounded form logout_token, verifies
its signature/claims using pinned Oidcc/JOSE, and commits durable jti plus revocation
atomically through Store. Replay remains a denial and does not repeat an effect.
Unknown COMMIT is reported as unavailable and reconciled by readback.

## How to use it

1. Make sure your codebase is set up to work well with agents: see
   [Harness engineering](https://openai.com/index/harness-engineering/).
2. Get a new personal token in Linear via Settings → Security & access → Personal API keys, and
   set it as the `LINEAR_API_KEY` environment variable.
3. Copy this directory's `WORKFLOW.md` to your repo.
4. Optionally copy the `commit`, `push`, `pull`, `land`, and `linear` skills to your repo.
   - The `linear` skill expects Symphony's `linear_graphql` app-server tool for raw Linear GraphQL
     operations such as comment editing or upload flows.
5. Customize the copied `WORKFLOW.md` file for your project.
   - To get your project's slug, right-click the project and copy its URL. The slug is part of the
     URL.
   - When creating a workflow based on this repo, note that it depends on non-standard Linear
     issue statuses: "Rework", "Human Review", and "Merging". You can customize them in
     Team Settings → Workflow in Linear.
6. Follow the instructions below to install the required runtime dependencies and start the service.

## Prerequisites

### Disabled Authentik protocol adapter (Task1)

`SymphonyControl.Auth.Config`, `Oidc` and `Clock` are source-only modules; they are
not installed in the application supervisor or HTTP pipeline. Authentication stays
disabled. The adapter pins Oidcc 3.9.0, uses operator-bound HTTPS endpoints, S256,
one token POST, one key refresh, and a shared maximum 5-second network deadline.
Secret values are read through owned file references and are never configuration
fields. Test CA trust is confined to the disposable HTTPS fixture.

Run the focused protocol suite from this directory after `mix setup`:

```sh
mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace
```

The fixture requires an existing `openssl` binary and loopback listeners. Full
`make all` also requires the existing disposable SN004 PostgreSQL fixture described
in [control-foundation.md](../docs/engineering/control-foundation.md). Neither a
focused GREEN nor compilation enables live SSO. Evidence, previous native history
and the Cloud gate blockers are in
[authentik-project-access.md](../docs/engineering/authentik-project-access.md).

The separately approved 2026-10-05 fixup adds a valid UTF8 Content-Type parameter
regression with structural binary/integer-list telemetry checks. Header values preserve
wire bytes, while nonUTF8 values are refused inside the adapter callback. Targeted49/0,
full CoreTest52/0 and broad462/0/6 with coverage100% are observed. Only three CoreTest
retry cases select local empty memory fixtures; assertions/timers/ranges are unchanged.
Final exact-source gates and owned PostgreSQL cleanup are in the checkpoint/workpad.
Pin/lock/coverage policy and prior histories are preserved. Authentication stays disabled;
independent review/trusted checks/live acceptance remain separate.

The 2026-10-06 repair also checks current credential UTC expiry at caller acceptance,
after the existing absolute monotonic deadline guard. The real HTTPS queued-result
tests cover expiry before resumption and a still-valid positive control:51/1 semantic
RED then51/0 GREEN. Both check one token POST, worker termination and captured-log
redaction. The HTTPS fixture and dependency/coverage policies remain unchanged.
Final full gates, exact source bindings and owned PostgreSQL cleanup are in the
engineering report/checkpoint; auth activation and trusted checking remain separate.

We recommend using [mise](https://mise.jdx.dev/) to manage Elixir/Erlang versions.

```bash
mise install
mise exec -- elixir --version
```

## Run

```bash
git clone https://github.com/openai/symphony
cd symphony/elixir
mise trust
mise install
mise exec -- mix setup
mise exec -- mix build
mise exec -- ./bin/symphony ./WORKFLOW.md
```

## CLI shutdown

Once the CLI has started monitoring its supervisor, a VM shutdown (including
SIGTERM) is allowed to finish its application stop callbacks and preserve the
VM's selected exit status. An unexpected supervisor failure while the VM is
running still exits nonzero. This does not add a guarantee for signals received
before the CLI finishes startup.

## Burrito releases

Symphony ships self-contained executables built with
[Burrito](https://github.com/burrito-elixir/burrito). They embed Erlang/OTP, Elixir, and Symphony,
but still expect `codex`, `git`, and the selected tracker credentials on the target machine.

Configured Burrito build targets:

- `macos_arm64`
- `macos_x86_64`
- `linux_arm64`
- `linux_x86_64`

`v*` tags publish all four targets with checksums. A manual workflow run builds the same
artifacts without creating a release.

Build targets do not establish runtime support. Startup currently requires Linux
with readable `/proc/self/environ`, even when control is disabled. The macOS
targets remain build configurations; agent startup there is rejected with
`credential_environment_unverifiable` because this Linux evidence is unavailable.
Linux packaged execution and deployment readiness require separate verification.

For a Linux x86_64 artifact, the launch command has this form:

```bash
chmod +x ./symphony-v0.0.1-linux_x86_64
./symphony-v0.0.1-linux_x86_64 ./WORKFLOW.md
```

## Configuration

Pass a custom workflow file path to `./bin/symphony` when starting the service:

```bash
./bin/symphony /path/to/custom/WORKFLOW.md
```

If no path is passed, Symphony defaults to `./WORKFLOW.md`.

Optional flags:

- `--logs-root` tells Symphony to write logs under a different directory (default: `./log`)
- `--port` also starts the Phoenix observability service (default: disabled)

The `WORKFLOW.md` file uses YAML front matter for configuration, plus a Markdown body used as the
Codex session prompt.

Minimal example:

```md
---
tracker:
  kind: linear
  provider:
    project_slug: "..."
workspace:
  root: ~/code/workspaces
hooks:
  after_create: |
    git clone git@github.com:your-org/your-repo.git .
agent:
  max_concurrent_agents: 10
  max_turns: 20
codex:
  command: codex app-server
---

You are working on an issue from the configured tracker {{ issue.identifier }}.

Title: {{ issue.title }} Body: {{ issue.description }}
```

Notes:

- If a value is missing, defaults are used.
- `tracker.kind` selects an adapter. Adapter-owned endpoint, scope, and auth settings belong under
  `tracker.provider`; the current Linear adapter still accepts the older flat `endpoint`,
  `api_key`, `project_slug`, and `assignee` aliases for compatibility.
- `tracker.required_labels` is optional. When set, an issue must have every
  configured label to dispatch or continue running. Label matching ignores
  case and surrounding whitespace. A blank configured label matches no issue.
- Safer Codex defaults are used when policy fields are omitted:
  - `codex.approval_policy` defaults to `{"reject":{"sandbox_approval":true,"rules":true,"mcp_elicitations":true}}`
  - `codex.thread_sandbox` defaults to `workspace-write`
  - `codex.turn_sandbox_policy` defaults to a `workspaceWrite` policy rooted at the current issue workspace
- `codex.turn_timeout_ms` is the maximum silence interval while a turn is streaming. Each
  app-server update resets it; it is not a total turn runtime cap.
- Supported `codex.approval_policy` values depend on the targeted Codex app-server version. In the current local Codex schema, string values include `untrusted`, `on-failure`, `on-request`, and `never`, and object-form `reject` is also supported.
- Supported `codex.thread_sandbox` values: `read-only`, `workspace-write`, `danger-full-access`.
- When `codex.turn_sandbox_policy` is set explicitly, Symphony passes the map through to Codex
  unchanged. Compatibility then depends on the targeted Codex app-server version rather than local
  Symphony validation.
- Workflows that run package managers or other commands that resolve external hosts should set
  `networkAccess: true` in `codex.turn_sandbox_policy`; otherwise DNS/network access may be denied
  by the Codex turn sandbox.
- `agent.max_turns` caps how many back-to-back Codex turns Symphony will run in a single agent
  invocation when a turn completes normally but the issue is still in an active state. Default: `20`.
- If the Markdown body is blank, Symphony uses a default prompt template that includes the issue
  identifier, title, and body.
- Use `hooks.after_create` to bootstrap a fresh workspace. For a Git-backed repo, you can run
  `git clone ... .` there, along with any other setup commands you need.
- If a hook needs `mise exec` inside a freshly cloned workspace, trust the repo config and fetch
  the project dependencies in `hooks.after_create` before invoking `mise` later from other hooks.
- For the Linear adapter, `tracker.provider.api_key` reads from `LINEAR_API_KEY` when unset or
  when value is `$LINEAR_API_KEY`. The legacy flat `tracker.api_key` alias behaves the same way.
- Do not put a literal tracker token in a repo-owned `WORKFLOW.md` if Codex can read that
  workspace. Use `$VAR`/host-side secret references so Symphony can keep the token out of the
  child environment.
- For path values, `~` is expanded to the home directory.
- For env-backed path values, use `$VAR`. `workspace.root` resolves `$VAR` before path handling,
  while `codex.command` stays a shell command string and any `$VAR` expansion there happens in the
  launched shell.

```yaml
tracker:
  provider:
    api_key: $LINEAR_API_KEY
workspace:
  root: $SYMPHONY_WORKSPACE_ROOT
hooks:
  after_create: |
    git clone --depth 1 "$SOURCE_REPO_URL" .
codex:
  command: "$CODEX_BIN --config 'model=\"gpt-5.5\"' app-server"
```

- If `WORKFLOW.md` is missing or has invalid YAML at startup, Symphony does not boot.
- If a later reload fails, Symphony keeps running with the last known good workflow and logs the
  reload error until the file is fixed.
- `server.port` or CLI `--port` enables the optional Phoenix LiveView dashboard and JSON API at
  `/`, `/api/v1/state`, `/api/v1/<issue_identifier>`, and `/api/v1/refresh`.

### Linear adapter profile

- Config: use `tracker.kind: linear` with `tracker.provider.endpoint` (default
  `https://api.linear.app/graphql`), `api_key` (defaults to `LINEAR_API_KEY` and accepts
  `$VAR`), required `project_slug`, and optional `assignee` (a Linear user ID or `me`,
  defaulting to `LINEAR_ASSIGNEE`).
  The legacy flat `tracker.endpoint`, `api_key`, `project_slug`, and `assignee` aliases remain
  supported. `required_labels`, `active_states`, and `terminal_states` stay under `tracker`.
- Scope and paging: candidate reads filter the configured project slug and requested state names,
  following Linear pages of 50. ID refreshes are also project-scoped and batch up to 50 IDs. Empty
  state/ID lists return `{:ok, []}` without a Linear request.
- Identity and normalization: `issue.id` is the Linear issue ID and `issue.native_ref` is currently
  `nil`. Records missing a nonblank ID, identifier, title, or state are dropped from candidate
  pages and fail ID refreshes. State keeps Linear's spelling; integer priorities are preserved and
  other priority values become `nil`; RFC 3339 timestamps are parsed and unusable timestamps become
  `nil`. Labels are trimmed, lowercased, deduplicated, and blanks are dropped; blockers come from
  inverse `blocks` relations.
- Dispatchability: the adapter marks an issue dispatchable only when optional assignee routing
  matches and a `Todo` issue has no non-terminal blocker. The generic scheduler then applies
  active/terminal states, required labels, claims, retries, and concurrency.
- Tool: the Linear adapter advertises `linear_graphql`, accepting either a raw query string or an
  object with nonblank `query` and optional object `variables`. Symphony executes it host-side
  with the session-bound endpoint/token and strips declared token environment variables from the
  Codex child. `project_slug` scopes scheduler reads, not raw tool calls; the tool can access
  whatever the configured Linear token can access.
- Responsibility and errors: `linear_graphql` adds no idempotency key, retry, scope guard, or
  rate-limit policy, so workflows own idempotent mutations and handling provider errors. Read/config
  failures use `{:error, :missing_linear_api_token}`, `{:error, :missing_linear_project_slug}`,
  `{:error, :invalid_linear_endpoint}`, `{:error, :invalid_linear_assignee}`,
  `{:error, :missing_linear_viewer_identity}`, `{:error, {:linear_api_status, status}}`,
  `{:error, {:linear_api_request, reason}}`, `{:error, {:linear_graphql_errors, errors}}`,
  `{:error, :linear_unknown_payload}`, or `{:error, :linear_missing_end_cursor}`. Tool results
  are maps with `"success"`, JSON-string `"output"`, and text `"contentItems"`; invalid
  arguments, missing auth, and transport failures return `"success" => false` with
  `{"error": {"message": ...}}`, while top-level GraphQL errors preserve the response body with
  `"success" => false`.
  For portable reporting, map missing/invalid token, project, endpoint, assignee, or viewer errors
  to `tracker_config` or `tracker_auth`, request failures to `tracker_transport`, non-200 responses to
  `tracker_response` (`429` is `tracker_rate_limited`), GraphQL/unknown payload failures to
  `tracker_payload`, and missing cursors to `tracker_pagination`; logs and tool responses carry the
  human-readable provider detail.

### GitHub Issues adapter

- Config: use `tracker.kind: github` with required `tracker.provider.repo` in `owner/repo` form,
  optional `token` (defaults to `GITHUB_TOKEN` and accepts `$VAR`), and optional `api_url`
  (default `https://api.github.com`, HTTPS only). Set explicit `active_states` and
  `terminal_states`; active entries may be `open` and terminal entries may be `closed`.
- Reads and identity: polling is scoped to the configured repository; `issue.id` is the
  repository issue number, `issue.identifier` is `GH-<number>`, hidden or deleted `404` issues are
  omitted on refresh, and pull requests returned by the Issues API are not dispatchable.
- Tool and auth: `github_api` accepts a relative REST `path` plus optional `params` and JSON
  `body`; Symphony executes it host-side with the session-bound token, removes configured tracker
  credentials and provider authentication aliases from the Codex child, and leaves raw tool access
  limited by that token's GitHub permissions.

### Jira Cloud adapter

- Config: use `tracker.kind: jira` with provider `base_url`, `email`, `api_token`, and required
  `project_key`; the first three default to `JIRA_BASE_URL`, `JIRA_EMAIL`, and `JIRA_API_TOKEN`
  and accept `$VAR`. Set explicit Jira-native `active_states` and `terminal_states`.
- Issues and reads: candidate reads and ID refreshes stay scoped to the configured project and
  requested statuses; `issue.id` is Jira's immutable ID and `issue.identifier` is the issue key.
- Blockers: inward `Blocks` links populate `blocked_by`; issues in Jira's `new` status category
  wait until blockers reach configured terminal states, while in-progress categories keep running.
- Tool: `jira_rest` sends relative `/rest/api/3/` requests host-side with configured Basic auth,
  strips token environment variables from Codex, and can reach whatever the Jira credential can.

### Asana adapter

- Config: use `tracker.kind: asana` with required `tracker.provider.project_gid`, optional
  `endpoint` (default `https://app.asana.com/api/1.0`), and `api_key` (defaults to `ASANA_PAT` and
  accepts `$VAR`); `active_states` and `terminal_states` are project section names.
- Scope: Symphony polls tasks in the configured project, treats their section as state, and omits
  deleted or out-of-project tasks during ID refreshes.
- Tool: `asana_api` sends relative Asana REST requests host-side with the configured auth; Symphony
  strips `ASANA_PAT` and configured token variables from the Codex child, while raw tool calls are
  not limited to the configured project.

### GitLab adapter

- Configure `tracker.kind: gitlab` with `tracker.provider.project_path`, optional `api_url`, and
  `api_key` (default `GITLAB_PAT`); use `opened` and `closed` tracker states.
- Symphony reads project issues by IID and exposes route-safe `GL-<iid>` identifiers.
- `gitlab_api` forwards raw GitLab REST requests with host-side auth and keeps configured tracker
  credentials and provider authentication aliases out of the Codex child.

## Web dashboard

The observability UI now runs on a minimal Phoenix stack:

- LiveView for the dashboard at `/`
- JSON API for operational debugging under `/api/v1/*`
- Bandit as the HTTP server
- Phoenix dependency static assets for the LiveView client bootstrap
- Tracker issue identifiers link to the tracker-provided URL when it uses `http` or `https`

## Project Layout

- `lib/`: application code and Mix tasks
- `test/`: ExUnit coverage for runtime behavior
- `WORKFLOW.md`: in-repo workflow contract used by local runs
- `../.codex/`: repository-local Codex skills and setup helpers

## Testing

```bash
make all
```

Run the real external end-to-end test only when you want Symphony to create disposable Linear
resources and launch a real `codex app-server` session:

```bash
cd elixir
export LINEAR_API_KEY=...
make e2e
```

Optional environment variables:

- `SYMPHONY_LIVE_LINEAR_TEAM_KEY` defaults to `SYME2E`
- `SYMPHONY_LIVE_SSH_WORKER_HOSTS` uses those SSH hosts when set, as a comma-separated list

`make e2e` runs two live scenarios:
- one with a local worker
- one with SSH workers

If `SYMPHONY_LIVE_SSH_WORKER_HOSTS` is unset, the SSH scenario uses `docker compose` to start two
disposable SSH workers on `localhost:<port>`. The live test generates a temporary SSH keypair,
mounts the host `~/.codex/auth.json` into each worker, verifies that Symphony can talk to them
over real SSH, then runs the same orchestration flow against those worker addresses. This keeps
the transport representative without depending on long-lived external machines.

Set `SYMPHONY_LIVE_SSH_WORKER_HOSTS` if you want `make e2e` to target real SSH hosts instead.

The live test creates a temporary Linear project and issue, writes a temporary `WORKFLOW.md`, runs
a real agent turn, verifies the workspace side effect, requires Codex to comment on and close the
Linear issue, then marks the project completed so the run remains visible in Linear.

Run the opt-in GitHub Issues live test with a disposable/scratch repository:

```bash
cd elixir
export SYMPHONY_LIVE_GITHUB_REPO=owner/scratch-repo
export GITHUB_TOKEN=...
SYMPHONY_RUN_GITHUB_LIVE_E2E=1 mix test test/symphony_elixir/github_live_e2e_test.exs
```

Run the opt-in Jira Cloud live test against a disposable project whose credential can browse,
create, comment on, transition, and delete issues:

```bash
cd elixir
export JIRA_BASE_URL=https://your-site.atlassian.net
export JIRA_EMAIL=...
export JIRA_API_TOKEN=...
export SYMPHONY_LIVE_JIRA_PROJECT_KEY=TEST
SYMPHONY_RUN_JIRA_LIVE_E2E=1 mix test test/symphony_elixir/jira_live_e2e_test.exs
```

Run the opt-in Asana live E2E against disposable Asana resources:

```bash
cd elixir
export ASANA_PAT=...
export SYMPHONY_LIVE_ASANA_WORKSPACE_GID=...
# Required only when the workspace is an organization:
# export SYMPHONY_LIVE_ASANA_TEAM_GID=...
SYMPHONY_RUN_ASANA_LIVE_E2E=1 mix test test/symphony_elixir/asana_live_e2e_test.exs
```

Run the opt-in GitLab live E2E against a disposable project:

```bash
cd elixir
export GITLAB_PAT=...
export SYMPHONY_LIVE_GITLAB_PROJECT_ID=...
SYMPHONY_RUN_GITLAB_LIVE_E2E=1 mix test test/symphony_elixir/gitlab_live_e2e_test.exs
```

## FAQ

### Why Elixir?

Elixir is built on Erlang/BEAM/OTP, which is great for supervising long-running processes. It has an
active ecosystem of tools and libraries. It also supports hot code reloading without stopping
actively running subagents, which is very useful during development.

### What's the easiest way to set this up for my own codebase?

Launch `codex` in your repo, give it the URL to the Symphony repo, and ask it to set things up for
you.

## License

This project is licensed under the [Apache License 2.0](../LICENSE).

## Native control foundation

`SymphonyControl.Application` supplies a PostgreSQL repository and read-only health
components. Its standalone interface accepts optional `http: [port: 4328]` to
serve control health, identity and individual project GET routes on `127.0.0.1`;
HTTP is off by default. `GET /api/v1/projects/:id` reuses the existing project-read
authorization and returns a versioned field whitelist with UTC timestamps. Project
responses are not cached. The listener includes no dashboard. Task3 adds cookie
authentication through explicit server options for owned HTTPS tests; production
auth remains disabled and default Access denies. It is a
component interface, not a production runner or change to dashboard port 4327.
The default legacy application and agent supervisor reject control
enablement or access to its credentials before starting agent children. Individual
Codex, workspace hook and SSH launch paths enforce the same restriction, including
a retained URL in Linux's initial `/proc/self/environ`. Missing startup-environment
evidence fails closed; platforms without this Linux evidence are not admitted.
A verified OS/container identity boundary is required before control and agents
can operate together. Parent Repo configuration remains intact.

Credential-free children lose `SYMPHONY_CONTROL_DATABASE_URL` and receive
`SYMPHONY_CONTROL_ENABLED=false`, including explicit overrides and shell/profile
initialization. This filtering alone does not provide process isolation.
Control component tests require isolated PostgreSQL through `SN004_TEST_PG_SOCKET`.
See [the configuration and test guide](../docs/engineering/control-foundation.md)
for startup, migration, health, authorization and test limits. Default startup
keeps control disabled; production tracker and Authentik acceptance remain separate.

The separately admitted 2026-10-06 dependency-context continuation adds43 tests:
scoped structural telemetry/log checks over real signed-token HTTPS malformed responses
and scanner controls. Baseline and candidate94/0 pass; makeall507/0/6, coverage100%,
strict Credo and Dialyzer pass. No semantic product RED was reproduced; oidc.ex is
unchanged. [Complete licensed dependency source context](../docs/engineering/oidcc-3.9.0-review-context.md) binds the actual
selected Oidcc/Telemetry files; Oidcc selected Hex-source equivalence is verified,
full Telemetry archive equivalence is NOT_VERIFIED. Existing token_type/unknown-field
acceptance is classified explicitly; no stricter protocol contract is added.
Actual client model/effort/speed remain UNKNOWN. History and frozen controls are preserved;
new independent review/trusted native/live acceptance remain separate, auth stays disabled.


TLS fixture attempt20261007 stopped **BLOCKED repair_cycles_exhausted (2/2)**.
Cloud baseline507/0/6,100%; uncommitted candidate509/1/6,100% exposes a charlist/binary
fixture failure in the new positive POST control. The1500ms/<1700ms deadline and
negative TLS-stage/latePOST assertions remain. Full gates/commit/push/newHEAD are
NOT_RUN; auth remains disabled. See [actual evidence report](../docs/engineering/authentik-project-access.md).


AUTH-TLS-SOURCE-20261008-NEXT recovered the exact historical TLS draft and fixed
its real socket binary-mode failure. Final Config/OIDC96/0, bounded TLS/positive/
setup-pause controls, strict gates, make all509/0/6 and fixed-seed confirmation
509/0/6 passed with coverage100%. Earlier650ms/readiness failures remain in the
engineering report; cause UNKNOWN. New attempt2/2; publication readback is in
workpad33. Independent review/native check/live acceptance remain NOT_RUN; auth
stays disabled and historical native HOLD is open.


SN005-DEADLINE-POST-BARRIER-20261008 replaces the650ms test's pre-token timing race
with a reference-bound acknowledgement of a complete validated HTTPS POST. Its
response is held past the SAME original deadline; the850ms bound, onePOST and
caller/worker/provider cleanup remain. A signed positive control and separate
discovery/JWKS shared-budget regression pass. Final Config/OIDC101/0; fixed-seed
coverage and make all514/0/6,100%, all stage exits0. TLS1500ms/<1700ms/latePOST0
controls remain intact. Actual commands/hashes and preserved failure history are
in the engineering report. Closed old source attempts (including budget_violation)
and native422 HOLD remain unchanged. Independent new-HEAD review/trusted/live
acceptance remain separate and NOT_RUN; production auth stays disabled.


SN005-OWNER-DOWN-OBSERVER-41D840 repairs the fixture cleanup regression: a surviving
observer receives the actual reference/stage/provider-bound completion outcome.
Owner death must report owner_down; no release must report abandoned. The old
test passed with DOWN handling removed; the repaired test rejects that mutant,
and both cases pass after exact-byte restoration. Config/OIDC101/0 and one full
make all514/0/6,coverage100%,all stage exits0 passed. This is prior closed2/2 plus
one separately admitted additional cycle1/1; historical reports remain. The650ms
POST/shared-budget and stagedTLS controls are byte-unchanged, auth disabled and
native HOLD remains. New independent review/trusted/live acceptance are NOT_RUN;
actual commands, mutation hashes and owned PostgreSQL cleanup are in the report.
# Task2 local auth state

`SymphonyControl.Auth.Store`, `Actor` and `TokenVault` add the local state contract;
they are not wired into the production supervisor or HTTP authentication pipeline.
The auth migration is `20261004000000_create_control_auth.exs`. Health accepts the
legacy project-only schema with auth disabled, or the exact project+auth schema with
all constraints. No migration runs automatically.

For owner-provisioned disposable PostgreSQL only, set the non-production test
bindings `SN005_TEST_PG_SOCKET`, `SN005_TEST_PG_PORT`, `SN005_TEST_PG_USER`,
`SN005_TEST_PG_DB`, `SN005_TEST_KEY_ROOT`; retain the existing owned SN004 fixture
bindings for legacy tests. The key root must be private and owned by the test identity.
Run `mix test test/symphony_control/auth/store_test.exs
test/symphony_control/auth/vault_test.exs test/symphony_control/auth/schema_test.exs
test/symphony_control/foundation_test.exs test/symphony_control/schema_contract_test.exs
--trace`, then `make all`. Keep PostgreSQL alive through all dependent processes.
Keys and test canaries are synthetic; no production credentials or shared database
are used. See the root engineering report for time, transaction and recovery semantics.

The PR97 repair starts a single 750ms monotonic budget before validation, key IO,
serialization or SQL. Queries/transactions use at most min(500ms, remaining), with
queueing and query logging disabled. A late cleanup reply cannot release a result;
the caller also checks the budget after its final bounded `Clock.now(timeout)`.
Possible-write timeouts return `unknown_outcome`; read timeouts return
`dependency_unavailable`. Do not retry an unknown write outcome automatically.

Use snapshots from the trusted `SymphonyControl.Auth.Clock`, including its new
`sample_valid` field. The existing UTC/monotonic/epoch fields and `now/0` and
`start_link/1` remain available. Stable native time-offset sampling brackets the UTC
read; discontinuity or uncertainty invalidates that sample and rotates the epoch.
Store rejects unsupported/stale-epoch snapshots and checks both strict expiry
bounds again before releasing a handle, plaintext, Actor or rights. Reads never
renew lifetimes. Permission decisions join the session, user, exact identity and
requested grant in one statement snapshot; an ordinary later revocation is a
separate event.

Key references must name stable, owner-provisioned regular files with exactly32
bytes. Vault checks the opened descriptor, uses raw caller-owned IO, and projects
crypto/key exceptions to fixed errors. The path check does not prove safety against
concurrent filesystem replacement or arbitrary stalled kernel IO; these tests do
not establish a hard realtime OS guarantee. Controlled test resources are bounded
and released, and no background file IO server is created for the key.

Include `test/symphony_control/auth/clock_test.exs` in targeted auth checks. Late
reply controls use a VM-local OTP breakpoint on existing Task code, without
replacing installed tools or adding dependencies. Production callbacks, auth
activation, HTTP integration and independent acceptance remain outside this repair.

PR97's remaining F2 repair keeps private validity through the final caller decision.
Clock adds a floor-conservative native anchor, its unit and local producer identity;
now/0, now(timeout) and start_link/1 remain compatible. Store accounts for the age
of that measured sample until it checks the original deadline and remaining
flow/session/credential lifetime together. Delayed delivery/queued processing
cannot renew the lifetime. Real committed consumption/insertion remains, while
expired results yield no plaintext/handle/Actor/rights and actor_current? is false.
No schema or Store API signature changes, retry, epsilon or TTL extension. Tests
freeze the last sample before a barrier and use an explicit native time mapping.
See the new F2 section in the engineering report. Independent exact-HEAD review
is pending; authdisabled/trusted/native/live/HOLD boundaries remain unchanged.


## Task3 browser/session HTTP fixture

Task3 composes the accepted Oidc, Store and native Clock APIs without changing them.
`Login.begin/3` commits a browser-bound random state/nonce/PKCE flow before redirect;
`Login.finish/6` consumes it before its single real exchange and confirms session insertion
or rotation before returning an opaque handle. HTTP handlers start one absolute
five-second budget before the first body/limiter/Clock wait and pass it through compatible
internal arities. Login retains both issue axes and validates a session through Store in
its actual caller, with no further dependency wait after that acceptance. Both use that budget;
the stricter Store bounds remain 750ms. Late/expired results and unknown COMMIT outcomes
produce refusal, with no retry or compensation. Arbitrary caller/VM suspension after the
last synchronous acceptance decision is not a hard realtime guarantee.

Cookies are `__Host-symphony-browser` and `__Host-symphony-control`, Secure/HttpOnly,
SameSite=Lax, Path=/, with no Domain. The fixture has an actual loopback TLS ingress and
private test CA; the product never substitutes insecure cookies for loopback HTTP.
GET login/callback, POST denied logout/backchannel, 405+Allow, 404 and no-store are tested.
Callback code/state and auth bodies are bounded at 4096/256 bytes and 32KiB. Local counters
are charged to the exact opaque binding allocated before the first login. Auth ingress
supports HTTP/1.0/1.1 no-body or a single decimal Content-Length at most32768; actual bytes
are checked during reads of at most1KiB with the remaining absolute timeout. Transfer-Encoding,
ambiguous/oversized/unfinished framing closes safely before body drain or expensive work.
Unsupported HTTP/2 auth streams reset before reading or response-window waits; public health
remains independent. Fully consumed valid bodies preserve keep-alive even on400/403/429.
Pinned Bandit advisories remain a separate release dependency disposition for broader scope.
Local counters
limit login to 5/min per binding and 60/min globally, callback/backchannel to a shared
120/min global budget, with at most 1000 entries and lazy expiry cleanup.

`SYMPHONY_CONTROL_AUTH_CONFIG` names a nonsecret JSON file (at most 32KiB). Its string keys
must exactly match the closed Auth.Config bindings; unknown keys, TLS material, callback
or module selectors are rejected. Load happens in runtime configuration before control
startup. Explicit unreadable/malformed config raises fixed `invalid_control_auth_config`,
clears stale configuration and refuses standalone admission; an existing Router cannot
use the prior binding after that invalid load. Missing env is intentionally absent.
Exact callback/backchannel paths must be canonical, distinct, non-root and outside fixed
login/logout, public health and protected project/identity routes. The successful LOGIN
callback returns to the fixed `/`. The separate operator-bound `post_logout_uri` retains
its exact Config-valid HTTPS same-origin value, including non-root paths; it is not an
additional callback/backchannel route or a Task3 landing-page implementation.
Valid distinct custom paths keep their exact redirect URI. Valid config is stored as unverified;
Config.activation_allowed? remains false, so environment configuration cannot activate
production auth. Explicit trusted `auth: [config: cfg]` supervisor opts start Clock, Access
and the limiter after Repo; the default eligibility callback still denies. Only owned
tests provide an explicit callback that actually calls their HTTPS provider. Existing
project/platform Domain authorization remains separate and defaults to deny.

Run with own disposable PostgreSQL, the SN005 fixture bindings documented above, and
own dependencies and separate per-environment build directories plus MIX_HOME/HEX_HOME
(including own core/project PLTs). Do not share one MIX_BUILD_PATH between dev and test:

```sh
mix test test/symphony_control/auth/login_http_test.exs test/symphony_control/auth/environment_test.exs --trace
mix test test/symphony_control/auth/http_body_test.exs test/symphony_control/auth/request_context_test.exs test/symphony_control/auth/routes_test.exs --trace
mix test test/symphony_control/project_read_http_test.exs test/symphony_control/standalone_http_test.exs test/symphony_elixir/control_boundary_test.exs test/symphony_elixir/control_environment_test.exs --trace
mix test test/symphony_control/auth test/symphony_control/foundation_test.exs test/symphony_control/schema_contract_test.exs --trace
# from the repository root, in the same prepared own Mix environment:
make -C elixir all
```

Auth config/secret-reference variables are removed from synthetic children, and both
control/auth markers are forced false after shell initialization. Active control/auth
workers or loaded config block agent startup before child creation or secret reads.
Environment filtering does not prove production file/proc isolation across UIDs; that
remains Task5. No actual agent/model engine is used by these boundary fixtures.
The [engineering report](../docs/engineering/authentik-project-access.md) retains initial
failures, budget history, exact source and the separate acceptance gates.


## R6/N1 effective selection representation (2026-10-14)

`AuthorizerBindings.resolve/1` returns the managed Auth.Authorizer only after
a bounded current-lifecycle lookup. Outside a confirmed managed mode, it returns
the current raw Application default. The raw project_authorizer and
runtime_identity_authorizer keys are never temporary managed storage: a raw
get_env during an active generation still shows the operator/default value.

The existing component owns generation/current writer and monitors the
supervisor owner. Access restarts retain the generation and replace only the
writer; a stale generation or writer cannot release the current binding.
Confirmed release clears owned state only. A module-owned persistent sentinel
contains component pid/incarnation, not authority. Pending startup, unexpected
component death, malformed context, queued replies from an ended incarnation
and lookup failure deny; they cannot fall back to a permissive base. Normal
owner retirement permits legacy selection. A restarted binding component stays
pending until explicit install; it does not recreate a lost grant automatically.

An explicit legacy fixture callback is not managed production admission.
Concurrent direct put_env/delete_env calls remain ordinary trusted base edits,
not a revisioned runtime API. The latest completed edit survives cleanup,
including equal values and ABA sequences. Resolver module selection never
replaces the existing Actor/session/current-grant checks, no public selection
endpoint exists, and production auth activation stays disabled.

The old read->completed independent base write->old restore schedule failed6/6;
new scoped controls passed16/0, including216 release/owner-shutdown schedules,
cold restart rights checks and production-supervisor topology. These are author
causal controls, not the final T1/T2/T3 gates or historical failure disposition.
Final results, first failures and exact source are in owning #33. A specific
compatibility decision for two inherited R1 identity-barrier fixture setups was
pending when this dated candidate note was written; their assertions are intact.

## Identity lifetime fixture adaptation — R6/N1 cycle2/2 (2026-10-14)

Only the owning identity-barrier tests and paired controls explicitly combine
`task4: true`, `eligibility_confirm: &SymphonyControl.Auth.Eligibility.confirm/4`
and an initial real `runtime_identity_authorizer: Auth.Authorizer`.
AuthHttpFixture accepts only that exact external capture in the new combination;
anonymous forwarding and permissive callbacks are rejected. Ordinary managed
Task4 and prior default/legacy modes keep their selection behavior.

The existing explicit-fixture path owns an intentionally inactive binding.
The tests check config/callback identity, `Access.task4?`, actual cached receipt,
local private witness and original request binding while the real authorizer's
successful request waits before snapshot. Both expiry axes retain400ms lifetime,
1500ms barrier/1800ms existing helper fail-safe/2000ms await and every denial,
private-data and cookie assertion. Timely release returns the real four-field
snapshot; removal of the current platform grant denies before the barrier.
Unchanged managed lifecycle controls independently cover active selection,
foreign defaults, two Access restarts and current rights revocation.

Scoped24/0 is author evidence, not final qualification or independent acceptance.
Final commands/inputs/results and later docs-only seals are in owning #33.
All product lib/AuthDbFixture bytes remain158529de; historical failures, original
requirements and native/trusted/live/Bandit/Task5 boundaries remain unchanged.

Continuation final executable results: T1 67/1 exit2, T2 465/0 exit0. The two
identity barriers and paired controls passed in both full suites. T1 failed at
an unchanged standalone initial-missing-connection identity request with
Req.TransportError before any status; cause unresolved. T3 NOT_RUN_T1_RED.
Broader style remains RED on10 frozen158529de remarks. Python12/11 and final
static/body results do not close those holds. This result-only docs/MANIFEST
seal follows the tested executable freeze; exact inventories are in #33.


2026-10-15 — T4-N2/P1 + STYLE author candidate: effective authorizer decisions
carry a unique lifecycle revision through raw selection and callback acceptance
in Projects/RuntimeIdentity. Callbacks keep their original request process and
HTTP deadline; lookup250ms remains a separate delivery bound. Operator defaults,
legacy/graceful lifecycle, current grants and protected identity controls remain.
Fresh final T1 92/0, T2 490/0, ordinary make856/0/6 unchanged skips with100%
coverage/Dialyzer0 errors, strict lint and Python12/11 passed. First make failed
coverage99.82%; cycle2 removed duplicate inner callback catches, retaining the
original consumer error boundaries. First failures and historical results remain.
Prepared-cache isolation was breached during early setup; pre-bytes and some old
exit/reap observations remain UNKNOWN. Author GREEN does not erase that hold.
Independent review of the new exact HEAD is required. NOT_ACCEPTED_FOR_TASK5 /
NOT_RELEASE_APPROVAL / DO_NOT_MERGE. Full causal matrix, style-only equivalence,
input/output seals and limits are appended to docs/engineering/authentik-project-access.md.


2026-10-15 — R6-TIME author candidate adds a fresh closing native-time check after
complete binding-state validation. Selection retains its original lookup limit;
callback acceptance retains only the original HTTP deadline, with nil context
unchanged. Descriptor/lifecycle/defaults and both consumers are byte-preserved.
Actual direct RuntimeIdentity/Projects causal controls: old4 semantic RED plus4
positive controls; fixed8/0. Standard native regressions run without the one-off
observer. Fresh T1 98/0,T2 496/0,ordinary make862/0/6 with100% coverage and
Dialyzer0,strict lint,T4 Python12/11 passed. Full causal times/diff/source/limits
and first failures are appended to docs/engineering/authentik-project-access.md.
Prior prepared-cache process hold and UNKNOWN remain; current preparation004
also had inherited HOME despite own cache paths, then corrected/rechecked.
This is not independent acceptance or Task5/release approval. DO_NOT_MERGE.

### PR99 B/C harness, 2026-10-15 — WIP / STYLE_HOLD

The owner-approved staged TLS expectation separates EARLY_DEADLINE_NO_POST from
FULL_TLS_STAGE_CONTROL. Both original1500/<1700 negatives retain delay200,
dispatch600, SNI700 and adverse setup800; early absent SNI is recorded explicitly.
Separate real5000 positives for setup0/800 require accept1/SNI1/POST1 and600/700
measured gaps. The opt-in causal gate precedes accept/dispatch; no fake stage
or warmup client supplies missing coverage. Default fixture delays remain intact.
F5 retains real FIFO850/ENXIO400, both Vault refusals and Store750/elapsed<800.
Its local Python supervisor confirms child startup, shares one3000ms cleanup
budget, classifies nonzero/cancellation, actually waits/reaps and removes FIFO
through nested finally without replacing a primary failure.

Scoped selection (all six OidcTest and five StoreRepairTest cases are enumerated
in the engineering evidence):
`mix test test/symphony_control/auth/oidc_test.exs test/symphony_control/auth/store_test.exs --only bc_harness --trace --seed 381068 --max-cases 1`.
Author final scoped11/0, T1 98/0 and T2 503/0; Python12/0 and11/0 after runtime.
Ordinary `make -C elixir all` was run once and FAILED at strict Credo: three
long lines and two complexity findings in the new harness. Build/format/specs
passed; coverage, ordinary full tests/skips and Dialyzer were NOT_RUN.
Two harness cycles were used; no further code change or make rerun was made.
The ordinary make concurrency/seed/quality rules remain unchanged.
[Exact contract, commands, UTC/exits/seals and cleanup](../docs/engineering/authentik-project-access.md).
This explicitly changes the prospective test interpretation, never the old run2
FAILED result. A_UNKNOWN/process holds and independent review/qualification
remain; NOT_ACCEPTED_FOR_TASK5 / NOT_RELEASE_APPROVAL / DO_NOT_MERGE.
