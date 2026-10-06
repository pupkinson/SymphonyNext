# Symphony Next: автономность внутри договора

Дата: 2026-10-06. Версия дополнения: AUT/v1. Владелец: Денис.
Статус: принцип и подготовка контрактов согласованы; письменный design candidate. Implementation, product acceptance и runtime activation этим изменением не выполняются.
Основание и границы документального этапа: GitHub issue #81, AUTONOMY-CONTRACTS-SPEC-20261006.
Исходный main: `2bf21950e0725bc9228b262e1495f5af5eeea1d6`, tree `f228f3a5743317138de89a849cbbe13dee092835`.

## 1. Решение и результат

«Автономность внутри договора, человек — на согласованных решениях и реальном расширении границ».

После согласования цели, доступных ресурсов, делегации, бюджета и контрольных точек система сама декомпозирует, назначает работу, реализует, проверяет, исправляет и выпускает результат внутри этих границ. Инженерная проверка остаётся обязательной, но не превращается в просьбу владельцу повторно разрешить уже согласованную работу.

Выбран contract-first вариант: machine-enforced policy + role contracts + typed transitions + skills как процедурные инструкции. Prompt-only вариант не обеспечивает одинакового исполнения разными моделями. Полный доступ всех агентов к серверу неприемлем: он смешивает разработку, авторизацию и доверенную приёмку. Эти альтернативы не вводятся.

Разделяются проектный договор (долго живёт), отдельное admission/lease (одна попытка), доказательства качества (конкретный source/context) и одноразовое решение человека (конкретный payload). Новый commit требует новых evidence, но не новой проектной делегации. Это уточняет запрет переноса старых approvals в v0.5: старое разовое разрешение не переносится; действующий проектный договор перечитывается и сужается до новой задачи.

## 2. Четыре базовых артефакта и правила загрузки

| Артефакт | SHA-256 |
| --- | --- |
| `schemas/autonomy-contract.schema.json` | `b2c1f32e391eda98ea076c47dc5a16362a6c18033132dec2c5d3dcf5dd6a6f0b` |
| `docs/autonomy/role-contracts.md` | `e0dc35737f175ab7df906dc2e091a5d808cdb8f913154ce03699e2ea314731d3` |
| `docs/autonomy/human-escalations.md` | `8d10bcca54e8d809deb5a96c0c7e946c77703da83520479b57038b3d8ade973c` |
| `docs/autonomy/agent-transitions.md` | `d58d03391d293446eaf7e68100896f3c57f272aa3c23caa514c7b19ced124bdc` |

Эти четыре источника составляют контракт дополнения, а не необязательные подсказки. Consumer проверяет exact hashes до использования. Несовпадение, отсутствие полного текста или неподдерживаемый контракт вызывает planning hold; нельзя молча пропустить часть требований. Ни сама JSON Schema, ни валидный JSON не являются полномочием или работающим authorizer.

Существующие `SPECIFICATION.md`, `TASKS.md`, backlog, traceability, `PROJECT_RULES.md`, `AGENTS.md`, `SKILLS_POLICY.md`, project policy и MCP-SN031-r2 остаются неизменными. Старый `docs/ROLE_CONTRACTS.md` сохраняется как baseline; новый файл уточняет роли целевого продукта, не меняет привилегии установленного bootstrap. Все пять новых файлов и изменение spec-index связаны корневым MANIFEST.

## 3. Семантика Autonomy Contract

Schema задаёт закрытый формат v1: identity/revision проекта и договора; hash-bound цель, policy, resource/skill manifests и authority record; статус/срок; allow/deny grants на точные capability/resource IDs; role bindings; бюджеты/профили/квоты; milestones; recovery policy. Секреты, shell-команды и произвольные URL для выдачи прав в договоре не хранятся. Ссылки разрешает доверенный registry, не сетевой fetch по подсказке модели.

Обязательная semantic validation сверх JSON Schema:

1. Authority record создан аутентифицированным субъектом с текущим правом делегировать именно эти действия; его hash, project binding и revision проверены. Поле status=active от клиента не активирует договор. Неактивный/отозванный/истёкший договор не допускает side effects.
2. Все pin IDs/revisions/hashes существуют и совпадают; resource и principal IDs принадлежат разрешённому scope. Capability descriptor и constraints — зарегистрированные типизированные контракты, а не неизвестный текст. Неизвестный формат/операция отклоняется, даже если структура JSON правильная.
3. Grant IDs уникальны, role binding однозначен; grant_ids ссылаются на существующие grants. Role contract не получает больше прав, чем родитель. Любой deny имеет приоритет; внешние запреты сильнее project allow. Нельзя выдать право за пределами полномочий issuer.
4. Времена парсятся с timezone; expiry строго позже not_before. Milestone termination ссылается на существующий уникальный milestone и прекращает допуск после достижения указанного gate. Истечение/достижение границы никогда не продлевает договор автоматически.
5. Budget и resource quotas не превышают действующих верхних лимитов; money хранится целыми minor units. Валюта должна поддерживаться ledger. Нет defaults на неограниченную стоимость, параллельность или циклы. Нулевая денежная сумма не разрешает платные вызовы.
6. Execution profile валиден для движка/модели/effort/speed и data policy. Состояние assigned не выдаётся за observed; неподтверждённые параметры исполнения остаются UNKNOWN. Смена профиля подчинена актуальной policy и остатку лимита, а не желанию агента.
7. Preflight проверяет фактическую доступность необходимых инструментов, сети, изолированной рабочей среды и проверок. Договор не подменяет provisioning. Недостающая capability даёт конкретный blocker, а не новый вопрос о согласии с прежней целью.
8. Signature/authority validation, clock, durable store, revocation, constraints evaluation и CAS — обязанности реализации. JSON Schema проверяет только структуру; её успешная проверка не доказывает эти свойства.

Договор сохраняется в control state, а не в чате. Новая сессия получает текущий разрешённый snapshot; новый task получает подмножество прав. При каждом side effect повторно проверяются revocation/state/bindings. Уже отправленный внешний запрос нельзя обещать мгновенно отменить; допускается только разрешённое безопасное завершение/cleanup с сохранением evidence.

## 4. Полномочия, роли и проверяемые переходы

Эффективное разрешение — пересечение ограничений платформы/организации/ресурса, проектного договора, роли и задачи. Tasks, skills, найденный текст и LLM judgement не могут изменить его. Владелец меняет собственную policy новой аутентифицированной revision; универсального обхода внешних ограничений нет.

Planner, implementer, reviewer и optional arbitrator — LLM-роли. Scheduler, policy, release и recovery controllers — детерминированные компоненты с проверяемыми predicates. Runtime verifier отделяет наблюдаемую функцию от заявления исполнителя. Arbitrator помогает разобрать спор, но не открывает gate собственным суждением.

Агент предлагает typed command; controller проверяет identity, scope, state version, lease и evidence. Атомарно фиксируются state change, следующая obligation и outbox. Внешние записи используют устойчивый intent и reconciliation; абсолютный exactly-once для произвольного API не предполагается.

Система не принимает собственное изменение authorizer или protected checks как доказательство безопасного self-update. Candidate source/test и доверенные acceptance runner/policy — разные trust domains. Будущая поддержка обычных новых commit/test/dependency должна быть автоматической в пределах договора; нынешние frozen CI profiles, receipts и HOLD не ослабляются этим документом.

## 5. Контрольные точки, неопределённость и восстановление

`report_only` публикует результат и продолжает. `human_decision` требует конкретного выбора после проверяемой демонстрации. Перечень human reasons закрыт и задан отдельным контрактом; единственный факт сомнения модели не оправдывает вопрос «продолжать?». При этом важные неизвестные требования или риск после разрешённого анализа честно эскалируются; формальный ноль вопросов не важнее корректности.

При transient сбое применяется действующая finite retry policy; при auth/policy denial нет перебора обходных инструментов/credentials. Unknown write сначала reconciles. Repair chain, расходы, cooldown, leases и история сохраняются между task/agent/restart. Создание новой подзадачи не обнуляет исчерпанные лимиты. Блокировка одной ветви не останавливает независимую работу, если нет общей угрозы/проектной границы.

## 6. Трассировка требований и владельцы реализации

