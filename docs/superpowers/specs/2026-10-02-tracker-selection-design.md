# SymphonyNext: выбор таск-трекера для каждого проекта

Редакция TRK-r1 от 02.10.2026. Дополнение к неизменяемой базе v0.5 и MCP-SN031-r2.
Основание: прямое требование владельца поддержать встроенный трекер, GitHub и Linear.
Статус: требования и критерии приёмки; адаптеры нового продукта НЕ реализованы этим документом.

## Решение и границы первой версии

В настройках каждого проекта выбирается один основной трекер: **SymphonyNext (native)**,
**GitHub Issues (github)** либо **Linear (linear)**. По умолчанию выбран native.
Все три варианта входят в первую принимаемую версию; ранние демонстрации native могут
выпускаться раньше, но не закрывают итоговую приёмку внешних адаптеров. Полный собственный
трекер из раздела 5 остаётся обязательным. Выбор внешнего трекера не превращает продукт
в оболочку над SaaS и не делает внешнюю учётную запись обязательной для native-проектов.

Принятый подход: адаптер выбранного источника + единый Symphony scheduler и локальный
Execution domain. Не выбраны два независимо редактируемых backlog с общей live-sync
и замена встроенного трекера сторонним: они создают конфликт владельцев и меняют цель.
Готовность upstream GitHub/Linear adapters оценивается отдельно: их наличие не доказывает
project isolation, запись, review и recovery нового продукта.

## Точное уточнение прежних требований

Файлы SPECIFICATION.md, TASKS.md, planning/backlog.json и planning/traceability.json
остаются исторической базой с прежними SHA256. Это обязательное дополнение включается
через planning/spec-index.json. При противоречии действует только следующая узкая замена;
остальные исходные требования, безопасность, MCP parity и критерии MVP сохраняются.

| Прежнее положение | Действующее уточнение |
| --- | --- |
| INV-02, DEC-04, DEC-05; разделы 3–5 | Локальный project registry и полноценный native обязательны; отсутствие обязательного Linear сохраняется. Запрет добровольного live-подключения GitHub/Linear отменён только для явно выбранного provider. |
| TSK-01, DATA-03, DATA-09 | Native UUID/номер сохраняются. Внешняя задача имеет локальный устойчивый task_ref, не вторую редактируемую native issue. Run и уникальный active claim ссылаются на project_id + task_ref + binding generation. |
| DATA-01, DATA-05, INT-07 | Для native прежняя атомарная DB transaction сохраняется. Во внешнем режиме tracker business fields принадлежат выбранному provider; локальные Execution/audit/outbox и подтверждённая проекция не подменяют его. Распределённая транзакция с SaaS не обещается. |
| TSK-04, TSK-10, UI-02 | Native UI/optimistic concurrency/all-or-nothing bulk не урезаются. Внешние UI-команды проходят adapter capability checks и показывают confirmed/pending/conflict. Неподдерживаемый атомарный bulk отключён, не маскируется частичным success. |
| TSK-13 | Native attachments остаются локальными. Внешние вложения — разрешённые provider refs или явно полученные project-scoped snapshots; токены и приватные URL не превращаются в публичные ссылки. Evidence выполнения остаётся в локальном защищённом storage. |
| INT-01, INT-02, INT-08; раздел 10 | Native остаётся default, но routing выбирает native/github/linear на уровне проекта. Используются нормализованные scoped domain tools, не произвольный upstream GraphQL/HTTP доступ агента. |
| NFR-11, AC-34, AC-73 | Без Linear работают native-проекты и ручные локальные функции; тест полной автономности выполняется в профиле без внешних tracker bindings. Выбранный внешний provider — явная зависимость только соответствующего проекта. GitHub как code provider не смешивается с tracker provider. |
| Разделы 17.2, 18, 26; SN-043, BOOT-07 | Переход на native — выбранный владельцем вариант, не обязанность каждого проекта. При выбранном cutover обязательны native acceptance, drain, snapshot, source→target mapping и count/hash readback; старые admission снимаются до передачи единственного execution owner. После такого перехода прежний bootstrap сохраняется stopped для rollback, без удаления. До выбранного cutover текущая постоянная GitHub-очередь продолжает работу. |

