# ChatGPT MCP parity — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for one admitted leaf at a time. No extra agents. Independent exact-HEAD review remains a release gate. Track each step with `- [ ]`.

**Goal:** Реализовать remote MCP и плагин облачного ChatGPT с теми же бизнес-возможностями, правами и проверяемыми результатами, что веб-панель Symphony Next.

**Architecture:** Elixir/Phoenix domain services владеют задачами, ACL, настройками и операциями. Тонкий TypeScript gateway на официальном MCP SDK обслуживает Streamable HTTP и вызывает тот же backend. Отдельной БД задач, второй очереди и административной gateway identity нет.

**Tech Stack:** Принятые Elixir/OTP, Phoenix, PostgreSQL и TypeScript; официальный `@modelcontextprotocol/sdk` и `zod`; ExUnit, Node test runner, Playwright. W02.02 проверяет совместимость и фиксирует фактические SDK/runtime версии в lockfile/ADR/image digest. Незакреплённый `latest` в release manifest запрещён; этот план зависимости не устанавливает.

**Spec:** `docs/superpowers/specs/2026-09-23-chatgpt-mcp-parity-design.md`, базовый `SPECIFICATION.md` §22. Точные Files, fixtures, requirements, acceptance и commands каждой задачи находятся в `planning/mcp-execution.json` и являются частью этого плана. Порядок композиции и hashes — `planning/spec-index.json`.

## Global Constraints

Одинаковые права и бизнес-результаты UI/REST/MCP; целевое покрытие 100% применимых команд, не заявление о текущей реализации. Actor определяется авторизацией, не аргументом модели. Consent/MFA и личное подтверждение не подделываются `approve=true`. Secrets не входят в schemas, аргументы, tool results или model logs.

Только `pupkinson/SymphonyNext`. DF Assistant, его службы, `/home/programmer`, credentials и workspaces вне scope. Один bootstrap writer; ранее использованный BOOT-P01 и его markers/result.json не изменять и не запускать повторно. PR #8 observer repair — отдельная работа.

Все новые карточки planned/admitted=false. До исполнения нужны принятые prerequisites, exact source, identity/sandbox/budget и scheduler admission. Перед новым реальным запуском Symphony — отдельное предупреждение владельцу и отдельная команда в tmux. Этот документ не содержит команды запуска службы.

Релиз: independent exact-HEAD checks/review → scoped merge → штатный Coolify webhook → functional readback. GitHub Actions не включать; повторного per-deploy согласования внутри действующей делегации не добавлять.

## Review Focus

1. Цикл MCP/provisioning: W02.02 означает готовность транспорта, не полноту всех инструментов; SN-042 обязан ждать W06.
2. Отзыв роли после preview: повторная проверка authority на commit независимо от cached tools/list — W02.01/W04.04.
3. Lost write acknowledgement: один operation key через разные каналы не создаёт вторую запись; иной payload с тем же key отклоняется — W02.02/W03.01/W04.01.
4. Pagination/attachments: чужие данные не раскрываются через counts; opaque filename не считается bytes — W03.02/W03.03.
5. Gateway restart/stale telemetry: reconnect читает ту же operation, прежний запуск не превращается в not_started — W04.03/W04.06/W06.

## 1. Композиция и граф

Base main: `30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8`. Backlog SHA256: `c2a0e1a51409bd82c4dda0c5195b60926d311a64098d28defd14842c9a77b4f0`.

После принятия exact source planner проверяет hashes, expected_depends_on и expected_interfaces_consumes, добавляет 14 дочерних карточек и применяет только две явные поправки. SN-031 становится aggregate_only и ждёт W06; все первоначальные prerequisites SN-005/SN-014/SN-029 перенесены на W01. SN-032 ждёт W02.02 вместо полного SN-031: одновременно заменяются depends_on и interfaces.consumes. Старый список consumes сверяется целиком через expected_interfaces_consumes; оставшиеся inputs SN-006/SN-014 и все produces сохраняются. Все остальные baseline edges/statuses/admission сохраняются.

