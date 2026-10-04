# Native control foundation (SN-004)

This increment adds a PostgreSQL repository, the project identity root, explicit
migrations, health endpoints and an authorization boundary for runtime identity.
It does not complete the native tracker, Authentik, durable execution or product
deployment acceptance. The existing Symphony scheduler remains unchanged.

The [canonical requirements excerpt](control-foundation-requirements.md) copies
the complete assigned SN-004 task, its ARCH/DATA requirements and acceptance rows,
and selected invariant/security context with the canonical source hashes. This
small source subset supplies readable review context; the canonical specification
and backlog remain authoritative. It records no implementation or acceptance result.

## Startup and migrations

Control is disabled by default. The legacy application starts its agent scheduler
and cannot safely share its process identity with the control database. Setting
`SYMPHONY_CONTROL_ENABLED=true` configures control and requires a dedicated
`SYMPHONY_CONTROL_DATABASE_URL`, but the default application and direct agent
supervisor startup reject that combination with
`{:error, :control_agent_runtime_unsupported}` before starting their children.
No supported production control-and-agent composition is provided by this
foundation. A separately verified OS/container identity boundary is required
before that combination can be enabled (ARCH-04/SEC-02).

The same admission check protects individual Codex, workspace hook and SSH
launches, including direct/custom-named agent supervisor startup and its restart
callback. Configured control, a retained Repo URL, a live control supervisor,
and a URL in the current or initial process environment each prohibit a launch.
On Linux the check reads only `/proc/self/environ`: deleting the current variable
does not remove the initial bytes that a same-UID child could read. Unreadable or
missing startup-environment evidence returns
`{:error, :credential_environment_unverifiable}`. Platforms without this Linux
proc evidence are not admitted; the existing macOS build target is not evidence
of support for agent execution. Guards never erase parent Repo configuration or
include database values in their errors. Existing after-run/before-remove cleanup
contracts still ignore hook failure; the blocked hook itself never executes.

Credential-free legacy launches remove the URL and force
`SYMPHONY_CONTROL_ENABLED=false` in System.cmd and Port environments, even when
an explicit override attempts to enable it. Codex, local hooks and remote SSH
commands restore this policy after shell/profile initialization. Ordinary
variables and existing tracker credential filtering are preserved. Hooks needing
other credentials must receive separately scoped values. Environment filtering
is defense in depth and does not constitute same-UID process isolation.

The standalone `SymphonyControl.Application` and isolated PostgreSQL component
fixtures exercise repository/health behavior without admitting agent execution.
They are trusted developer components, not a control-only production runner or
proof of isolation. Use the new product's database and role; never reuse another
application's database, credentials or writable state. No database connection is
started by the control component when disabled.

Mix embeds `config/runtime.exs` in an Elixir escript, evaluates it at launch,
merges it over build-time configuration and installs merged values with
`persistent: true` before invoking the CLI. `app: nil` suppresses automatic
application startup, not configuration loading. The CLI helper retains its
explicit environment-validation contract; its normal startup callback then
applies the admission check described above.

