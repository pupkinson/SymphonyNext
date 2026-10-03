# SN-004 canonical requirements excerpt

This document copies the complete assigned SN-004 task, all of its owned
ARCH/DATA requirements and acceptance rows, and the selected invariant/security
context below. It supplies small, complete review input when the large canonical
files exceed a source tool response limit. It is a subset of the product
specification, not a replacement, implementation report or acceptance approval.
Requirements outside this subset remain applicable to their own scope.

The canonical files are unchanged from PR14 base `2bf21950e0725bc9228b262e1495f5af5eeea1d6`:

- [SPECIFICATION.md](../../SPECIFICATION.md) SHA256 `b107299574b8717e45d9fc58e8f204b37b441344c8c559e5e65a8113d10238a6`.
- [TASKS.md](../../TASKS.md) SHA256 `4ddfbeabf36a43064bfc84c6385be2bb6bd4bb58441d09556651d660b710fa11`.
- [planning/backlog.json](../../planning/backlog.json) SHA256 `c2a0e1a51409bd82c4dda0c5195b60926d311a64098d28defd14842c9a77b4f0`.

The task and quoted paragraphs/rows below are verbatim copies of those bytes.
TASKS.md and planning/backlog.json assign the same 16 requirement IDs and two
acceptance IDs to SN-004. The canonical sources govern any future change; refresh
this copy and its manifest digest when those sources change. SN-003 prerequisite
acceptance, complete SN-004/product acceptance, execution and release gates
remain separate facts. No completed gate is asserted here.

## Assigned task from TASKS.md

## SN-004 — Domain API, PostgreSQL и идентификация сборки

**Эпик:** E01 Foundation. **Зависимости:** SN-003. **Статус:** planned, admission выключен.

Добавить модульный control/tracker без второго scheduler: Ecto migrations, domain contexts, typed errors, health/live, health/ready и versioned runtime identity.

**Создать/изменить:** `elixir/lib/symphony_control/repo.ex`; `elixir/lib/symphony_control/health.ex`; `elixir/priv/repo/migrations`; `elixir/lib/symphony_control/application.ex`.

**Тест:** `elixir/test/symphony_control/repo_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Реальная disposable PostgreSQL; чистая DB, уже migrated DB, partial migration, unavailable DB.

**Обязательный проверяемый результат:**
1. Миграции идемпотентны; readiness=false при несовпадении schema.
2. Live не выдаёт секреты; ready подтверждает DB/migration/required local dependencies.
3. Commit/image/config identity доступна отдельным authorised readback.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/repo_test.exs
git diff --check
```

**Шаги:**
- [ ] Fresh fetch; verify exact source/base, open branch/PR and accepted dependencies; no stale main.
- [ ] Create one isolated feature worktree. Capture ACCEPTED with issue/spec/policy/base and allowed paths.
- [ ] Write regression/integration fixtures described below. Run and save genuine RED; infrastructure setup failure is not a product regression.
- [ ] Implement minimal scoped delta. Execute targeted tests on real fixture, then relevant broader/static suite.
- [ ] Review complete diff including tests, secret scan, document behavior and failure/rollback. Commit related delta and non-force push feature branch.
- [ ] Obtain separate exact-HEAD review/trusted checks; delegated merge and webhook deploy only when gates apply and configured.
- [ ] Independently read actual runtime/artifacts; persist evidence and result. Stop with classified diagnosis when acceptance cannot be proved.

**Требования-owners:** ARCH-01, ARCH-02, ARCH-03, ARCH-04, ARCH-05, ARCH-06, ARCH-07, DATA-01, DATA-02, DATA-03, DATA-04, DATA-05, DATA-06, DATA-07, DATA-08, DATA-09.

**Приёмка:** AC-15, AC-19.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## Owned requirements from SPECIFICATION.md

**ARCH-01.** Core и проектные runner — отдельные Coolify Application/Compose-ресурсы с независимыми release manifests. Обновление runner A не должно пересоздавать runner B. Один общий стек со всеми проектами не выбирается как production default: stack-level lifecycle связывает их обновления. [S5, S14]

**ARCH-02.** В MVP runner заранее разворачивает оператор штатным repository/PR/CI/webhook path. UI регистрирует проект и показывает потребность в provisioning, но не создаёт Docker-контейнеры широким API-ключом. Добавление очередного проекта требует новых конфигурации/ресурса/identity, а не нового кода или второго scheduler.