Без поправки возникает цикл SN-031 → W06 → W04.05 → SN-034 → SN-033 → SN-032 → SN-031. Исправленный граф содержит 58 узлов, включая агрегат; 57 потенциально исполнимых leaf nodes. Количество узлов не означает готовность к запуску. SN-042/043/044 транзитивно ждут полной MCP-приёмки.

Исходные SPECIFICATION/TASKS/backlog/traceability v0.5 сохраняются как база, но не единственный вход. `spec-index.json` связывает обязательное дополнение, refinement и этот план в один источник. Это не второй tracker и не скрытая очередь.

Старая `schemas/backlog.schema.json` не принимает dotted IDs; новый refinement проверяется `schemas/task-refinement.schema.json`. Его нельзя подать старому parser как будто формат не изменился. Stock Symphony не импортирует эти файлы автоматически. Неподдерживаемый refinement вызывает `unsupported_task_refinement`, а не пропуск дочерних задач. Этот PR не реализует importer и не повторяет исторически отклонённый серверный validator.

## 2. Файлы, контракты и тестовый harness

Все implementation_paths в карточках — точные proposed targets, не уже существующие модули. W01 создаёт `elixir/lib/symphony_control/mcp/registry.ex` и `mcp/domain.ex`; W02.01 — `mcp/authorization.ex`; остальные domain mappings лежат в `mcp/tools/*.ex`. Общие contexts не дублируются.

W02.02 создаёт `mcp-gateway/src/server.ts`, `catalog.ts`, `domain-client.ts` и package/lockfile. Gateway регистрирует отдельный SDK tool для каждой capability; generic HTTP/SQL/shell наружу отсутствует. Backend origin фиксирован конфигурацией. MCP bearer передаётся только защищённым заголовком внутри того же resource server; backend заново проверяет issuer/audience/expiry/scopes и ACL. Никакого переноса этого bearer в GitHub/Coolify/LLM API.

Плановые интерфейсы, создаваемые W01/W02.01:

```elixir
SymphonyControl.MCP.Registry.validate(entries, ui_commands)
# :ok | {:error, {:missing_mapping, ids}} | {:error, :invalid_contract}
SymphonyControl.MCP.Authorization.verify(bearer, resource, scopes)
# {:ok, actor} | {:error, :unauthenticated | :forbidden}
SymphonyControl.MCP.Domain.invoke(actor, capability, arguments, preconditions)
# {:ok, result} | {:accepted, %{operation_id: id, state: :queued}} | {:error, reason}
# preconditions: expected_version, idempotency_key, preview_id/hash по типу команды.
```

Mutation сохраняет durable intent до ответа; повтор key с иным payload отклоняется. Read возвращает observed_at/revision/stale и bounded страницу. Личность не берётся из tools/call.arguments. Долгий tool call не удерживает выполнение проекта до конца: возвращается operation_id.

W01 также создаёт `elixir/test/support/mcp_case.ex`: `fixture!(name)` формирует два проекта A/B и reader/operator/admin с непересекающимися ACL; `exercise!(fixture, steps)` вызывает реальные domain/REST/MCP handlers и читает test PostgreSQL. Возврат `%{results: list, saved_entities: changed_rows, operations: created_operations, audit: list}`. Это изменённые данным сценарием строки, не вся БД. Constant stubs для domain outcomes запрещены.

W02.02 создаёт `mcp-gateway/test/helpers/wire.ts`: `callMcp(method, params)` делает настоящий initialize/initialized и SDK request по loopback, `countOperations(key)` независимо читает test DB. Такая проверка не подменяет облачный ChatGPT.

## 3. Порядок каждого leaf

До шагов ниже: прочитать его exact JSON-карточку, проверить accepted inputs, записать ACCEPTED с source/scope и открыть отдельный worktree. Setup failure из-за отсутствующего prerequisite не засчитывается как RED продукта. После GREEN: полный diff вместе с тестами, related commit/обычный feature PR, независимые exact-HEAD checks; только затем принятие leaf. Приведённые команды и тестовые примеры здесь не выполнялись.

