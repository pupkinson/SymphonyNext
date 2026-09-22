# Symphony Next — пакет задач v0.5

> Исполнитель: отдельный stock Symphony. Каноническое машиночитаемое представление — `planning/backlog.json`; трассировка — `planning/traceability.json`. Это задания к реализации, не отчёт о готовом продукте.

## Порядок и правила выполнения

**Текущая граница:** установка окружения выполняется оператором вне DAG продукта. SN-001 пока BLOCKED: точная серверная запись `tools/validate_package.py` отклонена платформой (PUP-179), новый private repo/credentials ещё не созданы (PUP-250). Отказ не обходить передачей той же операции другому инструменту/агенту. Остальные карточки описывают целевую реализацию, не запущенные процессы.

Начать с одного допущенного SN-001 после проверки новой identity/repo/auth. Planner, implementer, reviewer и release-verifier — роли и последовательные стадии. Много разных агентов не запускаются ради самого количества. Две независимые продуктовые очереди включаются после SN-038. Тесты указаны как обязательные команды будущей реализации; наличие строки команды не является фактом её запуска.

Общий контракт ошибок: `invalid_input`, `forbidden`, `conflict`, `dependency_unavailable`, `unknown_outcome`. Версионированный envelope результата: task/spec/attempt/policy/base/head/tree/outcome/evidence. Планировщик уточняет внутренние API в ADR до реализации зависимых задач, не меняя согласованную внешнюю семантику и security invariants.

Временный GitHub Issues adapter stock Symphony используется только в новом private repo. Backlog JSON не является автоматически работающим tracker adapter. Материализация задач и admission требуют отдельной readback-проверки; dispatch по умолчанию выключен. После собственного native tracker — один явный cutover без двух competing очередей.

## Дорожная карта зависимостей

| Задача | Результат | Зависимости | Риск |
| --- | --- | --- | --- |
| SN-001 | Пакет требований, DAG и первый проверяемый PR | Нет | low |
| SN-002 | Изолированный bootstrap и проверенный полный Codex | SN-001 | high |
| SN-003 | Форк pinned upstream и доверенный non-Actions CI | SN-001 | high |
| SN-004 | Domain API, PostgreSQL и идентификация сборки | SN-003 | high |
| SN-005 | Authentik SSO, роли, project ACL и отзыв доступа | SN-004 | high |
| SN-006 | Реестр проектов и непересекающиеся bindings | SN-005 | high |
| SN-007 | Полноценные задачи и optimistic concurrency | SN-006 | medium |
| SN-008 | Комментарии, workpad, ТЗ и versioned documents | SN-007 | medium |
| SN-009 | Защищённые вложения и артефакты | SN-007 | high |
| SN-010 | Иерархия, зависимости, milestones и циклы | SN-007, SN-008 | medium |
| SN-011 | Локальный поиск, доска и сохранённые представления | SN-007, SN-008, SN-010 | medium |
| SN-012 | Durable inbox и outbox уведомлений | SN-008 | medium |
| SN-013 | Архивирование, экспорт и однократный импорт | SN-009, SN-010, SN-011 | high |
| SN-014 | Durable команды и state machine | SN-004, SN-006, SN-007 | high |
| SN-015 | Один scheduler, leases, epochs и admission | SN-010, SN-014 | high |
| SN-016 | Runner protocol и изоляция процессов проектов | SN-014, SN-015 | high |
| SN-017 | Codex App Server adapter | SN-016 | high |
| SN-018 | Второй независимый агент через локальный SDK | SN-016, SN-017 | high |
| SN-019 | Каталог capabilities и безопасные обновления adapters | SN-017, SN-018 | high |
| SN-020 | Вопросы агенту, scoped approvals и deadline | SN-005, SN-014, SN-017 | high |
| SN-021 | Reconciliation после сбоев и остановка intake | SN-015, SN-016, SN-020 | high |
| SN-022 | Диагностический пакет и безопасная классификация ошибок | SN-012, SN-014, SN-016 | high |
| SN-023 | Конечные retries, backoff и unknown writes | SN-021, SN-022 | high |
| SN-024 | Local watchdog и stop при partition | SN-016, SN-021, SN-023 | high |
| SN-025 | Usage ledger и атомарные бюджетные резервы | SN-014, SN-019 | high |
| SN-026 | Routing manual/recommend/auto и risk floor | SN-019, SN-025, SN-022 | high |
| SN-027 | Память проекта, context manifest и allowlisted skills | SN-008, SN-009, SN-019 | high |
| SN-028 | Проверяемая передача между агентами | SN-021, SN-025, SN-027 | high |
| SN-029 | Spec → planner → проверяемый DAG задач | SN-010, SN-014, SN-026, SN-027 | high |
| SN-030 | Независимый review и защищённая приёмка | SN-003, SN-017, SN-029 | high |
| SN-031 | Authenticated MCP для ChatGPT и API parity | SN-005, SN-014, SN-029 | high |
| SN-032 | Typed provisioning GitHub/Coolify/Authentik | SN-006, SN-014, SN-031 | high |
| SN-033 | Автоматический release через штатный webhook | SN-030, SN-032 | high |
| SN-034 | Runtime acceptance и безопасный автоматический rollback | SN-021, SN-033 | high |
| SN-035 | Mobile-first интерфейс полного трекера и запусков | SN-011, SN-012, SN-020, SN-026 | medium |
| SN-036 | Мобильные approvals, reconnect и потерянное устройство | SN-035, SN-005 | high |
| SN-037 | Проверяемые уведомления на телефон | SN-012, SN-036 | medium |
| SN-038 | Два параллельных проекта, квоты и независимые обновления | SN-018, SN-025, SN-033 | high |
| SN-039 | Резервное копирование и полное восстановление | SN-013, SN-021, SN-025 | high |
| SN-040 | Оценка маршрутизатора и экономика результата | SN-026, SN-030 | medium |
| SN-041 | Наблюдаемость, SLO и эксплуатационные runbooks | SN-022, SN-024, SN-039 | medium |
| SN-042 | Сквозной автономный milestone до рабочего сервиса | SN-029, SN-031, SN-034, SN-035, SN-038 | high |
| SN-043 | Переход с bootstrap на собственный трекер | SN-013, SN-039, SN-042 | high |
| SN-044 | Финальный fault-injection soak и acceptance dossier | SN-036, SN-037, SN-038, SN-039, SN-040, SN-041, SN-042, SN-043 | high |

## SN-001 — Пакет требований, DAG и первый проверяемый PR

**Эпик:** E00 Bootstrap. **Зависимости:** Нет. **Статус:** BLOCKED (см. текущие ограничения SN-001), admission выключен.

В новом репозитории зафиксировать ТЗ v0.5, подтвердить полноту задач и ссылок, воспроизводимо проверить validators. Не перепроектировать согласованную систему. Первый stock worker публикует только related docs/config PR.

**Создать/изменить:** `SPECIFICATION.md`; `TASKS.md`; `planning/backlog.json`; `tools/validate_package.py`; `PROJECT_RULES.md`.

**Тест:** `tests/test_package.py`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Копии backlog с циклом, отсутствующим dependency, неизвестным requirement, leaf без test, лишним admission и устаревшим запретом deploy.

**Обязательный проверяемый результат:**
1. Валидный пакет проходит; каждый повреждённый fixture отклоняется с точным кодом.
2. Изменения ограничены новой веткой нового repo; существующий DF не прочитан и не изменён.
3. Реальный worker создаёт один commit/PR; повтор запуска не создаёт дубликат; labels снимаются до завершения пилота.