## Требования

**TRK-01. Выбор и область.** `tracker.kind = native | github | linear` задаётся отдельно
для каждого проекта. Один активный источник бизнес-задач на project/binding generation.
Допустимы параллельные проекты с разными трекерами. Подключение одного не меняет другой;
совпадение читаемых task IDs, имён или пользователей не объединяет scope.

**TRK-02. Настройка.** Администратор проекта выбирает provider, подключение, разрешённый
scope и карту статусов; получает preview, проверку доступа и явное сохранение версии.
GitHub: installation/account reference, stable repository ID, фильтр задач/меток.
Linear: workspace identity, team ID и необязательный project ID, фильтр задач/меток.
Идентификаторы читаются из provider API, а не угадываются по названию. Code-repository
binding и tracker binding отдельны: Linear/GitHub Issues могут управлять задачами кода
из другого разрешённого репозитория. Проверяются обе привязки, без расширения доступа.

**TRK-03. Источники истины.** Native хранит задачи/комментарии локально. Во внешнем
режиме provider authoritative для title/description/business status/assignee/labels
и опубликованных комментариев. SymphonyNext хранит task_ref, внешний stable ID и URL,
connection/scope ID, binding generation, source revision/fingerprint, время readback,
нормализованную проекцию, execution snapshot, runs/attempts, leases, budgets, approvals,
review evidence и audit. Внешний ID не даёт полномочий. Один внешний объект не может
иметь два активных execution owner в пересекающихся bindings, даже через разные credentials.
Кэш обозначается временем свежести; это не независимый native backlog.

**TRK-04. Общий контракт.** Адаптер обязан читать scoped задачи/контекст с полной
пагинацией, обновлять live state, получать blocking dependencies, создавать draft задачи,
обновлять разрешённые поля/статус, публиковать комментарий и idempotent workpad/evidence ref,
создавать отдельную review-задачу. Выдаёт нормализованные IDs, business categories,
revision/fingerprint и capabilities. Ошибки различают forbidden, not_found,
conflict, rate_limited, unavailable, unsupported и unknown_outcome. Возможности,
не поддержанные provider API, не имитируются успешным ответом.

**TRK-05. Статусы и admission.** Карта использует категории TSK-05:
triage/backlog/unstarted/started/review/completed/canceled. `blocked` — отдельная причина
недопуска, не скрытая новая категория. GitHub open/closed дополняются явно выбранной
схемой управляемых labels и state_reason; Linear workflow-state IDs сопоставляются
категориям, не строкам переведённого названия. Неизвестная/неоднозначная карта блокирует
admission. Закрытая/canceled задача не равна успешному execution или выполненному blocker.
Перед каждым claim проверяются live scope, статус, зависимости, local admission,
версия snapshot, policy и budget. Внешнее редактирование само по себе не выдаёт approval.

**TRK-06. Один процесс разработки и review.** Для всех provider сохраняется цикл
задача → исполнитель → PR и реальные тесты → отдельная review-задача → новая reviewer
сессия → исправления или выпуск. Обе карточки принадлежат выбранному трекеру, а exact
commit/тесты/решение и локальный execution journal связаны устойчивыми references.
Свежий commit требует свежего review; отсутствие тестов не равно PASS. Созданная агентом
подзадача поступает без self-admission. Ручной Done во внешнем трекере не подтверждает
release gate, хотя бизнес-статус отображается правдиво. Scheduler остаётся один.

**TRK-07. Безопасность и полномочия.** Authentik/project RBAC остаются входом продукта;
подключение provider не заменяет локальные ACL. Scope сервиса ограничивается конкретным
проектом и проверяется при прямом ID, списке, поиске, webhook, writes и выдаче attachments.
Секреты — только references в защищённом credential store, не UI/чат/Git/logs/agent env.
GitHub App и Linear OAuth имеют минимальные утверждённые разрешения; текущие роли и
revocation проверяются. Актор аудита и внешний автор отображаются отдельно, без
имперсонации человека. Общее сервисное подключение не даёт всем участникам полный scope.