### SN-031.W01: Реестр команд и полнота покрытия

**Files / inputs:** точная карточка SN-031.W01. Test: `elixir/test/symphony_control/mcp/registry_test.exs`.

- [ ] Создать registry/test helpers. RED — новая UI-only бизнес-команда без MCP mapping:

```elixir
assert {:error, {:missing_mapping, ["issues.archive"]}} =
  Registry.validate([], ["issues.archive"])
```

- [ ] Реализовать перечисление capabilities, точные schemas/roles/risk/version и accepted исключения. Registry не выдаёт права, handler проверяет ACL.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/registry_test.exs --trace`; добавить роль reader и запрещённый cross-project mapping. Сохранить evidence и related commit.

### SN-031.W02.01: OAuth и пользователь

**Files / inputs:** карточка SN-031.W02.01. Test: `elixir/test/symphony_control/mcp/authorization_test.exs`.

- [ ] Создать test issuer/expired grant и RED:

```elixir
assert {:error, :unauthenticated} =
  Authorization.verify(fixture!(:expired_mcp_bearer), "mcp-resource", ["issues.read"])
```

- [ ] Реализовать dedicated resource profile и повторную проверку actor/scopes/current ACL. Проверить wrong aud/issuer, revoked grant, replay code, downgrade PKCE и role revoked между preview/commit. Browser SSO отдельно не доказывает MCP login.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/authorization_test.exs --trace`; сохранить negative evidence, не публикуя bearer.

### SN-031.W02.02: Remote transport и domain bridge

**Files / inputs:** карточка SN-031.W02.02. Test: `mcp-gateway/test/transport.test.ts`.

- [ ] RED с реальными HTTP client/server и потерей ответа после durable command:

```typescript
const response = await callMcp("tools/call", {
  name: "get_operation", arguments: { operation_id: knownOperation }
});
assert.equal(response.structuredContent.operation_id, knownOperation);
assert.equal(await countOperations(knownKey), 1);
```

- [ ] Implement initialize, tools/list pagination, отдельные tools/call, schemas/annotations, OAuth challenge и фиксированный private backend. Check unknown tool, forged actor, stale schema и disconnect; никаких mutations из read-only tool. Закрепить реально совместимые SDK/runtime в lockfile/ADR.
- [ ] GREEN: `cd mcp-gateway && npm ci && npm test -- transport`. Исчерпание timeout возвращает typed unknown/error, не дублирует command.

### SN-031.W03.01: Проекты, карточки, комментарии и ТЗ

**Files / inputs:** карточка SN-031.W03.01. Test: `elixir/test/symphony_control/mcp/tracker_parity_test.exs`.

- [ ] RED: повтор одной create через MCP и REST:

```elixir
state = exercise!(fixture!(:two_projects), [
  %{channel: :mcp, actor: :operator_a, capability: "issues.create",
    arguments: %{project: "A", title: "Synthetic"}, preconditions: %{idempotency_key: "create-1"}},
  %{channel: :rest, actor: :operator_a, capability: "issues.create",
    arguments: %{project: "A", title: "Synthetic"}, preconditions: %{idempotency_key: "create-1"}}
])
assert length(state.saved_entities) == 1
assert Enum.at(state.results, 0).id == Enum.at(state.results, 1).id
```