**Команды после реализации:**
```sh
python3 -B -m unittest discover -s tests -v
python3 -B tools/validate_package.py
```

**Шаги:**
- [ ] Fresh fetch; verify exact source/base, open branch/PR and accepted dependencies; no stale main.
- [ ] Create one isolated feature worktree. Capture ACCEPTED with issue/spec/policy/base and allowed paths.
- [ ] Write regression/integration fixtures described below. Run and save genuine RED; infrastructure setup failure is not a product regression.
- [ ] Implement minimal scoped delta. Execute targeted tests on real fixture, then relevant broader/static suite.
- [ ] Review complete diff including tests, secret scan, document behavior and failure/rollback. Commit related delta and non-force push feature branch.
- [ ] Obtain separate exact-HEAD review/trusted checks; delegated merge and webhook deploy only when gates apply and configured.
- [ ] Independently read actual runtime/artifacts; persist evidence and result. Stop with classified diagnosis when acceptance cannot be proved.

**Требования-owners:** Верификация требований зависимых задач; общие INV обязательны.

**Приёмка:** AC-79, AC-93, AC-94.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-002 — Изолированный bootstrap и проверенный полный Codex

**Эпик:** E00 Bootstrap. **Зависимости:** SN-001. **Статус:** planned, admission выключен.

Принять уже подготовленные pinned runtime bytes в dedicated identity, отдельно авторизовать новый model profile и repo-scoped Git, проверить одну реальную задачу stock Symphony. Это bootstrap, не целевой продукт.

**Создать/изменить:** `bootstrap/owner_install.py`; `bootstrap/symphony-next-bootstrap.service`; `bootstrap/WORKFLOW.github.example.md`; `bootstrap/owner_readback.py`.

**Тест:** `tests/test_install_runtime.py`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Отдельный UID, пустой HOME, пустой memory tracker для smoke; новая private GitHub issue с уникальной pilot label; старый DF target запрещён.

**Обязательный проверяемый результат:**
1. Checksum и sidecars совпадают; codex --version/app-server schema проверены.
2. Служба не имеет sudo/Docker/groups старого контура; не читает DF home; без readiness marker не стартует.
3. Один model turn/commit/PR наблюдаемы; старые PID/workspace не изменены.
4. Stock memory-only blocked не принимается за durable target recovery; pilot bounded и без blind restart.

**Команды после реализации:**
```sh
python3 -B -m unittest discover -s tests -v
python3 -B bootstrap/owner_readback.py
```

**Шаги:**
- [ ] Fresh fetch; verify exact source/base, open branch/PR and accepted dependencies; no stale main.
- [ ] Create one isolated feature worktree. Capture ACCEPTED with issue/spec/policy/base and allowed paths.
- [ ] Write regression/integration fixtures described below. Run and save genuine RED; infrastructure setup failure is not a product regression.
- [ ] Implement minimal scoped delta. Execute targeted tests on real fixture, then relevant broader/static suite.
- [ ] Review complete diff including tests, secret scan, document behavior and failure/rollback. Commit related delta and non-force push feature branch.
- [ ] Obtain separate exact-HEAD review/trusted checks; delegated merge and webhook deploy only when gates apply and configured.
- [ ] Independently read actual runtime/artifacts; persist evidence and result. Stop with classified diagnosis when acceptance cannot be proved.

**Требования-owners:** BOOT-01, BOOT-02, BOOT-03, BOOT-04, BOOT-05, BOOT-06, BOOT-08, INV-01, INV-02, INV-03, INV-04, INV-05.

**Приёмка:** AC-01, AC-93, AC-94.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-003 — Форк pinned upstream и доверенный non-Actions CI

**Эпик:** E00 Bootstrap. **Зависимости:** SN-001. **Статус:** planned, admission выключен.

Создать новый private development repository на exact upstream commit с сохранением лицензии. Зафиксировать toolchain и baseline; подключить проверяющий CI вне writer trust boundary, не включая GitHub Actions.

**Создать/изменить:** `elixir/mix.exs`; `elixir/mix.lock`; `ci/verify.sh`; `ci/policy.json`; `docs/adr/0001-upstream-and-ci.md`.

**Тест:** `test`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Чистый clone pinned SHA и отдельный candidate branch; намеренно проваленный тест; успешный status другого SHA; попытка writer подписать status.

**Обязательный проверяемый результат:**
1. Baseline тесты реально запущены и результаты сохранены; исходные failures классифицированы.
2. PR не merge-ится без конкретного passing trusted check точного HEAD.
3. Отсутствующий проверяющий не подменяется словом CI PASS.
4. Source provenance, лицензия и ветки нового repo подтверждены readback.

**Команды после реализации:**
```sh
cd elixir && mix deps.get --check-locked
cd elixir && mix test
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

**Требования-owners:** Верификация требований зависимых задач; общие INV обязательны.

**Приёмка:** AC-84, AC-96.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

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

## SN-005 — Authentik SSO, роли, project ACL и отзыв доступа

**Эпик:** E01 Foundation. **Зависимости:** SN-004. **Статус:** planned, admission выключен.

Подключить собственное OIDC-приложение к существующему Authentik. Реализовать audience/issuer/nonce/PKCE/session validation и серверную авторизацию всех операций.

**Создать/изменить:** `elixir/lib/symphony_control/auth.ex`; `elixir/lib/symphony_control_web/plugs/authorize.ex`; `elixir/lib/symphony_control_web/oidc_controller.ex`.

**Тест:** `elixir/test/symphony_control/auth_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Отдельный тестовый OIDC provider/client; expired/wrong audience/token replay; роли viewer/contributor/operator/approver/admin; две вкладки и отзыв группы.

**Обязательный проверяемый результат:**
1. Чужая role/project claim не даёт доступ; browser/API/WS защищены.
2. Отзыв действует в пределах SLO на уже открытом канале.
3. Существующие Authentik flows/providers и чужая SSO интеграция не изменены.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/auth_test.exs
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

**Требования-owners:** AUTH-01, AUTH-02, AUTH-03, AUTH-04, AUTH-05, AUTH-06, AUTH-07, AUTH-08, AUTH-09, SEC-01, SEC-02, SEC-03, SEC-04, SEC-05, SEC-06, SEC-07, SEC-08, SEC-10.

**Приёмка:** AC-02, AC-03, AC-22, AC-30.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-006 — Реестр проектов и непересекающиеся bindings

**Эпик:** E01 Foundation. **Зависимости:** SN-005. **Статус:** planned, admission выключен.

Создать project descriptors, memberships, repository/workspace/runner bindings и типизированные limits. Ручной tracker не требует runner.

**Создать/изменить:** `elixir/lib/symphony_control/projects.ex`; `elixir/lib/symphony_control/projects/project.ex`; `elixir/lib/symphony_control/projects/binding.ex`.

**Тест:** `elixir/test/symphony_control/projects_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Проекты A/B/C с разными repo/identity; повтор repo source mapping; попытка bind pupkinson/dfassistant.

**Обязательный проверяемый результат:**
1. Bindings уникальны; запрещённый target отклонён до side effects.
2. Архивированный проект не dispatch-ится; новый проект добавляется конфигурацией.
3. Project ACL работает для counts, errors и metadata, не только страниц.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/projects_test.exs
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

**Требования-owners:** DEC-01, DEC-02, DEC-03, DEC-04, DEC-05, DEC-06, DEC-07, PRJ-01, PRJ-02, PRJ-03, PRJ-04, PRJ-05, TSK-07.

**Приёмка:** AC-24, AC-28, AC-33.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-007 — Полноценные задачи и optimistic concurrency

**Эпик:** E02 Native tracker. **Зависимости:** SN-006. **Статус:** planned, admission выключен.

Native issue CRUD со стабильными IDs, описаниями, acceptance, статусами, priority, assignee, labels и due dates. Статус задачи не равен runtime state.

**Создать/изменить:** `elixir/lib/symphony_control/tracker/issues.ex`; `elixir/lib/symphony_control/tracker/issue.ex`; `elixir/lib/symphony_control_web/issue_controller.ex`.

**Тест:** `elixir/test/symphony_control/issues_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Две конкурентные правки expected_version; повтор create key; multi-project equal display key; запрос без model credentials.

