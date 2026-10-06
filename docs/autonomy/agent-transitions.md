# Протокол переходов между агентами

Версия: AUT-TRANSITION/v1. Нормативный дизайн типизированных команд/событий; production handlers и wire-schema ещё не реализованы. Не создаёт вторую очередь рядом с существующим scheduler.

## 1. Предложение агента и событие сервера — разные объекты

Агент отправляет команду с `schema`, `command_id`, `idempotency_key`, `project_id`, `task_id`, `attempt_id`, `repair_chain_id`, `lease_epoch`, `expected_state_version`, `contract_id`, `contract_revision`, `policy_sha256`, `context_manifest_sha256`, `transition_kind`, `payload`, `evidence_refs`.

Сервер устанавливает actor principal/role из доверенного транспорта, проверяет membership, текущие bindings и полномочия. Поля модели не доказывают identity, source truth или право перехода. Неизвестная major schema, неизвестный kind, неизвестные поля и несоответствующий payload отклоняются `invalid_input`; нет угадывания команды по тексту.

Принятое событие дополнительно содержит `event_id`, `server_sequence`, `actor_principal_id`, `actor_role`, `recorded_at`, `new_state_version`, `command_payload_sha256`, `evidence_manifest_sha256`, `policy_decision_ref`. Только сервер записывает это событие. Подпись/доверенный storage receipt свидетельствует о происхождении, а не заменяет фактическую проверку результата.

## 2. Конечные состояния и permitted transitions

| transition_kind | Кто предлагает / кто применяет | Precondition | Результат |
| --- | --- | --- | --- |
| plan_revision | Planner / Scheduler | Valid goal, matching plan revision, covered requirements, acyclic DAG, task scope subset | READY leafs либо BLOCKED по реальным prerequisites; не автоматический запуск |
| start_attempt | Scheduler | READY, dependency acceptance, live delegation, atomic budget reservation, unique claim | RUNNING с новым fenced lease |
| submit_candidate | Implementer / Controller | Current attempt/lease, exact source identity, required handoff and evidence | REVIEW_PENDING и durable review obligation |
| review_accepted | Reviewer / Controller | Independent assignment, exact current review tuple, complete required evidence | RELEASE_PENDING либо ACCEPTANCE_PENDING по заранее заданному deliverable type; ещё не Done |
| accept_nonrelease | Controller | Для задачи заранее объявлен результат без runtime/release; обязательные review/checks и критерии выполнены | ACCEPTED без фиктивного deploy; изменение типа задачи не используется для обхода runtime gate |
| review_changes_required | Reviewer / Controller | Findings bound to exact tuple | REPAIR_PENDING; linked repair in same budget chain |
| review_blocked | Reviewer / Recovery controller | Missing source/evidence/dependency classified | HELD или WAITING_EXTERNAL; не ACCEPTED |
| release_begin | Release controller | Current independent review, trusted checks, target/constraints/migration gates | RELEASE_IN_PROGRESS; fixed release intent and artifact identity |
| release_observed | Release controller | Authoritative merge/webhook/readback for that intent | VERIFYING_RUNTIME; не Done |
| runtime_accepted | Verifier evidence / Controller | Exact deployed identity and required functional assertions | ACCEPTED task; dependencies may advance |
| recover | Recovery controller | Typed diagnosis, allowed action, remaining chain budget, reconciled prior writes | RECOVERING then concrete next state; no history reset |
| request_human | Agent / Controller | Valid taxonomy and actual decision requirement | Scoped NEEDS_HUMAN + durable inbox/outbox |
| revoke_or_stop | Authenticated owner / Controller | Current authorization to stop project | Stop intake, fence pending actions, bounded safe cleanup; preserve evidence |

Все переходы сверяют `expected_state_version`; stale writer/lease отклоняется `conflict`. Human resume сам по себе не запускает старую команду: заново проверяются state, delegation, budget и prerequisites. Reporting milestone не создаёт NEEDS_HUMAN; human-decision milestone останавливает только согласованный scope.

## 3. Handoff и exact-source review

`submit_candidate.payload` обязательно содержит repository binding ID, base_sha, head_sha, tree_sha, PR identity, requirement/acceptance revision, declared changed paths, check records, known issues и source-context manifest. Проверки: command/working-directory/environment identity, UTC start/end, actual exit code либо явный NOT_RUN/BLOCKED, log artifact hash, applicable acceptance IDs. Незапущенная проверка не получает exit_code=0. Доверенные checks контроллер читает отдельно; авторский JSON не превращается в trusted CI.

Review tuple: repository + task/criteria revision + base/head/tree + effective policy revision + context/toolchain/skill manifest identity + evidence manifest. Новый HEAD/base, изменённые criteria или релевантная policy делают прежнее review непригодным. Исторический результат сохраняется, но не может открыть gate нового candidate. Независимое повторное review назначается автоматически в рамках действующей делегации.

Недоступный или усечённый source/evidence означает BLOCKED, а не «замечаний нет». Source review и исполнение тестов различаются. Допустимое дерево с новым тестом или разрешённой dependency должно получать новую автоматическую CI-проверку; будущий контроллер не должен требовать от владельца вручную переписывать target каждого обычного commit. Защищённые runner/policy/acceptance-suite не меняются candidate-ом. Действующие frozen CI profiles и исторические HOLD этим требованием не изменяются и не переисполняются.

## 4. Надёжность, бюджет и неизвестные записи

Изменение состояния, создание следующей obligation и outbox фиксируются одной транзакцией. Доставка at-least-once, поэтому consumers дедуплицируют event_id/intent; ровно-однократное выполнение произвольного внешнего API не обещается. Контроллер хранит устойчивый intent до внешней mutation, provider idempotency key при наличии и результат последующего authoritative readback.

Повтор того же intent с тем же payload возвращает сохранённый результат; тот же ключ с другим payload — conflict. После timeout/падения при неизвестном внешнем результате сначала reconciliation. Без достаточных данных — HELD, не слепой повтор. Lease expiry не делает старый external write невыполненным; новый исполнитель получает обязанность reconcile.

Резервы атомарны на уровне проекта; расходы, оценка, резерв и фактический usage различаются. Неизвестная стоимость учитывается консервативно. Retry/repair/profile changes наследуют repair_chain_id и его накопленные пределы: новая подзадача, другая модель или новый процесс не обнуляют бюджет. Времена/cooldown и состояние попыток переживают restart. Provider billing имеет свои особенности; абсолютная гарантия счёта невозможна без соответствующей поддержки провайдера, поэтому admission резервирует верхнюю оценку и запас.

## 5. Отзыв, drift и release

Делегация проверяется при admission и непосредственно перед каждым side effect. При отзыве новые действия запрещены; queued capability аннулируется fencing epoch. Уже отправленный внешний запрос может завершиться — контроллер фиксирует outcome и выполняет только отдельно разрешённую безопасную cleanup/compensation. Обещание мгновенно отменить внешний запрос не допускается.

Изменение branch HEAD, resource/config identity, contract revision или lease между проверкой и действием вызывает повторный preflight либо отказ. CAS/expected-head и locks применяются там, где интерфейс их поддерживает; оставшееся race-окно документируется, а не скрывается.

После merge нельзя считать будущий webhook выполнившимся. Записать exact merge commit/image/config и проверить runtime отдельно. Auto rollback допускается только на фактически проверенный совместимый predecessor; отсутствие такого predecessor или несовместимая схема не разрешает destructive restore.

Обычная доработка приложения не изменяет работающий policy controller или его trusted suite. Self-update контролирующего слоя выделяется в отдельный защищённый release с независимыми checks; кандидат не аттестует собственный authorizer.