- [ ] Implement mappings к существующим tracker/spec/plans services; UI читает те же ID. Stale version rejected; новая spec revision не меняет активную attempt незаметно.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/tracker_parity_test.exs --trace`.

### SN-031.W03.02: Планирование, поиск и архив

**Files / inputs:** карточка SN-031.W03.02. Test: `elixir/test/symphony_control/mcp/planning_parity_test.exs`.

- [ ] RED для добавления циклической связи в fixture A-1 → A-2:

```elixir
state = exercise!(fixture!(:dependency_cycle), [
  %{channel: :mcp, actor: :operator_a, capability: "dependencies.add",
    arguments: %{from: "A-2", to: "A-1"}, preconditions: %{expected_version: 1, idempotency_key: "cycle-1"}}
])
assert hd(state.results).error == :dependency_cycle
assert state.saved_entities == []
```

- [ ] Implement hierarchy/milestones/cycles/views/search/archive через их domain owners. Проверить pagination boundaries, невидимую родительскую задачу, отсутствие утечки names/counts и archive/restore parity.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/planning_parity_test.exs --trace`.

### SN-031.W03.03: Вложения, импорт и экспорт

**Files / inputs:** карточка SN-031.W03.03. Test: `elixir/test/symphony_control/mcp/attachments_parity_test.exs`.

- [ ] RED: имя файла без реально переданных bytes:

```elixir
state = exercise!(fixture!(:two_projects), [
  %{channel: :mcp, actor: :operator_a, capability: "attachments.attach",
    arguments: %{issue_id: "A-1", source: "sandbox:/not-transferred.bin"}, preconditions: %{idempotency_key: "attach-1"}}
])
assert hd(state.results).error == :file_bytes_unavailable
assert state.saved_entities == []
```

- [ ] Implement protected upload grant, received-byte hash и разрешённые transfer flows. Negative tests: чужой grant, MIME/size/quarantine, SSRF; произвольного fetch URL нет.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/attachments_parity_test.exs --trace`.

### SN-031.W04.01: Выполнение, вопросы и остановка

**Files / inputs:** карточка SN-031.W04.01. Test: `elixir/test/symphony_control/mcp/execution_parity_test.exs`.

- [ ] RED: попытка незаметно продолжить вручную приостановленный проект:

```elixir
state = exercise!(fixture!(:paused_project_with_run), [
  %{channel: :mcp, actor: :operator_a, capability: "runs.resume",
    arguments: %{run_id: "run-a"}, preconditions: %{expected_version: 3, idempotency_key: "resume-1"}}
])
assert hd(state.results).error == :project_paused
assert state.operations == []
```

- [ ] Implement разные команды pause intake/cancel queued/interrupt active; replies/approvals и reconciled resume через существующие contexts. Lost acknowledgement не создаёт второго writer и не обнуляет budget.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/execution_parity_test.exs --trace`.

### SN-031.W04.02: Настройки, модели и бюджеты

**Files / inputs:** карточка SN-031.W04.02. Test: `elixir/test/symphony_control/mcp/settings_parity_test.exs`.

- [ ] RED: устаревший settings patch:

```elixir
state = exercise!(fixture!(:settings_version_4), [
  %{channel: :mcp, actor: :admin_a, capability: "settings.update",
    arguments: %{project: "A", concurrency: 2}, preconditions: %{expected_version: 3, idempotency_key: "settings-1"}}
])
assert hd(state.results).error == :stale_version
assert state.saved_entities == []
```

- [ ] Implement schema/default/desired/effective settings, routing, budgets и handoff. Проверить concurrent edits, активную attempt, запрещённую модель и UNKNOWN price. Модель не расширяет доступ изменением profile.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/settings_parity_test.exs --trace`.

### SN-031.W04.03: Health, диагностика и recovery

**Files / inputs:** карточка SN-031.W04.03. Test: `elixir/test/symphony_control/mcp/recovery_parity_test.exs`.

- [ ] RED для уже наблюдавшегося запуска после interrupt:

```elixir
state = exercise!(fixture!(:interrupted_observed_run), [
  %{channel: :mcp, actor: :operator_a, capability: "runs.get", arguments: %{run_id: "run-a"}, preconditions: %{}}
])
assert hd(state.results).run_started == true
assert hd(state.results).termination_reason == :operator_interrupted
refute hd(state.results).state == :not_started
```

- [ ] Implement read-only health/incidents и запросы ограниченному recovery executor. Проверить lost restart ack, stale snapshot, maintenance pause, падение gateway. Неисполненная операция и недоступная dependency не маскируются PASS. Полная приёмка требует accepted Health/Recovery domain из PR #3, не его draft-документ.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/recovery_parity_test.exs --trace`.