**Обязательный проверяемый результат:**
1. Одна запись либо явный conflict; потерянные изменения исключены.
2. CRUD доступен без AI и без обращения к Linear.
3. Todo/assignee/drag/import сами не создают attempt.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/issues_test.exs
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

**Требования-owners:** TSK-01, TSK-02, TSK-03, TSK-05, TSK-16.

**Приёмка:** AC-35, AC-36, AC-37, AC-45.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-008 — Комментарии, workpad, ТЗ и versioned documents

**Эпик:** E02 Native tracker. **Зависимости:** SN-007. **Статус:** planned, admission выключен.

Добавить threads, mentions, subscriptions, один versioned workpad, документы проекта и accepted spec revisions. Отделить обсуждение от команд исполнения.

**Создать/изменить:** `elixir/lib/symphony_control/tracker/comments.ex`; `elixir/lib/symphony_control/documents.ex`; `elixir/lib/symphony_control/specifications.ex`.

**Тест:** `elixir/test/symphony_control/comments_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Concurrent edit workpad; новый scope во время run; комментарий с текстом команды, HTML и ложным approval.

**Обязательный проверяемый результат:**
1. Документы и история переживают удаление run logs.
2. Принятое ТЗ immutable; правка создаёт revision и scope hold.
3. Комментарий не разрешает действие и не расширяет model context сам собой.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/comments_test.exs
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

**Требования-owners:** TSK-08.

**Приёмка:** AC-36, AC-40, AC-78.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-009 — Защищённые вложения и артефакты

**Эпик:** E02 Native tracker. **Зависимости:** SN-007. **Статус:** planned, admission выключен.

Локальное хранилище с project ACL, квотами, проверяемой выдачей, immutable evidence hashes, безопасными MIME и сроками хранения.

**Создать/изменить:** `elixir/lib/symphony_control/artifacts.ex`; `elixir/lib/symphony_control_web/artifact_controller.ex`; `elixir/lib/symphony_control/artifacts/storage.ex`.

**Тест:** `elixir/test/symphony_control/artifacts_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Файлы с traversal, active HTML/SVG, oversized payload, запрещённый project ID; scoped agent download.

**Обязательный проверяемый результат:**
1. Неавторизованный клиент не читает bytes или signed locator.
2. Размер/тип/path проверяются до записи; private cache исключён.
3. Run получает только manifest разрешённых snapshots.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/artifacts_test.exs
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

**Требования-owners:** SEC-09, TSK-13.

**Приёмка:** AC-16, AC-41.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-010 — Иерархия, зависимости, milestones и циклы

**Эпик:** E02 Native tracker. **Зависимости:** SN-007, SN-008. **Статус:** planned, admission выключен.

Ввести initiative/epic/task/subtask, checklist, relates/blocks/duplicates, milestones/cycles и проверяемые формулы прогресса.

**Создать/изменить:** `elixir/lib/symphony_control/tracker/dependencies.ex`; `elixir/lib/symphony_control/tracker/milestones.ex`; `elixir/lib/symphony_control/tracker/cycles.ex`.

**Тест:** `elixir/test/symphony_control/dependencies_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Cycle A→B→C→A; self-link; canceled blocker; reopen accepted task; carryover cycle.

**Обязательный проверяемый результат:**
1. Циклы/чужие связи отклонены атомарно.
2. Canceled и review не считаются принятым результатом.
3. Dependency reopen блокирует новый admission без ретроактивного изменения прошедшего evidence.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/dependencies_test.exs
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

**Требования-owners:** TSK-06, TSK-11.

**Приёмка:** AC-38, AC-46.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-011 — Локальный поиск, доска и сохранённые представления

**Эпик:** E02 Native tracker. **Зависимости:** SN-007, SN-008, SN-010. **Статус:** planned, admission выключен.

Список, Kanban, backlog, фильтры, группировка, saved views и локальный полнотекстовый поиск RU/EN с PostgreSQL как source of truth.

**Создать/изменить:** `elixir/lib/symphony_control/tracker/search.ex`; `elixir/lib/symphony_control/tracker/views.ex`; `elixir/lib/symphony_control_web/live/board_live.ex`.

**Тест:** `elixir/test/symphony_control/search_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Русский/английский текст, exact issue ID, emptyquery, revoked project membership, два проекта с одинаковыми словами.

**Обязательный проверяемый результат:**
1. Board/list/search показывают один набор данных.
2. Snippets/counts/export/live events не раскрывают чужой проект.
3. Нет обязательных внешних search/analytics assets.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/search_test.exs
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

**Требования-owners:** TSK-04, TSK-09, TSK-10.

**Приёмка:** AC-35, AC-42, AC-45.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-012 — Durable inbox и outbox уведомлений

**Эпик:** E02 Native tracker. **Зависимости:** SN-008. **Статус:** planned, admission выключен.

Сохранить события, subscriptions, mentions, delivery attempts и read/ack отдельно; предоставить локальный decision inbox.

**Создать/изменить:** `elixir/lib/symphony_control/notifications.ex`; `elixir/lib/symphony_control/outbox.ex`; `elixir/lib/symphony_control_web/live/inbox_live.ex`.

**Тест:** `elixir/test/symphony_control/notifications_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Коммит DB при недоступном delivery; повтор event; crash между send и ack; revoke.

**Обязательный проверяемый результат:**
1. Одна domain event и durable pending delivery; deliveryunknown не выдаётся за delivered.
2. Недоступность внешнего канала не мешает сохранить stop.
3. Inbox работает без GitHub/model.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/notifications_test.exs
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

**Требования-owners:** TSK-12.

**Приёмка:** AC-18, AC-42, AC-73, AC-92.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-013 — Архивирование, экспорт и однократный импорт

**Эпик:** E02 Native tracker. **Зависимости:** SN-009, SN-010, SN-011. **Статус:** planned, admission выключен.

Экспорт полного tracker manifest и attachments, безопасный import с ID mapping, архив/restore, без неявного enqueue или переноса секретов.

**Создать/изменить:** `elixir/lib/symphony_control/tracker/transfer.ex`; `elixir/lib/symphony_control/tracker/archive.ex`; `schemas/tracker-export.schema.json`.

**Тест:** `elixir/test/symphony_control/transfer_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Roundtrip проекта A; повтор import key; active issue archive/delete/move; права отозванного пользователя.

**Обязательный проверяемый результат:**
1. Повтор не дублирует задачи/связи/comments.
2. Active issue нельзя удалить/перенести без drain.
3. Restore сохраняет IDs, import отображает mapping; admission выключен.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/transfer_test.exs
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

**Требования-owners:** TSK-14, TSK-15.

**Приёмка:** AC-43, AC-44, AC-47.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-014 — Durable команды и state machine

**Эпик:** E03 Execution. **Зависимости:** SN-004, SN-006, SN-007. **Статус:** planned, admission выключен.

