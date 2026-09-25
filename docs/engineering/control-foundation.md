# Native control foundation (SN-004)

This increment adds a PostgreSQL repository, the project identity root, explicit
migrations, health endpoints and an authorization boundary for runtime identity.
It does not complete the native tracker, Authentik, durable execution or product
deployment acceptance. The existing Symphony scheduler remains unchanged.

## Startup and migrations

Control is disabled by default. `SYMPHONY_CONTROL_ENABLED=true` enables its
supervisor and requires `SYMPHONY_CONTROL_DATABASE_URL` from a dedicated runtime
secret reference. Use the new product's database and role. Do not reuse another
application's database, credentials or writable state. No database connection is
started by the control component when disabled.

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

Each health interaction has a 500 ms timeout, including connection checkout;
no individual SQL probe waits indefinitely. Readiness is read-only and does not open execution admission.
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

## Release boundary

Fresh independent review and protected verification of the new exact HEAD are
still required. The completed PR13 verifier is a frozen one-shot target and must
not be reset or reused. No Coolify configuration or runtime activation is part
of this change. A healthy compatible rollback predecessor is not yet established.
