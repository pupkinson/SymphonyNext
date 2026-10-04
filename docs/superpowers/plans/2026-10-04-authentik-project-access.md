# Authentik Project Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Вход через существующий Authentik и чтение проекта только человеком с текущей локальной membership, с проверенным отзывом доступа не позднее60секунд.

**Architecture:** Confidential OIDC Code + PKCE завершается внутри отдельного control process/UID boundary. PostgreSQL хранит одноразовые flows, локальные identities/memberships и отзываемые сессии; браузер получает opaque handle. Существующие Projects/RuntimeIdentity callbacks получают только серверный actor, заново проверяют сессию и локальные права и закрывают доступ при неизвестной IdP eligibility.

**Tech Stack:** Elixir1.19.x/OTP28, существующие Bandit/Plug, Ecto/Postgrex/PostgreSQL, Req/Jason. Oidcc — кандидат протокольной библиотеки; наблюдение3.9.0 в спецификации не является установленной/проверенной зависимостью. Task1 фиксирует exact version/provenance/mix.lock до реализации adapter; собственный JWT verifier не создаётся. Token vault использует стандартный OTP authenticated encryption adapter.

**Spec:** [2026-10-04-authentik-project-access-design.md](../specs/2026-10-04-authentik-project-access-design.md), SHA256 `49f4a2eda5c56b83b355f26aa69c92de4c84e549afad13b9c1c885dc9ea31c41`, commit `91df044bf458a3576a12fcb8f4e32be12bc9d524`. Владелец подтвердил этот документ 2026-10-04T13:30:55Z. Оба документа читаются вместе.

## Global Constraints

- `openid/profile/email`; без `offline_access` и `goauthentik.io/api`; confidential Code + `PKCE S256`, exact issuer/discovery/JWKS/client/redirect.
- Pending flow максимум `300s`, одноразовый, browser/config-bound; неизвестный исход token exchange не повторяет code.
- Cookie: `Secure, HttpOnly, SameSite=Lax, Path=/, без Domain`, префикс `__Host-`; handle не короче32 случайных байт.
- Absolute lifetime — меньший из `3600s` и срока допустимости IdP credential; чтение не продлевает срок.
- Identity — UNIQUE(issuer,subject), local user UUID; email/group/superuser claims не создают account, membership или platform grant.
- Sessions/memberships читаются для каждого protected operation. IdP observation максимум `50s`; общий сетевой deadline не более `5s`; required live revocation предел `60s`.
- Separate `runtime_identity_read` platform grant; membership не даёт mutation, enqueue, protocol approval или task-result acceptance.
- Missing/malformed/stale state, key/DB/IdP failure и authorizer result, отличный от ровно `:ok`, закрывают доступ.
- Ни fallback password/BasicAuth, ни test trust fixture в production pipeline. Нет LiveView/WS/mutation/list/dashboard/MCP реализации в этой вертикали.
- Secret values не попадают в argv/git/issue/log/event/UI/artifact; runtime references только нового control. Отдельные production OS/container identities и ingress обязательны.
- Один native writer; применять `superpowers:executing-plans`. PROJECT_RULES запрещает extra agents без admission и перекрывает рекомендацию в header.
- Каждый исполняемый leaf получает ACCEPTED exact HEAD/tree/base, allowlist, immutable attempt history и wall budget1800s; максимум2 repair cycles/1 profile change в том же бюджете. На deadline — checkpoint/stop, не новый бюджет для той же попытки.
- GH74 consumed repair history и PR34/PR38 refusals сохраняются. Не импортировать эти branches и не воспроизводить отказанные repair/validator/owner-install операции.
- CI owner отдельно готовит dependency-compatible профиль, independent read-only review и trusted exact-HEAD check. Автор не меняет locked suite/coverage exclusions/profile/CI policy и не пишет trusted status. GitHub Actions не включается.
- Full SN004/SN005 остаются planned/admitted=false. READY источника, fixture GREEN и live acceptance различаются; документация не меняет DAG/admission.

## Review Focus

1. Token endpoint успел употребить code, но ответ потерян: второй обмен запрещён и session/cookie отсутствуют (Task3).
2. Два callback одновременно, включая другой browser: ровно один разрешённый exchange; чужой browser не расходует legitimate flow (Task2/3).
3. Отзыв IdP eligibility сразу после cached success, затем outage/restart/clock rollback: старый success не обновляется и не переживает неизвестную свежесть (Task4/5).
4. Поддельный actor и старые platform/group claims после удаления локальной membership: Project B и identity endpoint остаются закрытыми (Task3/4).
5. Замена ключа или частичная миграция при живом Repo: plaintext fallback отсутствует, auth и readiness закрываются без exception/secret echo (Task2).

---

## Исходная точка и границы приёмки

Планирование начинает с doc HEAD91df044bf458a3576a12fcb8f4e32be12bc9d524/tree e8e6c4fa17ce2718c7715b32f3a34f015e7e0802. Принятый продуктовый parent PR14 — f16c32764df584291d2bdf95d66a4ef9f57daf83/tree44fe878d0de0dc6a2402b23508f4beb742231bb0; base2bf21950e0725bc9228b262e1495f5af5eeea1d6. Check111437950577 подтверждает только f16:413/0/6, configured coverage100%, Dialyzer0.