Ввести task/attempt/session/request/command как разные сущности. Реализовать expected version, command idempotency, append-only events и typed outcomes.

**Создать/изменить:** `elixir/lib/symphony_control/commands.ex`; `elixir/lib/symphony_control/execution/attempt.ex`; `elixir/lib/symphony_control/execution/state_machine.ex`.

**Тест:** `elixir/test/symphony_control/commands_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Два клиента с одним key и разными payload; crash после commit до response; delayed confirmation.

**Обязательный проверяемый результат:**
1. Повтор возвращает исходный outcome; key conflict отвергается.
2. Accepted не отображается Applied до runtime evidence.
3. Состояния не теряются при restart; запрещённые переходы закрыты.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/commands_test.exs
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

**Требования-owners:** CMD-01, CMD-02, CMD-03, STATE-01, STATE-02, STATE-03, STATE-04, STATE-05, STATE-06, STATE-07.

**Приёмка:** AC-04, AC-11, AC-15, AC-48.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-015 — Один scheduler, leases, epochs и admission

**Эпик:** E03 Execution. **Зависимости:** SN-010, SN-014. **Статус:** planned, admission выключен.

Развить выбранный Symphony scheduler: атомарный claim, fencing epoch, очередь отдельных проектов, admission snapshots и durable pause.

**Создать/изменить:** `elixir/lib/symphony_control/scheduler.ex`; `elixir/lib/symphony_control/execution/leases.ex`; `elixir/lib/symphony_control/admission.ex`.

**Тест:** `elixir/test/symphony_control/scheduler_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Два control одновременно; lease истекает при partition; blocker changes и revoke race; pause intake во время run.

**Обязательный проверяемый результат:**
1. Одна задача имеет одного writer; истечение lease не доказывает смерть старого worker.
2. Stale epoch не публикует side effects через broker.
3. Pause intake переживает restart и не останавливает текущий run.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/scheduler_test.exs
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

**Требования-owners:** ADM-01, ADM-02, ADM-03, ADM-04, ADM-05, SCH-01, SCH-02, SCH-03, SCH-04, SCH-05.

**Приёмка:** AC-05, AC-06, AC-37, AC-48.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-016 — Runner protocol и изоляция процессов проектов

**Эпик:** E03 Execution. **Зависимости:** SN-014, SN-015. **Статус:** planned, admission выключен.

Изолированный runner-контейнер на проект, версионированный auth transport, bounded process lifecycle, регистрация session/epoch, без второго планировщика.

**Создать/изменить:** `elixir/lib/symphony_control/runner_protocol.ex`; `runner/src/server.ts`; `deploy/runner.compose.yaml`.

**Тест:** `runner/test/protocol.test.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Runner A/B с separate HOME/volumes/network; forged runner token; partial connect; frozen worker.

**Обязательный проверяемый результат:**
1. Подмена project/epoch отбрасывается; остановка адресует свою process group.
2. Нет host Docker socket, root capability или shared writable dirs.
3. Protocol mismatch даёт explicit refusal, не silent fallback.

**Команды после реализации:**
```sh
cd runner && npm test -- protocol
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

**Требования-owners:** ENG-02, ENG-06, PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06, PROTO-07, PROTO-08, PROTO-09, PROTO-10.

**Приёмка:** AC-07, AC-24, AC-31, AC-58.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-017 — Codex App Server adapter

**Эпик:** E04 Engines. **Зависимости:** SN-016. **Статус:** planned, admission выключен.

Реализовать полный adapter Codex на pinned protocol: start/events/input/approval/interrupt/recovery/usage, точная model identity насколько signal доступен.

**Создать/изменить:** `runner/src/adapters/codex.ts`; `schemas/agent-event.schema.json`; `test/fixtures/protocol/codex`.

**Тест:** `runner/test/codex.test.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Протокольные fixtures exact CLI и одна реальная sandbox задача; question/deny/interrupt; killed app-server.

**Обязательный проверяемый результат:**
1. Events нормализованы с provenance и raw-reference; unsupported explicitly.
2. Реальный model turn не подменяется replay fixtures.
3. Codex sidecars и approval granular совместимы; auth не читается из старого HOME.

**Команды после реализации:**
```sh
cd runner && npm test -- codex
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

**Требования-owners:** Верификация требований зависимых задач; общие INV обязательны.

**Приёмка:** AC-08, AC-09, AC-12, AC-50, AC-51, AC-94.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-018 — Второй независимый агент через локальный SDK

**Эпик:** E04 Engines. **Зависимости:** SN-016, SN-017. **Статус:** planned, admission выключен.

Реализовать Claude Code/Agent SDK adapter с тем же contract, собственной авторизацией и учётом hidden subagent/tool permissions. При account incompatibility — stop до выбора поддержанного профиля.

**Создать/изменить:** `runner/src/adapters/claude.ts`; `test/fixtures/protocol/claude`; `docs/agents/compatibility.md`.

**Тест:** `runner/test/claude.test.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Реальные отдельные sandbox задачи двух движков и нормализованные contractfixtures.

**Обязательный проверяемый результат:**
1. Две разные engine implementations подтверждены actual calls, не две модели Codex.
2. Permissions и subagent usage не обходят policy.
3. Режимы stop/input/usage, которые SDK не гарантирует, обозначены unsupported.

**Команды после реализации:**
```sh
cd runner && npm test -- claude
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

**Требования-owners:** ENG-07.

**Приёмка:** AC-49, AC-50, AC-58.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-019 — Каталог capabilities и безопасные обновления adapters

**Эпик:** E04 Engines. **Зависимости:** SN-017, SN-018. **Статус:** planned, admission выключен.

Версионировать model/engine profiles, native capability evidence, allowed data regions/auth types, canary upgrades и точность resolved identity.

**Создать/изменить:** `elixir/lib/symphony_control/engines/catalog.ex`; `elixir/lib/symphony_control/engines/capabilities.ex`; `schemas/profile.schema.json`.

**Тест:** `elixir/test/symphony_control/catalog_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Новая версия без resume/price signal; moving model alias; invalid upstream enum.

**Обязательный проверяемый результат:**
1. Unsupported профиль исключён из нужной операции/strict auto.
2. Активная attempt pinned к старой версии; upgrade не меняет её.
3. Регрессия canary закрывает новые admissions и сохраняет predecessor.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/catalog_test.exs
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

**Требования-owners:** ENG-01, ENG-03, ENG-04, ENG-10.

**Приёмка:** AC-50, AC-51, AC-59.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-020 — Вопросы агенту, scoped approvals и deadline

**Эпик:** E03 Execution. **Зависимости:** SN-005, SN-014, SN-017. **Статус:** planned, admission выключен.

Реализовать request lifecycle с exact attempt/session/request, payload hash/TTL/role. Изменённый запрос требует нового решения.

**Создать/изменить:** `elixir/lib/symphony_control/requests.ex`; `elixir/lib/symphony_control/approvals.ex`; `elixir/lib/symphony_control_web/live/request_live.ex`.

**Тест:** `elixir/test/symphony_control/requests_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Replay approval после reconnect/restart/newattempt; stale actionhash; разрешённый и запрещённый native запрос.

**Обязательный проверяемый результат:**
1. Операторский ответ связан с живым запросом; старые решения не переносятся.
2. Нельзя разрешить то, что policy запрещает; reject не обходит sandbox.
3. UI показывает pending/applied/expired без ложного успеха.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/requests_test.exs
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

**Требования-owners:** Верификация требований зависимых задач; общие INV обязательны.

**Приёмка:** AC-08, AC-09, AC-10, AC-65.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-021 — Reconciliation после сбоев и остановка intake