**TRK-08. Записи и конкуренция.** UI/API/MCP/agent commands используют один policy-aware
adapter boundary. До записи сохраняется intent/idempotency key; после — authoritative
readback. Timeout после mutation сначала сверяется, не приводит к слепому повторному POST.
При отсутствии provider-native conditional write применяется read/compare + serialisation
своих операций, но абсолютная защита от чужой одновременной записи не обещается: конфликт
явно возвращается, чужие labels/поля не перезаписываются целиком. Workpad и review-задача
дедуплицируются по task_ref/этапу/exact commit. Unknown outcome удерживает новые зависимые
действия, пока результат не установлен.

**TRK-09. Доставка и отказы.** Polling с полной пагинацией и курсором сверки обязателен;
проверенные подписанные webhooks — ускорение, не единственный источник истины. Дубликаты,
события не по порядку и разрыв соединения не создают повторные runs. Перед внешней записью
и admission выполняется fresh readback. 401/403 требуют исправления доступа; 429/5xx имеют
конечный backoff/Retry-After и deadline по действующей policy. Сбой внешнего трекера ставит
intake только его проекта в hold, не останавливает постоянный Symphony и другие проекты.
Активные workers следуют существующей fail-closed partition policy; новые действия не
выполняются по устаревшему кэшу. Автоматического fallback в другой трекер нет.

**TRK-10. Смена трекера.** Настройка доступна и после создания проекта, но активный
provider не меняется молча: pause intake → завершение/безопасная остановка активных runs
и сверка pending writes → preview новой привязки и mapping → explicit apply новой
generation → readback → отдельный resume. Политики/leases старой generation не действуют
в новой. История runs/evidence остаётся доступной по старым references. Перенос задач между
native/GitHub/Linear не выполняется автоматически: первой версии достаточно preview
существующего scope и явных mapping, без массового двустороннего клонирования истории.
Импортированные/сопоставленные задачи получают admission=false; завершённые не запускаются
снова из-за cutover. Ошибка оставляет intake на паузе, без двух активных владельцев.

**TRK-11. Единый интерфейс.** Web/mobile/MCP позволяют выбрать трекер, проверить доступ,
читать/создавать/редактировать разрешённые общие поля, видеть очередь, запросить выполнение,
ответить на вопрос, выдать scoped approval и открыть оригинал задачи. Показаны provider,
scope, подтверждённый business state, execution state и свежесть/ошибка синхронизации.
UI не обещает полный клон GitHub Projects/Linear. Unsupported функции выключены с причиной;
локальный журнал/approved snapshots остаются доступны по ACL при сбое provider, внешние
записи офлайн не объявляются выполненными.

**TRK-12. GitHub Issues.** Первая интеграция работает с issues выбранного репозитория;
объекты pull_request из Issues API не становятся заданиями. Закрытие с completed и
not_planned различается. Управляемые labels не стирают чужие labels. Удаление/перенос issue,
смена repository binding и отзыв installation требуют сверки scope и останавливают
неподтверждённый admission. GitHub Projects v2/Enterprise как дополнительные варианты,
полная реплика board/custom fields и произвольные репозитории не входят автоматически.

**TRK-13. Linear.** Первая интеграция работает с issues выбранного workspace/team и,
при настройке, project. Используются stable IDs и cursor pagination; учитываются archived
и удалённые задачи при reconciliation. HTTP 200 с GraphQL errors/partial data не принимается
за успех всей операции. Разрешения чтения, изменения, создания issue и комментариев
проверяются отдельно. Конкретные scopes/schema закрепляются по официальному контракту
при реализации; наличие старого Linear adapter или доступа к другому проекту не есть acceptance.