Рабочая doc ветка: `docs/sn005-authentik-project-access-20261004`; native source `/srv/rdc-workspace/sn005-authentik-design-20261004/source`. [GH33](https://github.com/pupkinson/SymphonyNext/issues/33) содержит действующий workpad; не создавать конкурирующую карточку. Source tasks исполняются в собственной isolated ветке после review плана и fresh tuple/preflight, не меняют PR14 без отдельного exact-source handoff.

Все команды и тесты ниже — **NOT_RUN**. Это план, не тестовый отчёт. Текущий delta: этот файл и MANIFEST.sha256; product/dependency/IdP/runtime changes отсутствуют. До Task1 повторно сверить source/ref, complete spec-index composition и accepted capabilities; при расхождении остановиться и уточнить delta.

## Карта файлов и ответственности

Имена ниже — будущие файлы; существующие seams сохраняются.

| Task | Файлы | Ответственность |
| --- | --- | --- |
| 1 | `elixir/lib/symphony_control/auth/config.ex`, `oidc.ex`, `clock.ex` | Immutable operator bindings, bounded protocol/library adapter, server time/boot epoch |
| 1 | `elixir/test/support/auth_oidc_fixture.exs`; `elixir/test/symphony_control/auth/config_test.exs`, `oidc_test.exs` | Disposable HTTPS provider с реальными wire exchanges и signed tokens |
| 1 | `elixir/mix.exs`, `mix.lock`, `test/test_helper.exs` (все под `elixir/`); `docs/engineering/authentik-project-access.md`, `elixir/README.md`, `README.md`, `MANIFEST.sha256` | Dependency pin/provenance, require test support, ограничения/настройка |
| 2 | `elixir/priv/repo/migrations/20261004000000_create_control_auth.exs`; `elixir/lib/symphony_control/auth/actor.ex`, `token_vault.ex`, `store.ex` | Persistent local state, atomic flows, encrypted tokens, candidate actor |
| 2 | `elixir/lib/symphony_control/health.ex`; `elixir/test/support/auth_db_fixture.exs`; `elixir/test/symphony_control/auth/store_test.exs`, `vault_test.exs`, `schema_test.exs` | Exact supported schema, real PostgreSQL constraints/restart/faults |
| 3 | `elixir/lib/symphony_control/auth/login.ex`, `controller.ex`, `authenticate.ex`, `access.ex` | Browser-bound login, cookie/origin/HTTP, server authentication; access initially denies unconfirmed eligibility |
| 3 | `elixir/lib/symphony_control/application.ex`, `router.ex`, `runtime_config.ex`; `elixir/config/runtime.exs`; `elixir/lib/symphony_elixir/control_boundary.ex`, `subprocess_env.ex` | Explicit opt-in supervisor/config, reject agent+auth combination, filter new secret-reference variables |
| 3 | `elixir/test/symphony_control/auth/login_http_test.exs`, `environment_test.exs`; existing `project_read_http_test.exs`, `standalone_http_test.exs`, `control_boundary_test.exs`, `control_environment_test.exs` | Real loopback transport, replay/lost response, existing HTTP and process boundaries |
| 4 | `elixir/lib/symphony_control/auth/eligibility.ex`, `authorizer.ex`, `logout.ex`; auth `access.ex`, `controller.ex`, `oidc.ex`, `application.ex`, `router.ex` | Current permission checks, bounded observation cache, signed/RP logout |
| 4 | `elixir/test/symphony_control/auth/access_test.exs`, `revocation_test.exs`, `logout_http_test.exs`; shared auth fixture files | Real DB/network lifecycle, role matrix, clock/timeout/back-channel cases |
| 5 | `elixir/test/support/auth_live_fixture.exs`; `elixir/test/symphony_control/auth/live_acceptance_test.exs`; `docs/acceptance/authentik-project-access.md` | Controlled real-instance/browser acceptance and independently checked evidence |
| 1–5 | `docs/engineering/authentik-project-access.md`, relevant READMEs, `MANIFEST.sha256` | Same-PR documentation and digest maintenance for each changed material |

Test paths in the table are under `elixir/test/symphony_control/` unless fully qualified. Task3 existing Elixir boundary tests are under `elixir/test/symphony_elixir/`. `elixir/WORKFLOW.md` меняется только если реально меняется workflow contract; auth не загружается из tracker workflow, поэтому по этому плану его delta отсутствует. Existing Projects/RuntimeIdentity APIs, ProjectReadController whitelist и stock dashboard не переписываются.

## Общие интерфейсы и выбранные ограничения

Все public functions в `lib/` имеют adjacent `@spec`; callbacks — `@impl`. Конфигурация не разрешает module names из request/env strings. Production adapter выбор закрыт allowlist; fixtures инъецируются только явными opts собственного test supervisor, не runtime environment toggle.

`Auth.Config.t()`: generation, issuer, discovery_url, jwks_url, authorization/token/end_session URLs, client_id/client-auth method/allowed algorithms, public_https_origin, exact callback/post_logout/backchannel URIs, new application/provider/resource IDs, client_secret_ref/session_key_ref, eligible_mechanism binding и live evidence references. Токены/значения секретов не поля этой структуры. `Config.load(term()) :: {:ok, Config.t()} | {:error, :invalid_config}`; `Config.activation_allowed?(Config.t()) :: boolean()`. Неизвестный live binding =>false.

`Clock.t()` — `%{utc_ms: integer(), monotonic_ms: integer(), epoch: binary()}`. `Clock.start_link(keyword()) :: GenServer.on_start()`; `Clock.now() :: Clock.t()`. Один cryptorandom epoch на запуск control; mutable test clock доступен только в test support. Все сетевые вызовы получают **один абсолютный monotonic deadline**, а не новый5s на каждый redirect/key refresh.

`Config.reason()` в specs — union `:invalid_request | :forbidden | :dependency_unavailable | :unknown_outcome | :rate_limited`; type объявляется в Auth.Config в `config.ex`, без нового универсального error framework. Ни SQL, ни submitted values, ни provider exception в public errors.

План выбирает дополнительные bounds: network response≤1MiB, JWT≤16KiB, auth request body≤32KiB, code≤4096bytes/state≤256bytes; максимум один unknown-kid refresh, network redirects запрещены. Login≤5/мин на browser binding и≤60/мин глобально, callback/back-channel≤120/мин глобально; bounded1000-entry counters, HTTP429/no-store при исчерпании. Counter cleanup не продлевает pending flow. Эти значения проверяются Task1/3/4, не выдаются за measured production capacity.

Clock/session решение: DB stores boot epoch; сессии предыдущего control epoch требуют **нового входа после restart**, даже если DB expiry ещё впереди. В текущем epoch одновременно проверяются absolute UTC expiry и monotonic elapsed; rollback UTC закрывает affected session. Это сознательная потеря session continuity для исключения продления при clock/restart uncertainty. Consumed/revoked records не удаляются рестартом.

## Task1: Проверенный конфигурационный и OIDC adapter

**Files:** строки Task1 карты; только эти exact paths в ACCEPTED allowlist.

**Interfaces:**
- Consumes: operator-bound Config.t(), runtime secret resolver в owned control; не request Host/query/jku/x5u.
- Produces: `Oidc.authorization_url(Config.t(), %{state: binary(), nonce: binary(), verifier: binary()}, integer()) :: {:ok, String.t()} | {:error, Config.reason()}`.
- Produces: `Oidc.exchange(Config.t(), binary(), %{nonce: binary(), verifier: binary()}, integer()) :: {:ok, verified_identity()} | {:error, Config.reason()}`.
- `verified_identity()` = map issuer/subject(nonempty binaries), sid(binary|nil), credential_expires_at_ms(integer), tokens(private map). Claim roles/email не входят в identity binding.
- Fixture: `OidcFixture.start!(keyword()) :: map()`; `config(map()) :: Config.t()`; `issue_code(map(), keyword()) :: binary()`; `calls(map(), atom()) :: non_neg_integer()`; `assert_no_secret_echo(map()) :: :ok`. Реальные ephemeral HTTPS discovery/JWKS/token endpoints; signing через библиотеку, не mock exchange function. TLS test CA confined to fixture config.

- [ ] **1. Зафиксировать dependency preflight.** Проверить exact Oidcc candidate release3.9.0, license/source archive checksum, OTP28/Elixir1.19 compatibility и APIs для независимого discovery URL, TLS validation, allowed destinations и единого deadline. В planning lookup unversioned README дал3.7.2; version-specific3.9.0 docs не были доступны. Не превращать это расхождение в установленный факт. Зафиксировать verified exact version и transitive lock в evidence; если кандидат отсутствует/не удовлетворяет bounds, STOP dependency_contract_unverified и bounded пересмотр dependency choice, без installer/cache copy или обхода refused fetch endpoint.
- [ ] **2. Написать wire regression tests и fixture в exact Task1 paths.** До implementation adapter API tests компилируются с failure target; отсутствующая test infrastructure не считается RED.
```elixir
test "exchange accepts only exact signed issuer/sub and S256 expectations" do
  f = OidcFixture.start!(pkce: :s256)
  cfg = OidcFixture.config(f)
  code = OidcFixture.issue_code(f, nonce: String.duplicate("n", 43), verifier: String.duplicate("v", 43))
  assert {:ok, %{issuer: issuer, subject: "human-1"}} =
           Oidc.exchange(cfg, code, %{nonce: String.duplicate("n", 43), verifier: String.duplicate("v", 43)}, Clock.now().monotonic_ms + 5_000)
  assert issuer == cfg.issuer
  assert :ok == OidcFixture.assert_no_secret_echo(f)
end

test "bad token properties never return verified identity" do
  for fault <- [:wrong_issuer, :wrong_audience, :wrong_azp, :bad_signature,
                :alg_none, :disallowed_alg, :expired, :future_iat,
                :wrong_nonce, :empty_sub, :jku_other_host] do
    f = OidcFixture.start!(fault: fault)
    code = OidcFixture.issue_code(f, nonce: String.duplicate("n", 43), verifier: String.duplicate("v", 43))
    assert {:error, :forbidden} =
             Oidc.exchange(OidcFixture.config(f), code,
               %{nonce: String.duplicate("n", 43), verifier: String.duplicate("v", 43)}, Clock.now().monotonic_ms + 5_000)
  end
end
```
- [ ] **3. Добавить contract assertions.** `authorization_url` содержит ровно configured redirect, code response_type, scopes и S256 challenge; без code/secret/verifier. Отдельные tests: `issuer differs from discovery URL`, `Host does not select endpoint`, `foreign discovered endpoint/HTTP redirect/invalid TLS rejected`, `unknown kid performs at most one refresh`, `oversized response rejected`, `shared network deadline remains <=5000ms`. Fixture считает реальные requests; neither wrong TLS nor setup outage засчитываются как semantic RED.
- [ ] **4. RED:** `cd elixir && mix test test/symphony_control/auth/config_test.exs test/symphony_control/auth/oidc_test.exs --trace`. Expected: конкретный product assertion fails/adapter missing; infrastructure_READY отдельно.
- [ ] **5. Реализовать Config/Oidc/Clock и exact verified dependency pin.** Oidcc владеет signature/JWK/token crypto; наш adapter ограничивает endpoints/options/error projection и не позволяет implicit weaker PKCE/alg fallback. Client credential читается только по ref в control memory. Refuse expired credential без продления leeway; allowable future-iat skew≤30s. Public Config defaults disable authentication.
- [ ] **6. GREEN:** повторить command4, затем `mix format --check-formatted` и `mix specs.check`. Expected все exit codes0; verify actual dependency version/checksums and clean fixture process teardown. Документация указывает release/API provenance и все ещё BLOCKED live bindings.
- [ ] **7. Commit:** явно `git add` только Task1 paths + changed manifest records; `git commit -m "feat(auth): bind the OIDC adapter to verified control configuration"`. Получить exact HEAD/tree; independent review/protected gate как описано ниже. Сам adapter пока не устанавливает permissive authorizer.

## Task2: Durable sessions, one-time flows и локальные права

**Files:** Task2 карты; добавить auth DB support require в `elixir/test/test_helper.exs`. Existing CreateProjects migration неизменна.

**Interfaces:**
- Consumes: Config.t(), verified_identity(), Clock.t() из Task1.
- Produces `TokenVault.seal(Config.t(), binary(), binary()) :: {:ok, binary()} | {:error, Config.reason()}`; `open/3` с теми же аргументами config/ciphertext/AAD и результатом plaintext/error.
- Produces `Actor.t()` = struct session_id/local_user_id(Ecto.UUID), issuer/subject, config_generation, boot_epoch. Нет roles/tokens/email; происхождение actor само по себе не grant.
- `Store.put_login(cfg, browser_handle, flow, clock)` =>`{:ok, flow_id}`/error. Flow map state/nonce/verifier/issued_ms; state/browser DB hashes, encrypted verifier/nonce, cfg generation/boot epoch/300s expiry.
- `Store.consume_login(cfg, state, browser_handle, clock)` =>`{:ok, flow}`/error; атомарное DB consumption до exchange, не consume чужого browser.
- `Store.open_session(cfg, verified_identity, old_handle_or_nil, clock)` =>`{:ok, opaque_handle}`/error; local identity уже должна существовать и быть active.
- `Store.local_actor(cfg, opaque_handle, clock)` =>`{:ok, Actor.t()}`/error; это local validity candidate, без обещания IdP eligibility.
- `Store.actor_current?(cfg, actor, clock)` =>boolean; DB binding/revocation/expiry/generation/epoch читается повторно.
- `Store.permissions(cfg, actor, project_uuid_or_platform, clock)` =>`{:ok, MapSet.t(atom())}`/error; только текущие local rows.
- `Store.revoke(cfg, selector, clock)` и `Store.accept_logout(cfg, jti, selector, retain_until_ms, clock)` =>`:ok`/error. Selector — internal tagged tuple `{:session, uuid}`, `{:sid, issuer, sid, sub_or_nil}` или `{:subject, issuer, sub}`, не request-supplied mutation authority.
- DB fixture `AuthDbFixture.start!(keyword()) :: map()`, `seed_user!(fixture, keyword()) :: uuid`, `seed_membership!(fixture, user, project, roles) :: :ok`, `restart_control!(fixture) :: :ok`, `clock(fixture) :: Clock.t()`. Реальный disposable owner-provisioned PostgreSQL, isolated random schema, штатный migrator.

- [ ] **1. Проверить fixture READY.** Новые `SN005_TEST_PG_SOCKET`/port/user/db bindings получает owner отдельного fixture, не угадываются и не меняют existing SN004 DB. Новый DB/schema creation scope должен быть accepted. Writer не устанавливает PostgreSQL/root/Docker и не копирует dependency cache; недоступность — BLOCKED, не RED.
- [ ] **2. Написать миграционные и state regression tests.**
```elixir
test "flows have one durable consumer and foreign browser cannot consume" do
  f = AuthDbFixture.start!([])
  cfg = f.config
  now = AuthDbFixture.clock(f)
  flow = %{state: "state-32-byte-fixture", nonce: "nonce", verifier: "verifier", issued_ms: now.utc_ms}
  assert {:ok, _} = Store.put_login(cfg, "browser-A", flow, now)
  assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser-B", now)
  assert {:ok, _} = Store.consume_login(cfg, flow.state, "browser-A", now)
  AuthDbFixture.restart_control!(f)
  assert {:error, :forbidden} = Store.consume_login(cfg, flow.state, "browser-A", AuthDbFixture.clock(f))
end

test "unknown or same-email identity never registers or gains a session" do
  f = AuthDbFixture.start!([])
  AuthDbFixture.seed_user!(f, issuer: f.config.issuer, subject: "known", email: "same@example.invalid")
  unknown = %{issuer: f.config.issuer, subject: "unknown", sid: nil,
              credential_expires_at_ms: AuthDbFixture.clock(f).utc_ms + 3_600_000, tokens: %{}}
  assert {:error, :forbidden} = Store.open_session(f.config, unknown, nil, AuthDbFixture.clock(f))
end
```
- [ ] **3. Добавить assertions constraints/expiry/vault.** Таблицы `control_auth_users`, `control_auth_identities`, `control_auth_sessions`, `control_auth_pending_logins`, `control_auth_memberships`, `control_auth_platform_grants`, `control_auth_logout_jtis`. UUID PK/FK, UNIQUE issuer+subject, UNIQUE user+project, unique session/state hashes and issuer+jti; NOT NULL times/generations/active flags; recognized human roles only, positive membership revision, expiry>issued. Direct SQL violation тесты проверяют именно database constraints.
- [ ] **4. Написать boundary tests:** pending at299999ms permitted/300000ms denied; min3600000ms/credential expiry; expired handle/old config/old boot denied; revoked remains denied after restart. Parallel `consume_login` => exactly1ok; ciphertext contains no synthetic token canary; wrong AAD/key/tamper/missing key =>error. Live Repo with missing auth FK/unique/check/version blocks readiness. Driver timeout, suspended pool and ambiguous commit never yield new cookie/session permission.
- [ ] **5. RED:** `cd elixir && mix test test/symphony_control/auth/store_test.exs test/symphony_control/auth/vault_test.exs test/symphony_control/auth/schema_test.exs --trace`. Expected semantic failures with real migrated fixture READY.
- [ ] **6. Реализовать migration/Store/Actor/Vault и Health schema contract.** Vault использует OTP28 AES-256-GCM, runtime32-byte key, fresh96-bit nonce/128-bit tag, versioned envelope; AAD exact session-or-flow ID + config generation. Nonces не supplied клиентом; adapter review обязателен. Pending consume — guarded SQL UPDATE RETURNING with committed consumption before plaintext is used for exchange; unknown commit=>error/no exchange. Queries timeout500ms, queue:false, log:false и750ms outer bound по существующему Projects pattern. Rotation/revoke + new session выдаются только после confirmed transaction. DB хранит hash handle, не handle.
- [ ] **7. Обновить Health вместе с миграцией.** Разрешить ровно known migration sets [20260925000000] при auth disabled и [20260925000000,20261004000000] с полным auth+project contract; auth enabled требует вторую. Missing/future version/constraints дают ready:false; public shape/live/readiness/no-auto-migration остаются прежними. Старые foundation/schema tests сохраняют assertions для legacy/auth-disabled DB.
- [ ] **8. GREEN:** command5 плюс existing `mix test test/symphony_control/foundation_test.exs test/symphony_control/schema_contract_test.exs --trace`; expected0, repeated migration[], unchanged project rows. Обновить engineering migration/runbook docs и manifest.
- [ ] **9. Commit:** `git commit -m "feat(auth): persist one-time logins and revocable local sessions"` после explicit Task2 staging; exact-source review/gate. Без local signup/administration endpoint; identities/memberships seed делает только scoped owner fixture/bootstrap.

## Task3: Browser login и server-only HTTP authentication

**Files:** Task3 карты; test support из Task1/2. Access API сначала возвращает denial для unconfirmed eligibility; разрешение появляется только в Task4.

**Interfaces:**
- Consumes: Oidc.authorization_url/exchange, Store APIs и Clock.now; existing Router and Projects.get_project/2.
- `Login.begin(cfg, browser_handle_or_nil, clock)` =>`{:ok, %{location: binary(), browser_handle: binary()}}`/error.
- `Login.finish(cfg, code, state, browser_handle, old_session_handle_or_nil, clock)` =>`{:ok, opaque_handle}`/error.
- `Access.start_link(keyword()) :: GenServer.on_start()` принимает immutable config и trusted server-only `:eligibility_confirm` callback с signature `(cfg, actor, clock, deadline_ms) -> :ok | {:error, reason}`; default callback всегда forbidden. Production factory не читает callback из environment/request. Test supervisor задаёт callback, который действительно обращается к owned HTTPS fixture Task1; production callback появляется в Task4.
- `Access.authenticate(cfg, handle, clock) :: {:ok, Actor.t()} | {:error, Config.reason()}`; unknown eligibility=>forbidden. Task4 сохраняет эту signature.
- `Authenticate.init(keyword()) :: keyword()`; `Authenticate.call(Plug.Conn.t(), keyword()) :: Plug.Conn.t()`.
- `Controller.login/callback/logout/backchannel_logout(Plug.Conn.t(), map()) :: Plug.Conn.t()`; последние два initially denied, подписанные handlers Task4.
- `AuthHttpFixture.start!(keyword()) :: map()`; `login!(fixture, keyword()) :: %{cookie: binary(), response: map()}`; `get(fixture, path, keyword()) :: map()`; `callback(fixture, keyword()) :: map()`; `counts(fixture) :: %{exchanges: integer(), sessions: integer()}`. Bandit loopback real Req transport + Task1 provider + Task2 PG; cookie jars in memory only.

- [ ] **1. Написать browser/HTTP regressions.**
```elixir
test "parallel callback exchanges once and rotates the session handle" do
  f = AuthHttpFixture.start!([])
  login = AuthHttpFixture.login!(f, phase: :begin)
  responses = 1..2 |> Enum.map(fn _ -> Task.async(fn -> AuthHttpFixture.callback(f, flow: login) end) end)
                    |> Enum.map(&Task.await(&1, 6_000))
  assert Enum.count(responses, &(&1.status == 303)) == 1
  assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 1}
  # Fixture also checks old/pre-login session handle is unusable and cookie attributes.
end

test "lost exchange response never repeats code or sets a session cookie" do
  f = AuthHttpFixture.start!(token_response: :disconnect_after_accept)
  login = AuthHttpFixture.login!(f, phase: :begin)
  first = AuthHttpFixture.callback(f, flow: login)
  second = AuthHttpFixture.callback(f, flow: login)
  assert first.status in [403, 503]
  assert second.status == 403
  refute Map.has_key?(first.cookies, "__Host-symphony-control")
  assert AuthHttpFixture.counts(f) == %{exchanges: 1, sessions: 0}
end
```
- [ ] **2. Дополнить tests:** state mismatch/300s expiry/wrong browser/nonce/config change/no code; preassigned actor/query actor_id/roles/project claims/header actor не bypass Authenticate. Config absent=>project403 and identity403, no actor retained; health remains public. Cookie raw≥32bytes, __Host-Secure/HttpOnly/Lax/path/ noDomain; no tokens in redirects/finalURL/logs. External return_to/Host/forwarded headers не меняют redirect/client endpoints. Auth bodies/limits429/allowed methods проверяются real transport.
- [ ] **3. RED:** `cd elixir && mix test test/symphony_control/auth/login_http_test.exs test/symphony_control/auth/environment_test.exs --trace`; expected concrete callback/cookie/boundary assertion failures with fixture READY.
- [ ] **4. Реализовать Login/Controller/Authenticate/Access и explicit supervisor opts.** Begin генерирует32 random bytes для state/browser binding/nonce и PKCE verifier; pending flow сохраняется до redirect. Finish consumes first, exchanges once within shared5s deadline, maps only exact local issuer/sub, commits rotated handle,303 на фиксированный `/`. При failed transaction/token outcome cookie отсутствует. Protected middleware очищает current_actor прежде проверки; missing/invalid cookie=>nil actor/403, dependency failure=>fixed503/no-store. Для health и auth endpoints не выполняет project authorization.
- [ ] **5. Подключить routes и safe runtime configuration. В Application child list добавить Clock, Access и лимитеры после Repo; production Access пока использует deny callback.** GET login/callback; POST logout/backchannel; wrong method=>405+Allow, others existing404. Read configured manifest path из `SYMPHONY_CONTROL_AUTH_CONFIG` (nonsecret path), defaultdisabled; full load happens before standalone control supervisor/listener. New owned secret file refs задаются конфигурацией, не secret startup env. Не принимать arbitrary forwarded headers: exact public HTTPS origin/owned ingress binding проверены operator; backend listener остаётся127.0.0.1. Config lacking verified ingress/resource/eligible-state evidence не активирует production auth. Fixture ingress — отдельный owned test resource; insecure product cookie fallback не добавляется.
- [ ] **6. Проверить agent boundary.** Combined agent start при auth/control opts/loaded key reference =>`:control_agent_runtime_unsupported`. Existing ControlBoundary check сохраняется/усиливается только новым auth marker, не ослабляется. SubprocessEnv удаляет auth-config/secret-reference env names и явно выключает control/auth, включая after shell initialization; реальный synthetic child загружает конфигурацию с auth disabled. Если auth secrets уже загружены, agent launch отвергается до создания child. File/proc access denial между разными production UID доказывается Task5; env filtering не считается такой изоляцией.
- [ ] **7. Сохранить existing HTTP contract.** Старый TrustedActorFixture перед Router больше не доказывает auth; перенести positive HTTP tests на Task1/2 trusted server fixture и expected candidate actor; retain normalized UUID argument, schema_version1 whitelist,400/403/404/503/no-store, wrong methods and absent route assertions. Domain Projects authorization callbacks не переписываются; stock dashboard untouched.
- [ ] **8. GREEN:** command3 плюс `mix test test/symphony_control/project_read_http_test.exs test/symphony_control/standalone_http_test.exs test/symphony_elixir/control_boundary_test.exs test/symphony_elixir/control_environment_test.exs --trace`. До Task4 production unknown eligibility остаётся403. Positive legacy HTTP tests получают actor через Task3 test-only wire confirmation callback и existing test authorizer, заданные явными opts своего supervisor; они не обходят Authenticate. Production config не может выбрать эти callbacks. Expected0 и old public JSON/errors preserved; это не live SSO.
- [ ] **9. Commit:** `git commit -m "feat(auth): add browser-bound login and control authentication routes"`; docs env/HTTPS/log redaction same delta, manifest refreshed, exact source gates.

## Task4: Текущие permissions, freshness и logout

**Files:** Task4 карты. Store API/schema Task2 reused; новая migration не нужна.

**Interfaces:**
- `Eligibility.start_link(keyword()) :: GenServer.on_start()`.
- `Eligibility.confirm(cfg, Actor.t(), Clock.t(), integer()) :: :ok | {:error, Config.reason()}`.
- Own production adapter проверяет только configured client-scoped authoritative mechanism, tied exact version/provider/application/evidence/config generation. Unproved mechanism =>forbidden; старые JWT/groups/introspection URL alone не proof.
- `Authorizer.authorize(term(), :project_read, term()) :: :ok | :deny`; `authorize(term(), :runtime_identity_read) :: :ok | :deny`. Все прочие actions/scopes=>deny.
- `Access.authenticate/3` теперь использует Store.local_actor + Eligibility.confirm; `Access.authorize(cfg, actor, action, scope, clock) :: :ok | {:error, Config.reason()}` заново проверяет local candidate, current eligibility, membership/platform grant.
- `Oidc.verify_logout(cfg, jwt, deadline_ms)` =>`{:ok, %{jti: binary(), sid: binary() | nil, sub: binary() | nil, issued_ms: integer()}}`/error; library signature/JWKS/claim validation.
- `Logout.local(cfg, actor, clock)` =>`:ok`/error; `Logout.backchannel(cfg, jwt, clock)` =>`:ok`/error. Foreign token не selector authority.
- Test fixture добавляет `revoke!(fixture, kind) :: :ok`, `advance!(fixture, milliseconds) :: :ok`, `fault!(fixture, kind) :: :ok`, `actor!(fixture) :: Actor.t()`, `project!(fixture, atom()) :: uuid`, `session_count(fixture) :: integer()`. Mutation scope — только собственные fixture rows/provider state.

- [ ] **1. Написать policy/freshness regressions.**
```elixir
test "project roles never grant another project or runtime identity" do
  for role <- [:viewer, :contributor, :operator, :approver, :project_admin] do
    f = AuthHttpFixture.start!(role: role, projects: [:alpha, :beta])
    actor = AuthHttpFixture.actor!(f)
    alpha = AuthHttpFixture.project!(f, :alpha)
    beta = AuthHttpFixture.project!(f, :beta)
    assert Authorizer.authorize(actor, :project_read, alpha) == :ok
    assert Authorizer.authorize(actor, :project_read, beta) == :deny
    assert Authorizer.authorize(actor, :runtime_identity_read) == :deny
    AuthHttpFixture.revoke!(f, :local_membership)
    assert Authorizer.authorize(actor, :project_read, alpha) == :deny
  end
end

test "failed observation cannot renew old success at the 50s boundary" do
  f = AuthHttpFixture.start!(eligibility: :confirmed)
  login = AuthHttpFixture.login!(f, phase: :complete)
  path = "/api/v1/projects/" <> AuthHttpFixture.project!(f, :alpha)
  assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
  AuthHttpFixture.advance!(f, 49_999)
  assert AuthHttpFixture.get(f, path, cookie: login.cookie).status == 200
  AuthHttpFixture.fault!(f, :eligibility_unavailable)
  AuthHttpFixture.advance!(f, 1)
  assert AuthHttpFixture.get(f, path, cookie: login.cookie).status in [403, 503]
  AuthHttpFixture.advance!(f, 10_000)
  assert AuthHttpFixture.get(f, path, cookie: login.cookie).status in [403, 503]
end
```
- [ ] **2. Добавить grant matrix tests.** PlatformAdmin без membership не читаетalpha; explicit runtime_identity_read даёт только platformidentity. IdP superuser/groups/email/session credentials не дают membership. Service/agent/localinactive/unknown actor/partially malformed new Auth.Actor/maps/invalid UUID/action deny без KeyError. Raising/throwing/exiting lookup/adapter возвращает sanitized deny; проверяем новый owning contract, не исправляем PR38 SessionAccess.
- [ ] **3. Добавить signed/local logout tests.** Missing/wrong CSRF/session/exact Origin=>403; local revoke committed before external logout request и остаётся revoked при IdP outage. Signed back-channel exact issuer/aud/signature/events/iat/jti/no nonce и sid/sub binding; foreign issuer/sub/aud не изменяет sessions. Same jti повторно не применяет effect; dedup survives restart. sid+sub выбирает intersection, толькоsub — все sessions этой exactidentity. Logout iat≤300s age и future skew≤30s; replay records≥3600s. Cookie и bearer не заменяют signed logout_token.
- [ ] **4. RED:** `cd elixir && mix test test/symphony_control/auth/access_test.exs test/symphony_control/auth/revocation_test.exs test/symphony_control/auth/logout_http_test.exs --trace`; expected product role/freshness/logout assertion failures, не network/setup failure.
- [ ] **5. Реализовать bounded Eligibility/Access/Authorizer.** Cache key exact issuer/sub/sid/configgeneration/bootepoch, successful observation age<50000ms по monotonic; no cached success from failure/invalidation/restart. Network absolute deadline≤5000ms; revoke just after cache success tested worst boundary. Прошедший DB/expiry check не заменяет IdP check; authorizer rereads local session/membership every call. Empty/unverified eligible mechanism alwaysdeny. Production standard endpoint adapter разрешается только для exact binding, доказанного Task5 для трёх distinct cases; не добавлять admin-token или provider-wide API.
- [ ] **6. Реализовать signed logout и event invalidation.** Внутри committed Store.accept_logout transaction mark revoked + uniquejti; cache invalidate aftercommit, response only after confirmed effect. Неизвестный revoke outcome закрывает текущий request, reconciliation по immutable receipt/selector, без blind повтор mutation. В production Access factory заменить deny callback на &Eligibility.confirm/4, child Eligibility стартует перед Access. Runtime auth authorizers устанавливаются только при complete enabled config; disabled/default сохраняют existing nildeny.
- [ ] **7. Проверить lifecycle/fault limits.** Concurrent check/invalidation не публикует уже отозванный success; UTC rollback не продлеваетsession; restart old handle alwaysdeny; new login required. Replaced encryption key/config invalidates access. Stalled PG/IdP/FKmissing/decryptfailure sanitized403/503 within bounds; no token/code/secret in logs even exceptions. Body/rate limits apply before expensive verify; back-channel counters bounded. New tests for every Review Focus3/4 and retention at300/3600 boundaries.
- [ ] **8. GREEN:** command4 плюс `mix test test/symphony_control/auth test/symphony_control/project_read_http_test.exs test/symphony_control/identity_test.exs --trace`. Production adapter lacking live proof remains403; fixture grants use real wire authoritative observation + real PG. Expected0, every protected outcome matches role/current state and exact projector whitelist.
- [ ] **9. Commit:** `git commit -m "feat(auth): enforce current project rights and bounded session revocation"`; update engineering/README/manifest; exact-source independent/protected gate. Offline observation tests не принимают реальный AC-22.

## Task5: Exact-version Authentik, HTTPS и browser acceptance

**Files:** Task5 карты; no change to shared IdP/global flows/old config. Новый resource manifest и runtime evidence находятся в owned operator evidence directory; nonsecret acceptance summary в repo. Schema/secret/resource migrations делаются normal operator interface в accepted scope, не writer privilege escalation.

**Interfaces:**
- Consumes: accepted exact source/image/config/schema, protected check ID/receipt, Task1–4 APIs, separately verified new application/provider/HTTPS/control-UID/network/secret refs.
- Produces: immutable live acceptance receipt with exact provider version/IDs/issuer/client/endpoints/config hash, UTC+monotonic timestamps, case-specific browser/HTTP outcomes, latency bounds, test exit codes and redacted artifact hashes; no cookies/tokens/secrets.
- `AuthLiveFixture.preflight!()` returns manifest scoped to new controlled test users/projects/client; failure raises explicit fixture_unavailable and status BLOCKED, never PASS.
- `AuthLiveFixture.run_case!(fixture, atom())` returns `%{tab_a: [%{elapsed_ms: integer(), status: integer()}], tab_b: [...], observed_binding: map(), source_tuple: map()}`.
- Case actions use only already verified limited operator capabilities for those fixture IDs. Missing supported capability/observation=>BLOCKED; нет HTTP fallback на rejected endpoints. Same browser two tabs/private reads; cookie jars private runtime memory/file mode0600 in own UID, not exported to evidence.

- [ ] **1. Freeze operator manifest/preflight before any live write.** Fresh installed Authentik version/instance URL, new exact application/provider/client IDs, client-auth/signing policy, issuer separately from discovery/JWKS, exact HTTPS callback/postlogout/backchannel URLs. Readback verifiedowned resources, secret/key reference names, explicit local issuer + sub/user/project bindings, app eligibilityallowlist. Historical bootstrap RESOURCE_BINDINGS snapshot не доказательство.
- [ ] **2. Prove candidate observation semantics first.** Проверить installed client-scoped standard mechanism для app-group removal, user deactivation и terminated IdP session. Не считать наличие URL/activeclaim достаточным; измерить отрицательные ответы/события после каждого действия на disposable fixture. Если хотя бы один case не покрывается≤60s без wideadmin/globalchange, сохранить BLOCKED AC-22, auth disabled; source fix не выдумывает permission.
- [ ] **3. Проверить deployment boundary/ingress.** Control один в новом UID/container/resource, без agent/hook execution; runner отдельныйUID и не читает control proc/key files/tokens/socket. HTTPS externalexactorigin, Host/origin validation/trusted ingress overwrites clientforwardedheaders; access logs redact authquery/body before storage. Проверить secret synthetic canary через unprivileged child/runner, а не только childenv. Product cookie в realbrowser Secure/HttpOnly/Lax/__Host-. ProtocolTLSfixture не принимаетproductioncert.
- [ ] **4. Написать live assertions/harness.** Owner/browser sign-in через existing Authentik без password/cookie values в chat; no open registration; app-bound controlled users. `run_case!` waits for confirmed case-specific action receipt before elapsed_ms=0, polls both tabs≤1000ms, never renews old session. Критический revoke fixture намеренно действует сразу после fresh eligibilitysuccess.
```elixir
test "real installed IdP and local revocations close both tabs within 60s" do
  fixture = AuthLiveFixture.preflight!()
  for kind <- [:local_membership, :app_group, :user_deactivation, :idp_session] do
    proof = AuthLiveFixture.run_case!(fixture, kind)
    for samples <- [proof.tab_a, proof.tab_b] do
      assert Enum.any?(samples, &(&1.status in [403, 503] and &1.elapsed_ms <= 60_000))
      assert Enum.all?(Enum.filter(samples, &(&1.elapsed_ms >= 60_000)),
                      &(&1.status in [403, 503]))
    end
    assert proof.source_tuple == fixture.source_tuple
    assert proof.observed_binding == fixture.observed_binding
  end
end
```
- [ ] **5. RED/blocked observation:** only after fixture READY run `cd elixir && SN005_RUN_LIVE_AUTHENTIK=1 mix test test/symphony_control/auth/live_acceptance_test.exs --trace`. Missinglivebindings/operator/browser =>BLOCKED, not regressionRED. Actual wrongproject/поздний отзыв/чтение секрета is semantic FAIL and stopsenablement.
- [ ] **6. Complete exact app-local configuration then GREEN:** тот же command5 и fresh readbacks. Required cases: successfulOIDC+свой проект200, чужой проект403, identity только с explicit platform grant, нет открытой регистрации, logout/revoked session across tabs, provider outage failclosed, restart oldsessiondenied, matched exactcommit/image/config/schemahealth/function. Record deactivation/group removal/sessiontermination отдельно, real deliveries подтверждать DB/HTTP outcome. Если protocol/library adapter delta требуется, новый frozen source + independent/protected gate до повторного live run within remaining attempt budget.
- [ ] **7. Записать acceptance/commit only actual results.** `git commit -m "docs(auth): record exact-version project access acceptance"` для redacted summary + applicable tests/docs/manifest. NOT_RUN остаётся NOT_RUN; scoped live proof не объявляет полная SN-005, AUTH04 step-up/LiveView/WS/AUTH09 не implemented.
- [ ] **8. Release handoff:** only admitted resource/scoped source via normalPR/merge/Coolify webhook after exact-SHA gates; fresh independently verified runtime acceptance. Auto rollback только на verified schema-compatible predecessor; он сейчас UNKNOWN. No destructive restore/down migration for auth DB, no restoration of old sessions. До этого auth disabled, test resources cleanup scoped by ownership receipt only.

## Повторяемые source gates и evidence

Для каждой source задачи после targeted GREEN, до handoff:
- [ ] Refresh full dependency/source tuple and allowlist; pin implementation-relevant skills per attempt, preserve repair/profile/deadline history.
- [ ] Run `cd elixir && make all`: setup/build/escript build only, format-check, lint/specs/strictCredo, full tests configured coverage100%, Dialyzer0. Existing skips фиксируются по IDs/count, новые unexpectedskips reject. Новые Auth modules не добавляются в ignore_modules.
- [ ] Run `python3 -B -m unittest discover -s tests -p test_bootstrap_snapshot.py -v` and applicable unchanged refinement contracts; это static checks, не blocked general package validator. Run `sha256sum -c MANIFEST.sha256`, `git diff --check`.
- [ ] Validate real PR body `cd elixir && mix pr_body.check --file <own-evidence-dir>/pr_body.md`; expected0/template exact. Record UTC start/end/exit, output hash, source/lock/config/fixture hashes for all commands. Values in future commands remain NOT_RUN until executed.
- [ ] Verify diff confined frozen paths, explicitgitadd, commit/non-forcepush and GitHub/native HEAD/tree readback; unknown write reconcile before anyrepeat.
- [ ] Independent source reviewer reads full affected context/requirements; missing/truncated requirements=>limitation/HOLD, sourceREADY not testsPASS. Reviewer doesn't write implementation. Protected owner check exactHEAD must report installed-policy/result/review/inputs identities and readback; absence=>BLOCKED.
- [ ] If mix.lock changed relative preparedCIimage, owner makes bounded dependency-compatible preparedprofile/receipt first. Автор не rebuilds/repairs protectedimage or changes daily CI admission; unlimited daily setting stays asinstalled. Timerstate remainsownercontrolled, author doesn't enableit.
- [ ] No packaged entrypoint execution or replay of rejected cache-copy/server-validator/owner-install/PR38repair. `mix build` creates artifact only; it не attests packaged execution.
- [ ] Checkpoint VERIFIED/INFERRED/UNKNOWN/BLOCKED with exact head/tree/base, effects/current process states, test commands/exits/hash links, openissues/next bounded action; do notaccept task from source-only signal.

## Inline self-review и coverage map

| Spec section | Owning task / evidence |
| --- | --- |
| Protocol/identity/closedregistration/browser binding | 1wire negative token tests;2unique/localuser;3state/nonce/code/rotation |
| Session ciphertext/expiry/restart/schema | 2realPG/vault/constraint/fault tests;3cookie/process boundary |
| Role/project/platform separation/currentmembership | 4matrix+DB reread;3actor spoofing;5реальное чтение своего и чужого проекта |
| IdP50s + deadline5s + revoke60s | 4boundary/failure/invalidation/clock;5fourdistinct measured two-tab cases |
| RP/back-channel logout | 4signedselector/iat/jti/CSRF/origin/restarttests;5actualdelivery/effect |
| Secrets/defaultdeny/typed HTTP/health | 1networkredaction;2AAD/key/schema;3ingress/HTTP/env;5actualUID negativecanary |
| Independent/locked gates/live activation | sourcegatechecklist +5operator manifest/evidence, auth не включается bysourceGREEN |
| FullSN005 beyond firstreadvertical | Explicitly deferred step-up≤5min, WS/LiveView≤60s, mutation/AUTH09/MCP; no milestoneclaim |

Self-review выполнен inline: exact interfaces and fieldnames agree across tasks; tests own all five ReviewFocus cases; no missing-key access assumes actor is valid;границы0/50/60/300/3600 named. Неизвестность setup/dependency/live are stopgates with concrete evidence, not permissive fallbacks. Source tasks independently testable with defaultsdisabled and narrowly staged commits. Plan is intentionally more detailed than spec but does not contain implementation bodies or grant new capabilities.

**VERIFIED:** approved spec/source baseline, current seams/paths/quality gates, scoped document-only intent. **INFERRED:** architecture and selectedbounds can implement required refusal behaviour; no runtimeSLO claim. **UNKNOWN:** exact maintained dependency pin/installed IdP mechanism/HTTPSresources/secretrefs/live process isolation/schema-compatible production predecessor. **BLOCKED:** live SSO/AC-22/полная SN-005 until actual preflight and acceptance.

Следующий bounded action после письменного review этого плана: Task1 dependency/config/fixture preflight и его frozenACCEPTED source delta, затем targetedRED→GREEN. Сохранить native single-writer execution; план сам не запускает worker, CIservice или productimplementation.