**Эпик:** E03 Execution. **Зависимости:** SN-015, SN-016, SN-020. **Статус:** planned, admission выключен.

Сверять durable attempts с живыми runners и известными external operations до нового dispatch; обеспечить явные recovery states и restart-safe stop.

**Создать/изменить:** `elixir/lib/symphony_control/recovery.ex`; `elixir/lib/symphony_control/execution/reconciler.ex`; `elixir/lib/symphony_control/execution/stop.ex`.

**Тест:** `elixir/test/symphony_control/recovery_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Crashcontrol, crashSDK, unknown worker, stale heartbeat, две competingrestore instance.

**Обязательный проверяемый результат:**
1. UNKNOWN owner означает hold, не запуск замены.
2. Pending approvals инвалидируются когда исходный RPC потерян.
3. После stop новые modelcalls не начинаются; stop scope подтверждён.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/recovery_test.exs
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

**Требования-owners:** REL-01, REL-02, REL-03, REL-04, REL-05, REL-06, REL-07, REL-08.

**Приёмка:** AC-11, AC-12, AC-19, AC-74, AC-91.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-022 — Диагностический пакет и безопасная классификация ошибок

**Эпик:** E05 Reliability. **Зависимости:** SN-012, SN-014, SN-016. **Статус:** planned, admission выключен.

Собирать bounded structured evidence по попытке: stage, code, reasonclass, versions, logrefs, hypotheses, reproduction, next action; redact до передачи внешнему провайдеру/UI.

**Создать/изменить:** `elixir/lib/symphony_control/diagnostics.ex`; `runner/src/diagnostics.ts`; `schemas/diagnostic-bundle.schema.json`.

**Тест:** `elixir/test/symphony_control/diagnostics_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Canary secrets в HTTP headers, errors, nested JSON, logs; network/auth/schema/tool errors; oversized log flood.

**Обязательный проверяемый результат:**
1. Пакет пригоден для воспроизведения, но секреты/receipt не утекли.
2. UNKNOWN не превращается в убедительный rootcause; owner и nextsignal явны.
3. Сбой delivery не предотвращает localstop.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/diagnostics_test.exs
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

**Требования-owners:** DIAG-01, DIAG-02, DIAG-03, DIAG-09.

**Приёмка:** AC-14, AC-16, AC-88, AC-92.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-023 — Конечные retries, backoff и unknown writes

**Эпик:** E05 Reliability. **Зависимости:** SN-021, SN-022. **Статус:** planned, admission выключен.

Реализовать deterministic retries не через model thinking: три safe read attempts с10/60s,429 Retry-After/deadline, no authretry, reconciliation ambiguouswrites.

**Создать/изменить:** `elixir/lib/symphony_control/retries.ex`; `elixir/lib/symphony_control/external_operations.ex`; `test/fixtures/fault_server.ex`.

**Тест:** `elixir/test/symphony_control/retries_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Локальный HTTP server с последовательностями timeout/200,401,403,429 и create-committed-response-lost; fake clock плюс ограниченный тест в реальном времени.

**Обязательный проверяемый результат:**
1. Всего 3 попытки, не три дополнительных повтора; counters persist acrossrestart.
2. Новый expensive profile не исправляет auth/tooloutage.
3. Unknown write не повторяется пока outcome не установлен.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/retries_test.exs
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

**Требования-owners:** DIAG-04, DIAG-05, DIAG-06.

**Приёмка:** AC-13, AC-14, AC-55, AC-87, AC-88, AC-89, AC-91.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-024 — Local watchdog и stop при partition

**Эпик:** E05 Reliability. **Зависимости:** SN-016, SN-021, SN-023. **Статус:** planned, admission выключен.

Runner прекращает собственную процессную группу при утрате lease/контроля, deadline/quota; stop не зависит от model, outbound Internet или push.

**Создать/изменить:** `runner/src/watchdog.ts`; `runner/src/process_group.ts`; `test/fixtures/partition_scenario.sh`.

**Тест:** `runner/test/watchdog.test.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Реальная child process tree; blocked outbound, frozencontrol, DBdown, diskfull, notifydown; PIDreuse scenario.

**Обязательный проверяемый результат:**
1. Останавливается только зарегистрированная группа; PIDtoken защищает чужой процесс.
2. No new modelturn after stop, deferred event доставляется после recovery.
3. Неудача уведомления не порождает busyloop.

**Команды после реализации:**
```sh
cd runner && npm test -- watchdog
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

**Требования-owners:** DIAG-07, DIAG-08.

**Приёмка:** AC-07, AC-15, AC-90, AC-91, AC-92.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-025 — Usage ledger и атомарные бюджетные резервы

**Эпик:** E06 Routing. **Зависимости:** SN-014, SN-019. **Статус:** planned, admission выключен.

Считать usage/estimate/reserve/invoice отдельно. Лимиты task/project/provider/global сохраняются при retry/handoff/review.

**Создать/изменить:** `elixir/lib/symphony_control/budgets.ex`; `elixir/lib/symphony_control/usage.ex`; `elixir/lib/symphony_control/budgets/reservation.ex`.

**Тест:** `elixir/test/symphony_control/budgets_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Duplicate cumulative usage, latecharges, sharedprovider two projects simultaneous reserve, missingprice, countcache tokens.

**Обязательный проверяемый результат:**
1. Расход не удваивается и не сбрасывается; unknown не ноль.
2. Hardcap доступен только когда enforced by capability; inflightbound виден.
3. Одновременные reserve не выходят за policyallowance.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/budgets_test.exs
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

**Требования-owners:** BUD-01, BUD-02, BUD-03, BUD-04, BUD-05, BUD-06, BUD-07.

**Приёмка:** AC-29, AC-60, AC-61, AC-62.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-026 — Routing manual/recommend/auto и risk floor

**Эпик:** E06 Routing. **Зависимости:** SN-019, SN-025, SN-022. **Статус:** planned, admission выключен.

Детерминированный versioned router с explanation: фильтрация policy/data/capabilities перед стоимостью; plan/implement/review могут иметь разные профили.

**Создать/изменить:** `elixir/lib/symphony_control/routing.ex`; `elixir/lib/symphony_control/routing/risk.ex`; `policies/routing-default.json`.

**Тест:** `elixir/test/symphony_control/routing_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Однострочный authchange, unknownscope, formatter, forbiddenprovider, aliasmodel, provideroutage.

**Обязательный проверяемый результат:**
1. Одинаковый snapshot даёт тот же route; exclusions объяснимы.
2. Manual не переключается сам; Recommend не запускает.
3. Детерминированный formatter не вызывает модель; Economy не ослабляет права.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/routing_test.exs
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

**Требования-owners:** ENG-05, ROUT-01, ROUT-02, ROUT-03, ROUT-04, ROUT-05, ROUT-06, ROUT-07, ROUT-08, ROUT-09.

**Приёмка:** AC-51, AC-52, AC-53, AC-54, AC-55, AC-56, AC-72.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-027 — Память проекта, context manifest и allowlisted skills

**Эпик:** E06 Routing. **Зависимости:** SN-008, SN-009, SN-019. **Статус:** planned, admission выключен.

Формировать task context с sourceversions/verified vs hypothesis, ACL до retrieval и отдельным pinned skills registry без копирования старой Codex config.

**Создать/изменить:** `elixir/lib/symphony_control/context.ex`; `elixir/lib/symphony_control/skills.ex`; `schemas/context-manifest.schema.json`.

**Тест:** `elixir/test/symphony_control/context_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Чужой secret в retrieval, conflictingspec, untrusted skill prompt/shell, hashchanged skill, oldglobal plugin.

