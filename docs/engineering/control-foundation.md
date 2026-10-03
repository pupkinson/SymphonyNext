# Native control foundation (SN-004)

This increment adds a PostgreSQL repository, the project identity root, explicit
migrations, health endpoints and an authorization boundary for runtime identity.
It does not complete the native tracker, Authentik, durable execution or product
deployment acceptance. The existing Symphony scheduler remains unchanged.

## Startup and migrations

Control is disabled by default. `SYMPHONY_CONTROL_ENABLED=true` enables its
supervisor and requires `SYMPHONY_CONTROL_DATABASE_URL` from a dedicated runtime
secret reference. Mix embeds `config/runtime.exs` in an Elixir escript, evaluates
it at launch, merges it over the build-time configuration and installs the
merged values with `persistent: true` before invoking the CLI. `app: nil`
suppresses automatic application startup; it does not suppress configuration
loading. The CLI helper retains its explicit environment-validation contract.
Use the new product's database and role. Do not reuse another application's
database, credentials or writable state. No database connection is started by
the control component when disabled.

The database URL remains available to the control repository in the Symphony
process. It is removed from the environment of Codex, all local workspace hooks
and local SSH clients, including explicit SSH command environment overrides.
Codex launch commands and local hooks also unset the variable after shell startup,
so a shell profile cannot reintroduce it into the launched agent or hook. Ordinary
environment variables and the existing tracker credential filtering are preserved.
This environment boundary does not grant repository scripts database access;
configure any required hook credentials separately with their own scopes.

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

## Observable contracts

| Endpoint | Result |
| --- | --- |
| `GET /health/live` | 200 only while the control supervisor responds; otherwise 503. Body contains only `live`. |
| `GET /health/ready` | 200 only with a reachable repository, exact supported migration versions and the required project relation columns. Otherwise 503 with `ready`, `database`, `schema` booleans. |
| `GET /api/v1/control/identity` | 403 by default. Disclosure requires the configured server authorizer and the server's `current_actor` assignment. Query parameters do not supply authorization. |

Each individual SQL probe has a 500 ms outer timeout, including connection
checkout. Liveness and SQL probes run sequentially, so 500 ms is not an
end-to-end readiness deadline. The schema check verifies migration versions
and the availability of required columns, not their types, indexes or constraints.
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

## Release boundary

Fresh independent review and protected verification of the new exact HEAD are
still required. The completed PR13 verifier is a frozen one-shot target and must
not be reset or reused. No Coolify configuration or runtime activation is part
of this change. A healthy compatible rollback predecessor is not yet established.