Это requirements ownership, НЕ новые admitted tasks и НЕ изменение зависимостей текущего backlog.

| Требование | Содержание | Owners | Acceptance |
| --- | --- | --- | --- |
| AUT-01 | Ноль повторных подтверждений внутри договора при готовой среде | SN-020, SN-042 | AC-AUT-01, AC-AUT-02 |
| AUT-02 | Постоянный versioned договор отдельно от consent/evidence | SN-014, SN-020 | AC-AUT-03 |
| AUT-03 | Пересечение прав, deny и подлинная authority | SN-005, SN-020 | AC-AUT-04, AC-AUT-05 |
| AUT-04 | Детерминированные controller gates | SN-014, SN-033 | AC-AUT-06 |
| AUT-05 | Независимый exact-source review | SN-028, SN-030 | AC-AUT-07, AC-AUT-08 |
| AUT-06 | Typed transitions, CAS, outbox и idempotency | SN-014, SN-015 | AC-AUT-09, AC-AUT-10 |
| AUT-07 | Durable recovery/repair-chain, no blind replay | SN-021, SN-023 | AC-AUT-11, AC-AUT-12 |
| AUT-08 | Отзыв, fencing и resource drift | SN-005, SN-016, SN-020 | AC-AUT-13 |
| AUT-09 | Проверяемый human gate и честная неопределённость | SN-020, SN-022, SN-036 | AC-AUT-14, AC-AUT-15 |
| AUT-10 | Раздельные отчётные и decision milestones | SN-010, SN-029, SN-035 | AC-AUT-16 |
| AUT-11 | Role-derived pinned skills без новых прав | SN-027 | AC-AUT-17, AC-AUT-18 |
| AUT-12 | Разделение ролей, advisory arbitrator | SN-016, SN-030 | AC-AUT-19 |
| AUT-13 | Admission и атомарный бюджет поддерживаемых профилей | SN-015, SN-025, SN-026 | AC-AUT-20 |
| AUT-14 | Единая семантика UI/API/MCP и настоящий human consent | SN-031, SN-036 | AC-AUT-21 |
| AUT-15 | Additive spec composition, никаких скрытых runtime изменений | SN-029, SN-042, SN-044 | AC-AUT-22 |
| AUT-16 | Автоматические release/checks, честный runtime/rollback | SN-003, SN-030, SN-033, SN-034 | AC-AUT-23, AC-AUT-24 |

## 7. Приёмочные сценарии будущей реализации

Все AC ниже имеют статус NOT_RUN. Они не считаются пройденными от проверки схемы или наличия текста.

| AC | Проверяемый сценарий и ожидаемый результат |
| --- | --- |
| AC-AUT-01 | После одной действительной делегации обычная leaf-задача доходит до принятого результата; дополнительные человеческие approve отсутствуют |
| AC-AUT-02 | Reviewer требует исправление; repair, новый review и допустимый release выполняются без вопроса «продолжать?» |
| AC-AUT-03 | Restart/смена сессии восстанавливают действующий договор и историю; не переносят одноразовый consent на новый payload |
| AC-AUT-04 | Поддельный active contract, неизвестный grant или право сверх issuer отклоняются до side effect |
| AC-AUT-05 | Deny/внешний запрет не отменяется project allow, skill, task или решением arbitrator |
| AC-AUT-06 | Модель пишет «всё принято» без evidence; controller не открывает следующий gate |
| AC-AUT-07 | После ACCEPTED для A появляется B; старое review не принимается, новая проверка назначается автоматически |
| AC-AUT-08 | У reviewer неполный source либо обязательный тест NOT_RUN; результат BLOCKED, не PASS |
| AC-AUT-09 | Два одинаковых submit/review events создают одну obligation; одинаковый idempotency key с другим payload возвращает conflict |
| AC-AUT-10 | Падение между state change и доставкой не теряет следующую задачу; stale lease/CAS не меняет состояние |
| AC-AUT-11 | Timeout merge/deploy с неизвестным исходом ведёт к readback; без данных нет повторной mutation |
| AC-AUT-12 | Repair через новый task/model/restart сохраняет расходы/пределы цепочки; исчерпание не обнуляется |
| AC-AUT-13 | Отзыв либо drift между preflight и side effect блокирует новые действия; in-flight outcome честно reconciles |
| AC-AUT-14 | Ненужный human_request отклоняется и возвращается в разрешённый workflow; реальное расширение даёт запрос с exact delta |
| AC-AUT-15 | Существенно неоднозначная цель после ограниченного анализа даёт PRODUCT_DECISION; система не угадывает и не зацикливается |
| AC-AUT-16 | Reporting milestone продолжает работу; decision milestone останавливает согласованную область и показывает проверяемый результат |
| AC-AUT-17 | Skills с конфликтом прав/новым hook либо неизвестным hash не активируются |
| AC-AUT-18 | Внутренний procedural gate закрывается нужной ролью; внешнее обязательное личное согласие не имитируется |
| AC-AUT-19 | Автор не является своим independent reviewer; advisory arbitrator не публикует trusted acceptance |
| AC-AUT-20 | Параллельные reservations не перерасходуют допуск; неподдерживаемый профиль отклонён, observed параметры не выдуманы |
| AC-AUT-21 | UI/API/MCP одинаково проверяют права и одноразовый consent; replay, expiry и изменённый payload отклоняются |
| AC-AUT-22 | Все baseline/MCP и принятые addenda сохранены; неподдерживаемый source блокирует импорт, не исчезает из требований |
| AC-AUT-23 | Обычный новый commit и допустимые новые tests/dependencies проверяются автоматически без ручного редактирования protected target |
| AC-AUT-24 | Merge/container-running без functional evidence не даёт Done; rollback только на известный совместимый predecessor |