**Обязательный проверяемый результат:**
1. Sourceprovenance сохранён; чужие данные не попадают даже в summary.
2. Skill не расширяет tools/permissions и не выполняет installationhooks автоматически.
3. Доказанные installedskills импортируются только после отдельного read/audit/hashpin.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/context_test.exs
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

**Требования-owners:** CTX-01, CTX-02, CTX-03, CTX-04.

**Приёмка:** AC-16, AC-71, AC-94.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-028 — Проверяемая передача между агентами

**Эпик:** E06 Routing. **Зависимости:** SN-021, SN-025, SN-027. **Статус:** planned, admission выключен.

Передавать workpackage с exactSHA/dirtypatch/tests/questions/knownoperations между engines, прекращая старого writer и делая новую attempt.

**Создать/изменить:** `elixir/lib/symphony_control/handoff.ex`; `runner/src/handoff.ts`; `schemas/handoff.schema.json`.

**Тест:** `elixir/test/symphony_control/handoff_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Dirty worktree, untracked artifact, Gitwriteunknown, sessionexpired, providerdata deny.

**Обязательный проверяемый результат:**
1. Работа не теряется; один writer; inheritedapprovals/secrets отсутствуют.
2. Недоступное native resume не выдается за resume.
3. Budget/provenance продолжаются через handoff.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/handoff_test.exs
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

**Требования-owners:** ENG-08, ENG-09.

**Приёмка:** AC-57, AC-58, AC-74.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-029 — Spec → planner → проверяемый DAG задач

**Эпик:** E07 Autonomy. **Зависимости:** SN-010, SN-014, SN-026, SN-027. **Статус:** planned, admission выключен.

Планировщик принимает accepted spec, строит эпики и leaf tasks с проверками, dependencies, budgets и milestones. Детерминированный validator/admission независимо проверяет план.

**Создать/изменить:** `elixir/lib/symphony_control/plans.ex`; `elixir/lib/symphony_control/plans/validator.ex`; `elixir/lib/symphony_control/plans/admission.ex`.

**Тест:** `elixir/test/symphony_control/plans_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Leaf без fixture; hallucinatedrequirement; cyclicplan; изменения accepted version; auto-generateddefect loop.

**Обязательный проверяемый результат:**
1. Все requirements имеют owners/evidence; invalidplan не запускается.
2. Подзадачи не самозапускаются, но допустимые leaf проходят без ручного continue в пределах делегации.
3. Максимум вопросов на входе; последующие stopquestions конкретны и имеют диагностический пакет.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/plans_test.exs
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

**Требования-owners:** FLOW-01, FLOW-02, FLOW-03, FLOW-04, PLAN-01, PLAN-02, PLAN-03, PLAN-04, PLAN-05, PLAN-09, TSK-18, WF-01, WF-02, WF-03.

**Приёмка:** AC-38, AC-39, AC-40, AC-72, AC-78, AC-79, AC-80, AC-21.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-030 — Независимый review и защищённая приёмка

**Эпик:** E07 Autonomy. **Зависимости:** SN-003, SN-017, SN-029. **Статус:** planned, admission выключен.

Разделить implementer/read-only reviewer/trustedverifier. Защитить lockedacceptance suite и статус checks от writer; stage evidence exactHEAD.

**Создать/изменить:** `elixir/lib/symphony_control/quality.ex`; `ci/acceptance-policy.json`; `ci/review-verifier.sh`; `schemas/evidence.schema.json`.

**Тест:** `elixir/test/symphony_control/quality_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Writer удаляет test, подписываетсвой status, меняет HEAD после review; UIartifact содержит private data.

**Обязательный проверяемый результат:**
1. Изменённый HEAD аннулирует review/check.
2. Ослабление tests не засчитывает pass; контрольные test fixtures независимы.
3. Accepted task имеет actual evidence, не сообщение модели.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/quality_test.exs
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

**Требования-owners:** PLAN-07, QUAL-01, QUAL-02, QUAL-03, QUAL-04.

**Приёмка:** AC-69, AC-70, AC-84, AC-96.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-031 — Authenticated MCP для ChatGPT и API parity

**Эпик:** E07 Autonomy. **Зависимости:** SN-005, SN-014, SN-029. **Статус:** planned, admission выключен.

Expose typed own MCP через OAuth к тому же domain service, что UI: createproject/spec/plan/tasks/run/ops. Реальная запись с idempotency и expectedversion; granular scope и delegation.

**Создать/изменить:** `elixir/lib/symphony_control/mcp.ex`; `elixir/lib/symphony_control/mcp/authorization.ex`; `schemas/mcp-tools.json`.

**Тест:** `elixir/test/symphony_control/mcp_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Поддерживаемый ChatGPT-клиент реальный request; text/voice capability separately; forgeactorid, tokenaudience, replayprepare.

**Обязательный проверяемый результат:**
1. ChatGPT ставит один проект/задачу через реальный tool; не требует Linear.
2. OAuth token не передаётся в modelcontext; actor основан на auth.
3. Неподдерживаемый голосовой tool режим явно объявлен; обычный UI/текст остаётся рабочим.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/mcp_test.exs
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

**Требования-owners:** API-01, API-02, API-03, API-04, API-05, API-06, API-07, API-08, INT-01, INT-02, INT-03, INT-04, INT-05, INT-06, INT-07, INT-08, INT-09, MCP-01, MCP-02, MCP-03, MCP-04, MCP-05, MCP-06.

**Приёмка:** AC-77, AC-78, AC-83.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-032 — Typed provisioning GitHub/Coolify/Authentik

**Эпик:** E08 Release. **Зависимости:** SN-006, SN-014, SN-031. **Статус:** planned, admission выключен.

Ограниченный resource broker создаёт private repo и выделенные Coolify app/runner/DB и OIDCclient по reviewed manifest и квоте; работает с существующими платформами.

**Создать/изменить:** `elixir/lib/symphony_control/provisioning.ex`; `elixir/lib/symphony_control/provisioning/manifest.ex`; `schemas/provisioning-plan.schema.json`.

**Тест:** `elixir/test/symphony_control/provisioning_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** T естовые providercontracts плюс реальные sandboxresources; HTTPtimeout после create; чужой target; compensation при partial.

**Обязательный проверяемый результат:**
1. Повтор продолжает saga без duplicate resources; ownership доказан.
2. Agent не получает root/Docker/socket/broadtokens.
3. Изменение shared Authentik flows/DFtarget требует выхода из scope и блокируется.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/provisioning_test.exs
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

**Требования-owners:** PROV-01, PROV-02, PROV-03, PROV-04.

**Приёмка:** AC-28, AC-31, AC-81, AC-83.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-033 — Автоматический release через штатный webhook

**Эпик:** E08 Release. **Зависимости:** SN-030, SN-032. **Статус:** planned, admission выключен.

Связать exact PR checks/review с делегированным merge, observe штатный GitHub push→Coolify webhook; serialize releases, pin desiredobservedrevision.

**Создать/изменить:** `elixir/lib/symphony_control/releases.ex`; `elixir/lib/symphony_control/releases/gates.ex`; `deploy/control.compose.yaml`.

**Тест:** `elixir/test/symphony_control/releases_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Два PR, устаревший check, mergeambiguous, webhookoutoforder, failedbuild, отсутствие CI.