**ARCH-03.** Control → runner: частный аутентифицированный transport с project/slot identity, attempt и fencing epoch; сертификат/credential A не подходит для B. У агента нет прямого доступа к transport credential управляющего процесса. Native agent servers, включая Codex App Server, наружу не публикуются.

**ARCH-04.** Агент исполняет недоверенный код. UID, mounts, секреты и процессы отделены от supervisor. Нет privileged, host PID/network или Docker socket. Совместимость sandbox и контейнерного hardening подтверждается exact-version тестами, не обходится незаметным ослаблением защиты. [S11]

**ARCH-05.** Один runner slot закреплён за одним project_id и не переиспользуется между проектами. Раздельны workspace, HOME/engine-state (включая CODEX_HOME), временные файлы, Git config/keys, model-session state, tool/MCP bindings и журналы. Общим может быть immutable базовый image; mutable dependency caches по умолчанию раздельны.

**ARCH-06.** Проекты имеют отдельные private networks; разрешён только нужный transport к control и согласованный egress. Runner не подключается к общей сети всех production-сервисов ради удобства. Конкретный маршрут между ресурсами фиксируется до deploy и проверяется отрицательными сетевыми тестами: отдельное Compose-имя само по себе не является полным security boundary. [S12]

**ARCH-07.** Control и его DB остаются общими зависимостями нового продукта: их сбой может затронуть все проекты. Разделение runner не обещает HA или защиту от компрометации общего ядра хоста. Для взаимно недоверенных организаций/особо опасных workloads нужен отдельный host/VM либо усиленный runtime по отдельному ADR; выбирать его автоматически не требуется. [S11]

**DATA-01.** PostgreSQL собственного продукта — authoritative source задач, бизнес-статусов, комментариев/workpad, документов и отдельного состояния исполнения. Tracker и Execution — разные домены одной БД, не зеркала Linear. GitHub — источник commits/PR/checks; runner — источник наблюдений о процессе. UI cache/search index/outbox не являются альтернативным backlog.

**DATA-02.** Минимальные сущности: projects/memberships; issue_status_schemes/statuses, issues/revisions, labels/issue_labels, issue_relations, comments/workpads, documents/document_versions, attachments, cycles/milestones, saved_views/subscriptions, issue_activity/import_batches; repository_bindings, workflow_versions/policy_versions; runs/attempts, runner_slots/bindings, project_limits/provider_quota_pools, leases, commands, approval_requests/user_inputs, run_events/artifacts, provider_operations, engine_profiles/model_catalog_snapshots/routing_decisions, task_stage_runs/handoff_manifests, budget_reservations/usage_events/cost_reconciliations, evaluation_sets/evaluation_runs, device_push_subscriptions, outbox_messages/notification_deliveries/audit_events. Это логическая схема для проектирования migrations, не существующие production tables.

**DATA-03.** Issue — задание; run — его логическое выполнение; attempt — конкретный запуск. Retry создаёт новую attempt, не стирая старую. Каждый run ссылается на native issue_id/project_id и immutable execution snapshot описания, критериев, разрешённых комментариев/вложений. Внутреннее представление work item у adapter не создаёт вторую каноническую карточку.

**DATA-04.** Для attempt сохраняются upstream/fork/agent/adapter versions, requested/resolved/observed model identity, catalog/routing versions, stage/role, image digest, workflow/policy hashes, repo URL, base/head/tree SHA, branch/PR, workspace identity, runner generation, timestamps и результат проверок. Недоступные поля явно UNKNOWN, не вычисляются по имени ветки.

**DATA-05.** Разрешённое изменение issue, revision/activity и соответствующее outbox/admission intent сохраняются в одной DB transaction. Claim повторно проверяет issue_version, admission, зависимости, membership/policy и свободный slot атомарно. События имеют ID и монотонную последовательность в пределах issue/run; доставка at-least-once, consumers дедуплицируют. Потеря wakeup не теряет задачу: есть периодическая сверка долговечного состояния.

**DATA-06.** Роли приложения не могут произвольно исправлять audit history. Содержимое артефактов хранится отдельно от метаданных; применяются hash, size, media type, project scope и срок хранения.

**DATA-07.** Бизнес-статус issue, admission и runtime state раздельны даже в одной БД. Агент закончил turn, PR создан, tests passed, review accepted, issue Done, merged и deployed — разные факты. Источник и timestamp каждого факта доступны в карточке.