### SN-031.W04.04: Подключения, роли и provisioning

**Files / inputs:** карточка SN-031.W04.04. Test: `elixir/test/symphony_control/mcp/administration_parity_test.exs`.

- [ ] RED: роль отозвана после preview, модель подставляет approve:

```elixir
state = exercise!(fixture!(:role_revoked_after_preview), [
  %{channel: :mcp, actor: :operator_a, capability: "access.commit",
    arguments: %{preview_id: "preview-a", approve: true}, preconditions: %{expected_version: 2, idempotency_key: "acl-1"}}
])
assert hd(state.results).error == :forbidden
assert state.saved_entities == []
```

- [ ] Implement typed provisioning/access и browser secret enrollment. Проверить чужой target manifest, самоповышение роли и revoked delegation. Выдавать только secret metadata/reference, не token values.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/administration_parity_test.exs --trace`.

### SN-031.W04.05: Review, выпуск и backup/restore

**Files / inputs:** карточка SN-031.W04.05. Test: `elixir/test/symphony_control/mcp/release_restore_parity_test.exs`.

- [ ] RED: несовместимый restore:

```elixir
state = exercise!(fixture!(:incompatible_restore), [
  %{channel: :mcp, actor: :admin_a, capability: "backups.restore",
    arguments: %{backup_id: "backup-a"}, preconditions: %{expected_version: 1, idempotency_key: "restore-1"}}
])
assert hd(state.results).error == :recovery_required
assert state.operations == []
```

- [ ] Implement mappings к quality/release/backup contexts. Проверить changed HEAD, отсутствующий trusted CI, unknown restore и совместимость rollback; MCP не обходит обычные release gates или личные data-loss approvals.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/release_restore_parity_test.exs --trace`.

### SN-031.W04.06: Уведомления и состояние подключения

**Files / inputs:** карточка SN-031.W04.06. Test: `elixir/test/symphony_control/mcp/notifications_parity_test.exs`.

- [ ] RED: сохранённое уведомление ещё не доставлено:

```elixir
state = exercise!(fixture!(:pending_undelivered_notification), [
  %{channel: :mcp, actor: :operator_a, capability: "notifications.get",
    arguments: %{notification_id: "notice-a"}, preconditions: %{}}
])
assert hd(state.results).delivery_state == :pending
refute hd(state.results).read == true
```