**Обязательный проверяемый результат:**
1. Обычный scoped deploy не просит повторного humanapproval.
2. Открытие PR не считается productiondeploy; releasebranchpush после merge запускает штатный путь.
3. Ни directproductionpush, ни manualdeploy наудачу не обходят gate.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/releases_test.exs
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

**Требования-owners:** AUTO-01, AUTO-02, AUTO-03, AUTO-04, DEP-01, DEP-02, DEP-03, DEP-04.

**Приёмка:** AC-17, AC-26, AC-82, AC-84, AC-96.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-034 — Runtime acceptance и безопасный автоматический rollback

**Эпик:** E08 Release. **Зависимости:** SN-021, SN-033. **Статус:** planned, admission выключен.

Проверить exactimage/commit/config, TLS/routes/health и функциональный сценарий после release. Вернуть совместимый predecessor либо явный recoveryhold.

**Создать/изменить:** `elixir/lib/symphony_control/releases/readback.ex`; `elixir/lib/symphony_control/releases/rollback.ex`; `deploy/acceptance.sh`.

**Тест:** `elixir/test/symphony_control/readback_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Живой sandboxcontrol good→faultedrelease; backwardcompatiblemigration и destructivefixture; concurrentuserwrite.

**Обязательный проверяемый результат:**
1. Running/finished не равно acceptance; функциональные операции реально выполняются на testdata.
2. Rollback подтверждён по revision и функции, без потери новыхданных.
3. Несовместимаясхема блокирует автоматический restore; никакого фиктивногоуспеха.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/readback_test.exs
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

**Требования-owners:** DEP-05, DEP-06, DEP-07.

**Приёмка:** AC-17, AC-19, AC-20, AC-85, AC-86, AC-89.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-035 — Mobile-first интерфейс полного трекера и запусков

**Эпик:** E09 Mobile. **Зависимости:** SN-011, SN-012, SN-020, SN-026. **Статус:** planned, admission выключен.

PWA на общей Phoenix панели: projects/list/board/tasks/comments/specs, запуск/профиль/budget, inbox и drilldownevidence; UI пригоден также для desktop.

**Создать/изменить:** `elixir/lib/symphony_control_web/live/project_live.ex`; `elixir/lib/symphony_control_web/live/task_live.ex`; `assets/pwa/manifest.webmanifest`.

**Тест:** `test/e2e/mobile.spec.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** 360/390/430px, keyboardopen, longRussiantext, screenreaderfocus, networkslow; fullCRUD + run workflow.

**Обязательный проверяемый результат:**
1. Полный обычныйоператорскийцикл без SSH.
2. Верстка не скрывает критический target/risk; tasktracker не заменён terminaldashboard.
3. CoreUIassets хранятся локально.

**Команды после реализации:**
```sh
npx playwright test test/e2e/mobile.spec.ts
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

**Требования-owners:** MOB-10, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06.

**Приёмка:** AC-35, AC-42, AC-64, AC-73.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-036 — Мобильные approvals, reconnect и потерянное устройство

**Эпик:** E09 Mobile. **Зависимости:** SN-035, SN-005. **Статус:** planned, admission выключен.

Надёжные mobilecommands, explicit UNKNOWN, step-upauth для risk, безопаснаяполитика serviceworker/privatecache/device revoke.

**Создать/изменить:** `elixir/lib/symphony_control_web/live/decision_live.ex`; `assets/js/command_client.ts`; `assets/pwa/service_worker.js`.

**Тест:** `test/e2e/mobile-commands.spec.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Смена Wi-Fi/mobile, doubletap, offlineapproval, taboldsession, lostphone revoke.

**Обязательный проверяемый результат:**
1. Offline опасныеответы не отправляются позже скрыто.
2. Повтор возвращает исходную operation, targethash/expiry перепроверены server-side.
3. Revokeddevice теряет privatechannel и pushsubscription.

**Команды после реализации:**
```sh
npx playwright test test/e2e/mobile-commands.spec.ts
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

**Требования-owners:** MOB-01, MOB-02, MOB-03, MOB-04, MOB-05, MOB-06, MOB-09.

**Приёмка:** AC-65, AC-66, AC-68.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-037 — Проверяемые уведомления на телефон

**Эпик:** E09 Mobile. **Зависимости:** SN-012, SN-036. **Статус:** planned, admission выключен.

Опциональный WebPush/согласованныйканал: минимальный payload, authdeeplink, delivery/send/open/ack разделены, preference/revoke.

**Создать/изменить:** `elixir/lib/symphony_control/notifications/web_push.ex`; `elixir/lib/symphony_control/devices.ex`; `docs/mobile/device-acceptance.md`.

**Тест:** `docs/mobile/device-acceptance.md`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Согласованные реальные iOS/Android устройства; lockscreen; expiredsubscription; IdPsessionexpired.

**Обязательный проверяемый результат:**
1. Уведомлениеобоплате/ошибке не содержитсекретов/кода.
2. Реальная доставка проверена отдельно от сохранения outbox.
3. Внешняя Apple/Google доставка отмеченакак externaldependency.

**Команды после реализации:**
```sh
npx playwright test test/e2e/notifications.spec.ts
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

**Требования-owners:** MOB-07, MOB-08.

**Приёмка:** AC-18, AC-67, AC-68.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-038 — Два параллельных проекта, квоты и независимые обновления

**Эпик:** E10 Integration. **Зависимости:** SN-018, SN-025, SN-033. **Статус:** planned, admission выключен.

Провести projectconcurrencyverification: отдельно runtimeenforced CPU/memory/PIDs/storage/egress, fairness и liveoverlap; третья project конфигурациябез codechange.

**Создать/изменить:** `test/symphony_control/multi_project_test.exs`; `test/e2e/multi-project.spec.ts`; `deploy/project-limits.json`.

**Тест:** `test/e2e/multi-project.spec.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Проекты A/B на разных runners, A waiting/crash/deploy, Bcontinues, Cregistration, sharedproviderbudget.

**Обязательный проверяемый результат:**
1. Перекрывающиеся live modelturns A/B доказаны UTC/runneridentity.
2. Обновление A не перезапускает B; scope провереннауровне UI/API/tools/network.
3. Изоляцияконтейнеровне называетсяустойчивостьюкобщему hostfailure.

**Команды после реализации:**
```sh
npx playwright test test/e2e/multi-project.spec.ts
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

**Требования-owners:** Верификация требований зависимых задач; общие INV обязательны.

**Приёмка:** AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-49.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-039 — Резервное копирование и полное восстановление

**Эпик:** E10 Integration. **Зависимости:** SN-013, SN-021, SN-025. **Статус:** planned, admission выключен.

BackupDB+attachments+configmanifests в независимую failure domain; restore в изолированном контуре с закрытым admission и проверкой внешнихэффектов.

**Создать/изменить:** `ops/backup.sh`; `ops/restore-verify.sh`; `elixir/lib/symphony_control/recovery/restore.ex`.

**Тест:** `ops/restore-verify.sh`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Удалённая testDB, missingattachment/hashmismatch, revokedroles, lastbudgetreservation; два project exports.

**Обязательный проверяемый результат:**
1. Восстановлены IDs/revisions/comments/docs/bytes/policy/profiles/budgets.
2. Старые approvals и access не оживают, oldattempt не dispatch-ится.
3. Restore реально выполнен, не проверен только архив listing.