**DATA-08.** Все проектные данные, команды, артефакты, event subscriptions и cache keys имеют обязательный project_id. Foreign keys/constraints исключают связь attempt A с request или runner B. Доступ проверяется и для direct ID, поиска, экспорта и live-stream. Общая DB не является разрешением читать все строки.

**DATA-09.** Не более одного active claim по native issue_id и slot; composite FK/constraints связывают project_id всех отношений. Зеркала импорта не могут создать второй активный владелец той же исходной задачи. Сводки/экспорты агрегируют только доступные actor проекты; служебный DB owner не выдаётся приложению/агенту как пользовательский инструмент.

## Assigned acceptance rows from SPECIFICATION.md

| ID | Сценарий | Критерий PASS |
| --- | --- | --- |
| AC-15 | DB down / disk full | Нет фиктивно принятых команд; fail-closed admission; восстановление через reconciliation |
| AC-19 | Deploy/restart/reboot | Exact image/commit/config известны; persistence есть; intake не открывается до reconciliation |

## Invariant and security context from SPECIFICATION.md

**INV-01.** Запрещены изменения работающих процессов, WORKFLOW, окружения, Git/SSH-профилей, авторизации Codex, туннелей, user units, workspace, очереди и разрешений текущего DF Assistant ради разработки Symphony Control.

**INV-02.** Новый продукт получает отдельные репозиторий разработки, локальный проект в собственном трекере, deployment-ресурсы Coolify, домен, базу/DB-роли и служебные identities. До готовности трекера начальный backlog хранится в Git по разделу 17.2; создавать обязательный Linear-проект не требуется. Каждый подключённый проект получает собственные runner identity, credentials и writable volumes. Общие writable-каталоги с действующим Symphony запрещены. Существующие Authentik и Coolify используются повторно, но не чужие client secrets или DB-роли.

**INV-03.** Приём задач из проекта DF Assistant Bot и запись в pupkinson/dfassistant из нового контура запрещены политикой по умолчанию. Их возможное подключение — будущая отдельная миграционная задача с явным переключением владельца очереди.

**INV-04.** Одновременная работа старого и нового продуктов допустима только с непересекающимися проектами, задачами, workspace и полномочиями. Два исполнителя одной задачи недопустимы. Несколько разных проектов внутри Symphony Control должны исполняться параллельно; ограничение одного владельца относится к задаче/слоту, а не ко всей платформе.

**INV-05.** Интеграция Authentik ограничивается новым application/provider и относящимися к нему mappings/bindings. Нельзя ради нового продукта обновлять, пересоздавать или менять глобальные flows, существующие providers, DNS и рабочие сессии других приложений. Нужная общая инфраструктурная доработка требует отдельного согласования.

**SEC-01.** Секреты не размещаются в git, image layers, build args, issue, workflow, argv, UI, audit payload, logs или артефактах. Используются runtime secret references и независимые identities нового проекта. Существующие credentials DF Assistant не копируются.

**SEC-02.** Раздельные полномочия для model auth, native tracker tools, GitHub publication, runner transport, DB и инфраструктуры. Agent child не наследует управляющие переменные окружения. Одного удаления env недостаточно: проверяются UID, filesystem mounts, /proc, metadata service и доступ к локальным sockets.

**SEC-03.** Git-доступ ограничен repository bindings конкретного нового проекта. Repo-scoped read credentials не разделяются с другими runner; публикация write проходит через project/operation-aware boundary из SEC-04. Для API — минимально scoped GitHub App или утверждённый short-lived механизм. Общий постоянный широкий PAT и копирование credentials текущего DF Assistant запрещены.

**SEC-04.** Изменения native tracker и Git/PR publication проходят через project/operation-aware domain endpoints/broker. Agent не получает DB credentials, raw SQL/GraphQL или универсальный tracker admin token. Project/task/attempt/epoch извлекаются из доверенного назначения, не из аргумента модели; старый fencing epoch не выполняет mutation. UI и tools используют одинаковые ограничения, но разные actor capabilities.

**SEC-05.** Runner не получает root/sudo/Docker socket, host filesystem, host network или публичный control port. Базовые контейнерные ограничения: non-root, drop capabilities, no-new-privileges, контролируемые writable mounts, ресурсные лимиты и совместимый sandbox. Docker daemon относится к привилегированному control surface, не к инструментам worker. [S11]