**TRK-14. Расширяемость и приёмка.** Реестр provider capabilities и versioned adapter
interface позволяют позже добавлять другие трекеры без замены scheduler. Общие conformance
тесты проверяют три адаптера, изоляцию и ошибки; provider-specific интеграционные тесты
дополняют их. Mock/unit успешность не выдаётся за live external acceptance. Необходимые
учётные данные проверяются только в утверждённых test scopes; их отсутствие даёт BLOCKED.
Не включаются новые credentials, migration или runtime dispatch самим принятием этого ТЗ.

## Приёмка первой версии

| ID | Проверяемый результат |
| --- | --- |
| AC-TRK-01 | Native default: новый проект без tracker credentials выполняет ручной и агентный workflow без обращений к Linear/GitHub tracker API. Разрешённая GitHub code-интеграция оценивается отдельно. |
| AC-TRK-02 | GitHub: выбрать scope → получить все разрешённые issues → создать/обновить задачу → выполнить → опубликовать workpad/PR refs и отдельную review issue. Pull requests из issue-list исключены. |
| AC-TRK-03 | Linear: аналогичный live-путь в test team/project, пагинация, стабильные workflow IDs, подтверждённые comment/status writes. |
| AC-TRK-04 | Во всех трёх провайдерах закрытие задачи без тестов/review не разрешает release; новый commit аннулирует прежнее review. Нет второго scheduler. |
| AC-TRK-05 | Native + GitHub, native + Linear и GitHub + Linear работают параллельно; сбой одного provider не останавливает другой проект/оркестратор. |
| AC-TRK-06 | Одинаковые читаемые IDs, подмена project/scope, пересечение bindings, чужие webhook и direct URL не раскрывают данные и не создают второй claim. |
| AC-TRK-07 | Duplicate/out-of-order webhook, повтор страницы и restart до/после mutation не создают второй run/comment/workpad/review issue. Unknown write не переигрывается вслепую. |
| AC-TRK-08 | Concurrent user edit и устаревшая карта статусов дают явный conflict/hold, сохраняют чужие поля; ambiguous GitHub labels не допускают запуск. |
| AC-TRK-09 | 401/403, quota/429, 5xx, GraphQL partial errors, удаление/архив/перенос приводят к корректному ограниченному hold, не к Done или скрытому fallback. |
| AC-TRK-10 | Для каждой направленной пары разных provider проверяется pause/drain/switch: новая generation, история доступна, второй активный owner отсутствует, импорт не открывает admission. |
| AC-TRK-11 | Desktop/mobile/MCP показывают один выбранный источник, поддержку функций, stale/pending/conflict и отдельные business/execution статусы; native возможности раздела 5 не урезаны. |
| AC-TRK-12 | Общий adapter suite и live external fixtures проходят на exact revisions; выгрузки/логи не содержат секретов. Разделены source review, unit, integration и production acceptance. |

## Порядок включения в разработку

planning/tracker-selection.json задаёт пять новых planned work packages и связи с базовыми
SN-задачами. Это обязательное расширение требований, а не готовый execution DAG/importer.
После принятия refinement планировщик добавляет его конечные задачи к приёмке SN-042/SN-044,
сохраняя исходные зависимости и полный MCP-SN031-r2; unsupported refinement останавливает
импорт, а не игнорируется. Никакие baseline задачи, допуски, deadlines или старые CI-попытки
не сбрасываются. Первая вертикаль native и текущая постоянная bootstrap review-очередь
не переключаются на новый tracker этим документом. DF Assistant и его Linear исключены.

## Основания API (проверены 02.10.2026; не свидетельство нашей реализации)

- GitHub Issues API: https://docs.github.com/en/rest/issues/issues — issues/PR distinction, scope/state/transfer.
- GitHub Labels API: https://docs.github.com/en/rest/issues/labels — операции только над управляемыми метками.
- Linear API: https://linear.app/developers/graphql — GraphQL, команды/ID, pagination, partial errors.
- Linear OAuth: https://linear.app/developers/oauth-2-0-authentication — разрешения и жизненный цикл доступа.
- Linear webhooks: https://linear.app/developers/webhooks — валидация и доставка событий.