**Команды после реализации:**
```sh
bash ops/restore-verify.sh
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

**Требования-owners:** OPS-01, OPS-02, OPS-03, OPS-04, OPS-05, OPS-06, OPS-07, OPS-08, OPS-09, OPS-10, OPS-11, OPS-12.

**Приёмка:** AC-20, AC-32, AC-44, AC-74.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-040 — Оценка маршрутизатора и экономика результата

**Эпик:** E10 Integration. **Зависимости:** SN-026, SN-030. **Статус:** planned, admission выключен.

Зафиксировать корпус своих задач/holdout, baselinebalanced, shadowrecommend и сравнение acceptancecost с failures/retries/review.

**Создать/изменить:** `elixir/lib/symphony_control/evaluation.ex`; `eval/dataset.json`; `eval/run_comparison.exs`.

**Тест:** `eval/run_comparison.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Однакогорта с successes/failures/zeroaccepted, missinginvoice, routepolicychange; shadow no sideeffects.

**Обязательный проверяемый результат:**
1. Метрика расходы всейкогорты/accepted, zeroaccepted undefined.
2. Нет выдуманных confidence/economy; малый sample явноограничен.
3. Новая policy включаетсяпосле canary, не самолично по словамагента.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix run ../eval/run_comparison.exs
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

**Требования-owners:** EVAL-01, EVAL-02, EVAL-03, EVAL-04.

**Приёмка:** AC-63, AC-75.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-041 — Наблюдаемость, SLO и эксплуатационные runbooks

**Эпик:** E10 Integration. **Зависимости:** SN-022, SN-024, SN-039. **Статус:** planned, admission выключен.

Проектные metrics/structuredlogs, liveness/readiness, requesttimings, leases/queues/blockedcost, retention and runbooks; ограниченияресурсовпод нагрузкой.

**Создать/изменить:** `elixir/lib/symphony_control/observability.ex`; `ops/alerts.yml`; `ops/runbooks.md`; `test/load/tracker.js`.

**Тест:** `elixir/test/symphony_control/observability_test.exs`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** TenKissues synthetic corpus, Nprojects, logflood, storagequota, provideroutage, blockedworker.

**Обязательный проверяемый результат:**
1. SLO из spec измеренынагрузкой; отсутствующая метрика не замененаэвристикой.
2. Алерты не получают секретные данные; retention не удаляет acceptancehistory.
3. Health наблюдаетсянезависимоот modeloutput.

**Команды после реализации:**
```sh
cd elixir && MIX_ENV=test mix test test/symphony_control/observability_test.exs
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

**Требования-owners:** NFR-01, NFR-02, NFR-03, NFR-04, NFR-05, NFR-06, NFR-07, NFR-08, NFR-09, NFR-10, NFR-11, NFR-12, NFR-13, NFR-14, NFR-15, OBS-01, OBS-02, OBS-03, OBS-04, OBS-05, TSK-17.

**Приёмка:** AC-14, AC-15, AC-19, AC-45, AC-92.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-042 — Сквозной автономный milestone до рабочего сервиса

**Эпик:** E10 Integration. **Зависимости:** SN-029, SN-031, SN-034, SN-035, SN-038. **Статус:** planned, admission выключен.

Пройти идею→accepted ТЗ→DAG→leafregressions→интеграции→review→webhookdeploy→функциональнаяприёмка на двух безопасных демонстрационных проектах: HTTPservice и MCPserver.

**Создать/изменить:** `test/e2e/autonomous-milestone.spec.ts`; `test/fixtures/sample-http`; `test/fixtures/sample-mcp`; `docs/acceptance/milestone.md`.

**Тест:** `test/e2e/autonomous-milestone.spec.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Real disposable HTTPservice withseeddata + MCP tool list/call; owner только initialscope и finalacceptance, один контролируемый вопрос агента.

**Обязательный проверяемый результат:**
1. Обычные принятые этапы проходят без ручной команды продолжения.
2. Результат HTTP и MCP реальнодоступенчереззащищённыйконтур; not just codegenerated.
3. Любойискусственнопроваленный gate останавливает release, ане объявляет done.

**Команды после реализации:**
```sh
npx playwright test test/e2e/autonomous-milestone.spec.ts
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

**Требования-owners:** PLAN-06, PLAN-08.

**Приёмка:** AC-17, AC-34, AC-39, AC-54, AC-72, AC-73, AC-77, AC-80, AC-82, AC-96.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-043 — Переход с bootstrap на собственный трекер

**Эпик:** E10 Integration. **Зависимости:** SN-013, SN-039, SN-042. **Статус:** planned, admission выключен.

Остановить admissionbootstrap, drain единственный writer, importbacklogexactmapping/nativeIDs, сверить branches/PR/effects, включитьтолько один новый владелец исполнения.

**Создать/изменить:** `ops/cutover.sh`; `schemas/cutover-manifest.schema.json`; `docs/acceptance/cutover.md`.

**Тест:** `test/e2e/cutover.spec.ts`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Незавершённая issue/PR, waitingapproval, duplicateimport, restartoldbootstrap attempt.

**Обязательный проверяемый результат:**
1. Неоднозначное состояние worker блокирует переключение.
2. Старые labels непринимаются, nativeIDscanonical; два scheduler не берутоднузадачу.
3. Остановленный bootstrap и документы отката сохраняются.

**Команды после реализации:**
```sh
npx playwright test test/e2e/cutover.spec.ts
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

**Требования-owners:** BOOT-07.

**Приёмка:** AC-43, AC-93, AC-95.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.

## SN-044 — Финальный fault-injection soak и acceptance dossier

**Эпик:** E10 Integration. **Зависимости:** SN-036, SN-037, SN-038, SN-039, SN-040, SN-041, SN-042, SN-043. **Статус:** planned, admission выключен.

Выполнить24hboundedsoak с двумя движками/проектами, controlledfaults, budgetcaps, restart/recovery. Сверитьвсе AC01–96, приложить owneracceptance иограничения.

**Создать/изменить:** `test/soak/run.sh`; `docs/acceptance/final.md`; `docs/acceptance/evidence-index.json`.

**Тест:** `test/soak/run.sh`. Пути — контракт будущей реализации, не утверждение об уже существующих файлах.

**Fixture и воспроизведение:** Контролируемые partition/authfail/diskfull/DBdown/expiredapproval/releasefailure; boundedpaidbudgetmanifest.

**Обязательный проверяемый результат:**
1. Нет duplicatewriter/secretleak/scopeescalation/unexplainedcharges.
2. Каждый AC имеет actualresult и evidence либо explicitFAIL/BLOCKED; untested не PASS.
3. Все knownissues зарегистрированы; acceptedruntimeexact; rollback сохранён.

**Команды после реализации:**
```sh
bash test/soak/run.sh
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

**Требования-owners:** DIAG-10.

**Приёмка:** AC-76, AC-86, AC-87, AC-88, AC-89, AC-90, AC-91, AC-92, AC-96.

**Evidence:** base/head/tree SHA; workflow/policy/profile versions; test command + UTC start/end + exit code + protected artifact hashes; scope diff + independent exact-HEAD review; runtime/config identity + functional readback when release applies.

**Стопы:** required access/fixture/verification signal missing; unknown external mutation outcome cannot be reconciled; scope or privilege expansion; finite retry/deadline/budget exhausted.

**Rollback:** Preserve evidence and worktree. Before merge: abandon attempt without reverting unrelated work. After release: only verified compatible predecessor; incompatible data/schema enters recovery hold.

**Лимиты:** один writer; два repair cycles и одна смена profile; safe network максимум три попытки с 10/60 сек; платное исполнение только с effective project budget.

**За рамками:** Do not change existing DF Assistant or its Symphony/config/credentials. Do not replace the chosen Symphony scheduler or silently add another scheduler. Do not enable GitHub Actions, expand privileges or fabricate PASS for unrun checks.