- [ ] Implement inbox/operations/connection status с freshness, channel delivery и capability refresh. Закрытый ChatGPT не считается получившим сообщение; reconnect читает тот же operation_id, cached tools/list не даёт новых прав.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/notifications_parity_test.exs --trace`.

### SN-031.W05: Плагин и установка в Coolify

**Files / inputs:** карточка SN-031.W05. Test: `test/e2e/mcp-install.spec.ts`; дополнительно `test/contracts/mcp-deployment.test.mjs`.

- [ ] RED deployment contract: отсутствие gateway health/volume, hard-coded 1c-db mount и попытка выдать Deploy за готовый user consent обязаны проваливать assertions.

```sh
node --test test/contracts/mcp-deployment.test.mjs
```

- [ ] Implement Git-backed Dockerfile/Compose, plugin metadata/skills и onboarding. Использовать закреплённый проверенный формат OpenAI, не выдумывать установленный plugin ID. Выводить нужный endpoint, состояние Authentik и инструкцию consent; обязательные tools работают без виджета.
- [ ] GREEN: `npm exec --offline -- playwright test test/e2e/mcp-install.spec.ts`. Настоящая установка на новом поддерживаемом сервере — scoped fixture с новыми domain/secret refs, без копирования директорий с 1c-db.

### SN-031.W06: Полная cloud ChatGPT приёмка

**Files / inputs:** карточка SN-031.W06. Test: `test/e2e/mcp-parity.spec.ts`; дополнительно `test/contracts/mcp-client-evidence.test.mjs`.

- [ ] RED evidence contract: один обязательный UI action без MCP role-specific evidence, устаревшая server/schema version или CLI/Inspector вместо cloud_chatgpt вызывает FAIL.

```sh
node --test test/contracts/mcp-client-evidence.test.mjs
```

- [ ] Выполнить всю parity suite и реальные cloud шаги: OAuth → tools/list → создать задачу → повторить key → изменить разрешённую настройку → новый чат/прочитать operation → denied cross-project → разрешённый recovery synthetic target → authoritative readback. Записать безопасные object/request IDs, version, UTC и реальные assertions в dossier.
- [ ] GREEN: `npm exec --offline -- playwright test test/e2e/mcp-parity.spec.ts`, затем client-matrix proof. Web/mobile/voice проверяются раздельно; unsupported = BLOCKED, не PASS. Включить исходные AC-77/78/83 и все AC-MCP-01–20. До accepted recovery-domain gate полная приёмка запрещена.

## 4. Передача и границы доказательств

Каждый лист наследует применимые исходные requirements/limits/non-goals SN-031; task refinement содержит commands, fixtures, assertions и все зависимости. Первой допустима W01 только после принятия SN-005/SN-014/SN-029. Продуктовые prerequisites не считаются выполненными из-за наличия этого плана или observer PR.

Полный MCP backend в этой итерации не реализован. Структурные проверки плана не заменяют product tests, независимое review, проверку текущего Authentik, реального ChatGPT аккаунта или Docker-развёртывания. Нет model calls, запуска Symphony, merge или deploy; никакие новые токены не требуются для чтения плана.

## 5. Технические источники

Сверены 23.09.2026: OpenAI Build an MCP server — https://developers.openai.com/plugins/build/mcp-server ; Authentication — https://developers.openai.com/plugins/build/auth ; MCP transports — https://modelcontextprotocol.io/specification/2025-11-25/basic/transports ; authorization — https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization . Это основания механизма, не evidence нашей реализации. Конкретный version pin принимается по реальному compatibility test в W02.02.

План подготовлен к независимому review вместе с `planning/mcp-execution.json`. Исполнение сохраняет выбранный путь: отдельный Symphony, один writer, explicit admission и отдельное предупреждение перед реальным запуском в tmux.

## Исправление review от 23.09.2026 — контракт входов SN-032

Отчёт независимого review SHA256 `154ae22e36420d9f450fc93a169417dd9a5be2dd90aecccfcbb7acde5a405272` обнаружил, что одного изменения depends_on недостаточно. В refinement r2 явный override проверяет весь исходный interfaces.consumes и заменяет его одновременно с depends_on. Нельзя сохранять требование accepted полного SN-031, когда планировщик объявляет достаточным W02.02. Неизвестное поле override или несовпадение expected списка даёт planning hold, не игнорирование.

Семантический граф проверки включает объединение depends_on и task references из эффективных interfaces.consumes. Каждый consume обязан ссылаться на существующий prerequisite (прямой либо транзитивный), а не на будущего dependent. Проверять только формальные depends_on недостаточно. Все исходные поля, кроме явно разрешённых replacements/additions, сохраняются; полный SN-031/W06 по-прежнему блокирует приёмку SN-042/043/044.

Регрессия пакета (не реализация native importer):

```sh
python3 -B -m unittest discover -s tests -p test_mcp_input_contracts.py -v
```

Для проверки JSON Schema тест использует `jsonschema` из среды проверяющего; новую зависимость runtime продукта эта правка не устанавливает. Сценарии проверяют прежний скрытый цикл, точный expected контракт, отказ при изменённом baseline, обязательность обоих полей override, сохранность прочих полей и финальной полной приёмки.