This ordering is defined in [Mix 1.19.6 `escript.build` source](https://github.com/elixir-lang/elixir/blob/v1.19.6/lib/mix/lib/mix/tasks/escript.build.ex)
by `gen_main/5`, `main_body_for/4`, `load_config/1` and `start_app_for/1`.
`Application.put_env/3` alone is not persistent, but the normal generated
Elixir wrapper has already persisted the runtime override. Omitting that merge
can reproduce a reset on `Application.load/1`; that is a negative-control
scenario, not evidence that the normal packaged entry point resets the flag.

Migrations are explicit: `mix ecto.migrate -r SymphonyControl.Repo`. Use a separate
migration role in that invocation; the running application does not need schema
ownership. Startup and health checks never migrate or create migration tables.
The initial migration creates `projects` with a UUID identity, unique nonblank
key, nonblank name, positive revision and UTC timestamps. Memberships, registry
operations and bindings are separate SN-005/006 work. The complete DATA-02 schema
is developed with its owning domain tasks.

## Internal project domain

`SymphonyControl.Projects` operates on the existing identity-root schema:

| Function | Contract |
| --- | --- |
| `create_project(actor, %{key: key, name: name})` | Creates a UUID, revision 1 and UTC timestamps on the server; accepts only the two atom-keyed text fields. |
| `get_project(actor, uuid)` | Returns the persisted `SymphonyControl.Project` or a typed error. |
| `rename_project(actor, uuid, expected_version, name)` | Changes only name and increments revision with a database optimistic lock. Stale and exhausted revisions conflict. |

Each returns `{:ok, project}` or `{:error, %SymphonyControl.Error{}}`. Keys are
case-sensitive opaque values; text must be valid UTF-8, nonblank and NUL-free.
No case folding or trimming rewrites submitted names/keys. Caller-supplied UUID,
revision, timestamp or other fields are rejected. A rename cannot change a key.
The integer revision never wraps after 2147483647.

The server configures `:project_authorizer`, a module implementing
`authorize(actor, action, scope)`. Only `:ok` permits the operation. Creation
requires `:project_create` on `:platform`; reading and renaming require
`:project_read`/`:project_rename` on the normalized project UUID. Missing,
malformed, denying or throwing authorizers fail closed before database effects.
The actor must come from trusted server authentication. The fixture authorizer
is test-only; this callback is not Authentik, membership/RBAC acceptance or an
agent capability. No new HTTP route or production authorizer is exposed.

Errors contain only `code`, safe `fields` and an optional `reference_id`:
`invalid_input`, `forbidden`, `not_found`, `conflict`,
`dependency_unavailable`, `unknown_outcome`. They do not expose submitted values,
SQL or driver exceptions. Database query calls have a 500 ms timeout; a 750 ms
outer database deadline also bounds stalled checkout. Authorization and input
validation precede that database deadline, so it is not an end-to-end API limit.
The driver and supervisor may reconnect; the domain never automatically retries
a mutation. A confirmed stopped Repo is unavailable. Unconfirmed database writes
return `unknown_outcome` with the generated/known project UUID; a read failure
returns `dependency_unavailable`. Readback can show current persisted project
state, but neither absence nor a matching name proves a particular write's
outcome or makes retry safe. These are not idempotency or durable operation receipts.

Calls own their database work and must not be composed inside another Repo
transaction. The context does not accept execution commands, perform migrations,
open admission or implement the future issue/activity/outbox transaction. It
assumes the supported migrated schema; readiness remains a separate required
gate before exposing any product service. Project memberships, descriptors,
bindings, ACLs and the complete registry remain SN-005/006 work.

## Observable contracts

| Endpoint | Result |
| --- | --- |
| `GET /health/live` | 200 only while the control supervisor responds; otherwise 503. Body contains only `live`. |
| `GET /health/ready` | 200 only with a reachable repository, exact supported migration versions and the required projects schema contract. Otherwise 503 with `ready`, `database`, `schema` booleans. |
| `GET /api/v1/control/identity` | 403 by default. Disclosure requires the configured server authorizer and the server's `current_actor` assignment. Query parameters do not supply authorization. |

Each individual SQL probe has a 500 ms outer timeout, including connection
checkout. Liveness and SQL probes run sequentially, so 500 ms is not an
end-to-end readiness deadline. Read-only catalog checks verify the initial
projects table's required column types, timestamp precision, NOT NULL/defaults,
UUID primary key, immediate full unique key index and validated nonblank/positive
CHECK definitions. Missing, partial, invalid or weakened definitions block
readiness even when the migration version still matches. This is the supported
initial migration contract, not an audit of every database object; a future
supported migration must update that contract. CHECK/default expressions use
PostgreSQL's non-pretty deparser output. An unsupported representation fails
closed rather than asserting equivalent semantics.
Readiness is read-only and does not open execution admission.
Database failure does not by itself make the control supervisor dead. SQL,
connection strings and exception details are not returned in health responses.

`runtime_identity_authorizer` is an application-configured module implementing
`authorize(actor, :runtime_identity_read)`, returning `:ok` or a denial. No
production authorizer or substitute password/Basic Auth is supplied here.
SN-005 must provide the authenticated actor and real Authentik authorization;
the test authorizer is test-only and does not certify SSO integration.

The authorized identity response has schema version 1 and `commit_sha`,
`image_digest`, `config_sha256`. Supply these through
`SYMPHONY_CONTROL_COMMIT_SHA`, `SYMPHONY_CONTROL_IMAGE_DIGEST` and
`SYMPHONY_CONTROL_CONFIG_SHA256`. The config hash identifies a reviewed
non-secret configuration manifest. Missing or malformed hashes are `UNKNOWN`.
These declarations do not replace independent image/config readback.

## Isolated PostgreSQL tests

The control tests require a real disposable PostgreSQL database named
`sn004_test`, role `sn004_fixture`, port 55474 and a private Unix socket directory
passed in `SN004_TEST_PG_SOCKET`. No default host or shared database fallback is
used. Tests create separate randomly named schemas. Database-loss tests disable
connections to that fixture database and restore them afterwards; never point
this test configuration at an existing database.

Run as an unprivileged user with Elixir 1.19/OTP 28 and PostgreSQL tools available:

```bash
(
  set -eu
  SN004_FIXTURE_ROOT="$(mktemp -d)"
  printf '%s\n' "$SN004_FIXTURE_ROOT"
  mkdir -m 700 "$SN004_FIXTURE_ROOT/socket"
  initdb -D "$SN004_FIXTURE_ROOT/data" -U sn004_fixture \
    --auth-local=trust --auth-host=reject --no-locale --encoding=UTF8
  trap 'pg_ctl -D "$SN004_FIXTURE_ROOT/data" -m fast -w stop' EXIT
  pg_ctl -D "$SN004_FIXTURE_ROOT/data" -l "$SN004_FIXTURE_ROOT/postgres.log" \
    -o "-c listen_addresses='' -c unix_socket_directories='$SN004_FIXTURE_ROOT/socket' -c unix_socket_permissions=0700 -c port=55474" -w start
  createdb -h "$SN004_FIXTURE_ROOT/socket" -p 55474 -U sn004_fixture sn004_test
  export SN004_TEST_PG_SOCKET="$SN004_FIXTURE_ROOT/socket"
  cd elixir
  mix test --no-start test/symphony_control
  make all
)
```

The trap stops only that fresh cluster; evidence/data are retained in the printed
temporary path for investigation. No model turn, production service, TCP listener,
Docker socket or deployment is involved in this fixture.

`schema_contract_test.exs` migrates real isolated schemas and changes required
types, nullability, defaults, primary/unique keys and CHECK constraints. Each
fault must retain liveness and database connectivity while returning readiness
false and HTTP 503. Existing migration, connection-loss and timeout tests remain
applicable.

## Configuration-load tests and limits

`runtime_config_test.exs` has separate checks for the injected CLI callback and
fresh-VM application loading. The latter evaluate the real project configuration
files, merge them using `Config.Reader.merge/2`, set each value persistently as
Mix 1.19.6 does, call `RuntimeConfig.configure/0`, and load (not start) the OTP
application. They cover enabled and disabled control, database/identity
preservation, and an intentionally omitted runtime merge as a negative control.
No services, database connections or model turns are started by these fixtures.

These are configuration-load **unit tests**, not execution of the generated
escript or proof of a deployed image. Artifact-level entry-point and functional
acceptance remain required. The previous source-review P1 assumed an omitted
runtime merge; source inspection and the configuration-load tests do not support
that premise for the documented Mix 1.19.6 path. This does not grant release
approval or replace independent exact-HEAD review and trusted checks.

## Credential regression tests

`control_environment_test.exs` launches real credential-free fixture children,
including a marked shell profile that reintroduces the URL and enablement flag.
The final child has no URL and control is false. A trusted child evaluates the
real `config/runtime.exs` with control disabled while its parent's Repo remains
configured; it does not start the application or a database connection.

`control_boundary_test.exs` uses only synthetic credentials. In a fresh VM started
with a synthetic URL, an owned same-UID probe reads only that VM's known PID
under `/proc` and demonstrates that the initial canary remains readable after
the current variable is deleted. The product SSH launch and supervisor callback
then refuse execution. Tests also cover direct startup, live control, local
hooks, remote launch rejection, preserved cleanup, and missing/unreadable startup
evidence. This proves rejection of the unsafe combination, not OS isolation,
packaged entry-point acceptance or production runtime behavior.

## Release boundary

Fresh independent review and protected verification of the new exact HEAD are
still required. The completed PR13 verifier is a frozen one-shot target and must
not be reset or reused. No Coolify configuration or runtime activation is part
of this change. A healthy compatible rollback predecessor is not yet established.