Главная метрика: ноль лишних human approval для in-scope шагов. Обязательные guardrails: все реальные границы соблюдены; нет ложных PASS/Done, скрытых unknowns или бюджетного reset. Для интеграционной приёмки нужны restart, concurrency, fault-injection, denial и полный цикл до milestone, не только mock/schema tests.

## 8. Совместимость с параллельными дополнениями

Ветки других PR не изменяются и не считаются уже интегрированными. На момент чтения:

| PR | Exact source | Как используется |
| --- | --- | --- |
| #3 | a9682e2a1eed01f2f83cd7f79131f3ed3d28e54a | Recovery/health requirements; не второй recovery executor |
| #10 | a8aed85403ab4329c4e0d0fe9ea9c34d7f8bfb7f | Review obligations и transitions; единый scheduler |
| #15 | eab3d2b1f3f2a18135ec9b16933f3690eea0de25 | Standing read-only review остаётся узким; не право писать код/запускать tests |
| #26 | 85bb926f53028768400b67422cb60be1fb800cc1 | Tracker binding и task identity; права не зависят от display label внешнего трекера |
| #79 | e2f7a0591cf84df7a021aa692fafeb27cdc8812f | Task/planner model, effort, speed; не дублировать настройки в новом профиле |

Перед реализацией нужен assembled exact-source index с принятыми версиями, проверкой hash и semantic dependency graph. Старые pending refs в baseline index не переписываются историческими догадками. Этот кандидат добавляет только AUT addendum; merge других дополнений требует additive reconciliation index/MANIFEST, а не last-writer-wins. Конкретный DAG реализации остаётся отдельным инженерным артефактом; здесь нет новых executable leaf IDs и dispatch.

## 9. Следующий инженерный этап и границы доказательств

Из четырёх контрактов выводятся implementation tasks, wire schemas команд/событий, controller tests и проверяемые role skills. Вначале вертикальный сценарий: contract/preflight → task → implementation → independent review → repair → разрешённый release/readback → milestone. Затем concurrency/restart/revocation и UI/API/MCP parity. Не начинать с генерации десятков несогласованных prompts.

Для этого документального кандидата проверяются структура JSON Schema, положительные/отрицательные примеры, закрытость полей, ссылки/hashes, сохранение baseline index и точный Git delta. Это не independent review, не реализация state machine, не protected CI и не запуск продукта. Полные product tests и перечисленные AC — NOT_RUN. Active policy, CI profiles, GitHub Actions, services, credentials и DF Assistant не меняются. До merge rollback означает оставить draft неприменённым; восстановление runtime этим документом не требуется и не заявляется.
