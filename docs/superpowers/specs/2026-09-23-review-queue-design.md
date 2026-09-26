# Symphony Next — автоматическая очередь review и проверяемые переходы

Дата: 23 сентября 2026 года. Статус: **проект дополнения для согласования, не реализованная функция и не разрешение запуска**.

База: `pupkinson/SymphonyNext`, main `c3c8bce82d148c3e558481644eb5d0a4072fdb6f`, tree `05e57efc3f6ac81bc3ac11d8eef39e1c7fceb8b9`.

## 1. Основание и отличия от принятого ТЗ

Запрос владельца: после реализации и публикации PR исполнитель передаёт ссылку, точный commit, требования и результаты тестов; создаётся отдельное задание review, которое выбирает Symphony. Новый reviewer получает отдельный checkout, публикует замечания и результат «Принято», «Нужны исправления» или «Проверка заблокирована». Результат определяет следующую задачу автоматически. Отсутствующие тесты не считаются успешными; новый commit требует новой проверки.

В принятой базе уже существуют AUTO-02–04, QUAL-01–04, PLAN-04/07/08, DEP-02–05 и SN-030: разделение implementer/reviewer/verifier, новый контекст, exact HEAD, защищённые тесты и раздельная приёмка release. SN-014 описывает durable commands, SN-015 — единый scheduler/leases. Это дополнение не заменяет их и не создаёт второй scheduler: оно уточняет **автоматическую регистрацию, выполнение и завершение заданий review/repair/verification/release в одной системе**.

Авторская рекомендация: агент вызывает типизированную команду передачи результата, а создание единственной review-задачи и последующие переходы гарантирует сервер. UI может показывать «проверку создал исполнитель», но полномочия, транзакцию и допуск определяет оркестратор. Исполнитель не запускает следующую модель напрямую и не назначает себе проверяющего.

Альтернативы: цепочка произвольных agent-created issues требует доверять завершению каждого агента; только GitHub bot-review не управляет всей локальной очередью, зависимостями и release. Выбран единый Symphony scheduler с role jobs. Внешний reviewer может позднее стать адаптером со строгим контрактом, но не обязательной заменой серверного reviewer и не доказательством трёхзначного решения по произвольному комментарию бота.

## 2. Модель выполнения и статусы

Бизнес-задача имеет stable task_id, её попытки и артефакты версионируются. Review является отдельным видимым заданием встроенного трекера, связанным с исходной задачей и конкретной delivery revision; это не ещё одна копия feature-задачи.

Логический путь:

```text
implementation → candidate submitted → deterministic verification → review queue
review accepted → release eligibility → merge → deploy/readback (если применимо) → task accepted
changes required → repair attempt → новый candidate → новое review
review blocked → ожидание/устранение конкретного препятствия → проверка условий → допустимое продолжение
```

Это **предлагаемые целевые стадии продукта**, не команды установленной bootstrap Symphony. Для первой версии роли в проекте последовательно занимают существующий слот. Разные проекты могут двигаться независимо. Паузы, квоты и запрет двойного исполнителя сохраняются.

Человеческий итог стадии проверки имеет ровно три значения:

| Итог | Условие | Следующий шаг |
| --- | --- | --- |
| Принято / ACCEPTED | Независимая проверка кода завершена без неустранённых блокеров; все обязательные проверки покрыты достоверным PASS; версии и права актуальны | Поставить release job или закончить задачу на заранее определённом acceptance level |
| Нужны исправления / CHANGES_REQUIRED | Есть подтверждённый дефект, невыполненное требование либо отсутствующий обязательный тест, который надо написать | Один связанный repair job в той же ветке/PR, с конкретными findings и общим бюджетом |
| Проверка заблокирована / BLOCKED | Недостаточно достоверных данных/доступа/среды, несовместимый контракт, истёкший бюджет, неприменимый или незавершённый результат | Классифицированное ожидание, разрешённое восстановление либо один запрос владельцу; никакого auto-accept |

QUEUED/RUNNING/WAITING — промежуточные состояния выполнения, а SUPERSEDED/CANCELLED — состояние применимости задания. Они не четвёртый вердикт и не подмена BLOCKED. Поздний ACCEPTED для старого HEAD остаётся в истории, но не меняет текущую задачу.

## 3. Обязательные требования предлагаемого дополнения

**REVQ-01. Единая очередь.** Типы заданий implementation, review, repair, verification и release использует один scheduler и один источник истины. Очередь review в UI — представление тех же записей. Новые постоянные планировщики и неучтённые субагенты не создаются.

**REVQ-02. Серверная передача результата.** Команда submit_candidate принимает task/attempt, expected_version, PR/repository, exact head/tree/base, ссылки на evidence и idempotency key. Actor, права и допустимая роль выводятся из проверенной сессии. Сервер сам сверяет PR/commit, сохраняет submission и создаёт уникальное review-задание либо точно сообщает неприменимость/недостаток данных. Автор не может установить ACCEPTED, выбрать собственный approval identity или передать произвольный управляющий prompt как review policy. Название команды здесь концептуальное, не уже доступный MCP tool.

**REVQ-03. Нет разрыва между стадиями.** В одной транзакции БД сохраняются доставка артефакта, обязательство следующей стадии и событие outbox. Внутренняя job-строка также создаётся транзакционно, когда находится в той же БД. После crash до ответа повтор возвращает тот же delivery/review ID. Сбой между внешним GitHub PR write и submit_candidate закрывает reconciliation по авторитетному GitHub readback: сверить заранее записанную publication intent и branch/head, не создавать второй PR. Без полноценного handoff создаётся проверяемый BLOCKED, а не придуманная успешная сдача.

**REVQ-04. Дедупликация и восстановление.** Одна логическая review obligation определяется project/repository/task/delivery/head/diff-base/spec/policy/test-plan revision. Duplicate webhook, submit и restart не создают вторую задачу и второй оплачиваемый запуск. Повтор после crash — новая attempt той же job только после проверки прежнего владельца/внешнего запроса; истёкший lease не доказывает смерть процесса. Outbox предполагает возможные повторы доставки, а не обещание exactly-once внешнего исполнения.

**REVQ-05. Независимый reviewer.** Новая model session, отдельный checkout и чистый role-scoped context. Reviewer получает исходные требования, независимый review contract, полный diff/список файлов и ограниченный handoff автора; скрытая история implementer не переносится. Другая модель или движок допустимы по risk/data/budget policy, но не обязательны для каждой маленькой правки и не доказывают независимость сами по себе. Доступны чтение и публикация только собственного структурированного заключения через broker; нет push/merge/deploy, секретов implementer или самоповышения прав.

**REVQ-06. Immutable input.** Review фиксирует repository ID, PR number, head_sha, head_tree_sha, diff_base_sha, observed target-base SHA, spec/policy/test-plan revisions и hashes. Проверяется checkout именно commit, а не подвижного имени ветки. Вложения и журналы берутся по immutable artifact references с ACL. Diff автора не является единственным источником: сервер получает полный diff самостоятельно.

**REVQ-07. Новый commit — новая проверка.** Любое изменение candidate HEAD создаёт новую review revision и лишает прежний verdict права разрешить merge нового commit. Можно выполнять адресное delta-review с предыдущими findings, но нужно новое решение для нового exact HEAD и проверка полного набора изменённых файлов. Результат старого review не переносится автоматически, даже при похожем коде. Историческая запись сохраняется.

**REVQ-08. Целевая ветка и состав.** Перед merge сверяются current head, target-base, policy и применимость evidence. Для изменившейся целевой ветки формируется/проверяется актуальный merge candidate и выполняются применимые интеграционные проверки. Если новый base меняет review diff/контракты/риск — требуется новое применимое review. Отсутствие текстового конфликта не доказывает корректность сочетания двух PR; неизменённый отдельный PR не следует полностью переоценивать без изменения его проверяемого контекста.

**REVQ-09. Правдивые тестовые результаты.** Обязательный набор тестов определяется до исполнения и принадлежит trusted verification policy, а не автору PR. Статусы PASS, FAIL, NOT_RUN, ERROR, SKIPPED и NOT_APPLICABLE различны. Для обязательной проверки последние четыре не заменяют PASS. NOT_APPLICABLE допустим только по заранее принятой проверяемой причине, не как средство исправить красный тест. Missing regression, который надо реализовать, даёт CHANGES_REQUIRED; невозможность выполнить существующий тест из-за среды — BLOCKED. Report содержит команды, exit codes, suite/image/dependency/source IDs, hashes и субъект исполнения.

**REVQ-10. Проверки без лишнего расхода модели.** Сначала недорогие детерминированные проверки и trusted test job; затем содержательный reviewer, когда входы готовы. Модель не нужна, чтобы посчитать checksum или запустить известную команду теста. Успешный отдельный static check не подменяет весь gate. Упавший продуктовый assertion направляет repair, а инфраструктурная ошибка — путь восстановления, не автоматический кодовый ремонт.

**REVQ-11. Read-only не запрещает корректные тесты.** Авторитетный checkout reviewer неизменяем. Тесты работают через изолированный verification runner с disposable writable build/cache/test workspace или writable копией, без изменения исходного Git-объекта и без production secrets. Исполняемый из PR код недоверен: runner отделён от привилегированного издателя CI/evidence. Reviewer не выполняет произвольные команды автора с release-правами. Hash входов проверяется до/после, внешние зависимости и сеть ограничены контрактом.

**REVQ-12. Structured verdict.** Итог включает review/job/attempt identity, input hashes, session/profile, полноту рассмотренных требований/файлов, severity, blocking, path/line, evidence, воспроизводимый failure path, ожидаемое исправление, ограничения и recommended_next_action. Каждый finding получает устойчивый ID и собственный статус. Свободный текст «всё нормально», emoji, выход процесса 0 или отсутствие сообщения не считаются решением. Невалидный/неполный отчёт даёт BLOCKED и не разрешает release. Рекомендация модели не является исполняемой командой.

**REVQ-13. Два доказательства, один понятный итог.** Source review и результаты независимых проверок сохраняются раздельно; сервер формирует три человеческих итоговых статуса по их совместной применимости. Source assessment без findings при отсутствующих обязательных тестах ещё не ACCEPTED. После восстановления среды неизменный завершённый source assessment можно использовать вместе с новыми достоверными тестами, не вызывая того же reviewer снова только ради переписывания отчёта. Любое изменение HEAD, требований, policy или review coverage требует новой проверки применимости и, когда нужно, нового review.

**REVQ-14. Защищённый переход.** Только coordinator state machine применяет verdict в транзакции: проверяет current version, роль, lease/fencing epoch, input key, обязательные checks, бюджеты, manual pause и делегацию. Сохраняются решение, следующий job и outbox; late/stale result не переводит задачу. Publisher комментариев в GitHub и UI не является источником истины вместо БД. При недоступной БД — hold, не альтернативное разрешение в памяти.

**REVQ-15. Ремонт без размножения задач.** Блокирующие findings агрегируются в один repair job текущей delivery. Исполнитель получает IDs findings, regression target и прошлый evidence; исправляет существующую ветку/PR. Повтор одного текста замечания не создаёт новый дефект. Новый commit ведёт к новой review revision. Стиль/необязательные улучшения не блокируют вне acceptance policy; расширение scope направляется в отдельно предложенный backlog, без самодопуска.

**REVQ-16. Семантика BLOCKED.** Отличать auth/permission, unavailable tool, environment/dependency, incomplete evidence, ambiguous outcome, quota, conflict и human decision. Восстанавливать только разрешённый конкретный компонент и с конечным retry/deadline. Missing permission не лечится другой более дорогой моделью; отказ инструмента не обходится другой identity. После устранения причины resume начинает с первой непринятой стадии, а не с повторной реализации. Повторные уведомления/incident jobs дедуплицируются.

**REVQ-17. Ограничение циклов и разногласий.** Общий budget принадлежит исходной задаче и включает implementation, review, tests, repairs и эскалации. Сохраняется исходный предел двух repair cycles и одной допустимой смены профиля, если effective policy не строже. Повтор signature без нового evidence → hold. Несогласие автора с finding сохраняется как доказательная appeal, а не молчаливое удаление; спор разрешает назначенный независимый reviewer или владелец по risk policy. Второй reviewer обязателен только для заранее выбранных рисков/конфликтов, не бесконечное голосование моделей.

**REVQ-18. Приоритет и освобождение слота.** В первой версии после передачи результата и подтверждённого освобождения writer review выбирается раньше новой обычной implementation в том же проекте. Emergency/recovery и явная пауза имеют приоритет; между проектами нужны справедливость и контроль возраста очереди. Нельзя ставить review в ожидание завершения родительской feature-задачи: оно зависит от опубликованного candidate, иначе возникнет цикл. Repair attempts образуют возрастающую историю revisions, а не циклические depends_on бизнес-DAG.

**REVQ-19. Приёмка не равна deploy.** ACCEPTED review разрешает постановку release job только при applicable gates. Merge/deploy выполняет другой ограниченный субъект через существующий GitHub→Coolify webhook path, без подтверждения каждого обычного действия внутри уже принятой делегации. Dependent leaf разблокируется по объявленному типу evidence (например accepted-and-merged source либо deployed functional result), а не от одного комментария reviewer. Release не нужен для каждой документационной задачи; NOT_APPLICABLE должен быть определён её контрактом. Неудачный deploy не обнуляет честно выполненный review, но не даёт task/runtime PASS.

**REVQ-20. Trusted checks как часть продукта.** В первую рабочую поставку входит независимое self-hosted выполнение обязательных проверок и публикация настоящего exact-SHA результата с авторизованной identity. Это не требует GitHub Actions. Writer не может подписать собственный PASS. Review-агент и CI reporter — разные роли. Отсутствие CI signal остаётся BLOCKED; прошлые owner exceptions для PR8/PR9 не превращаются в постоянное автоматическое исключение.

**REVQ-21. UI и MCP.** Доска показывает исходную задачу, review/repair/release jobs, точный HEAD, кто/что проверял, текущий verdict/препятствие, budget и следующий разрешённый переход. Через MCP доступны те же read/submit/request review/comment/appeal/pause/resume операции по ролям. ChatGPT не может подставить себя как независимого reviewer собственного кода или создать release authority. Названия wire tools закрепляются в существующем capability registry MCP, не угадываются из этого документа.

**REVQ-22. Liveness и критерий успеха.** Контроль отдельно отслеживает candidate без review, review без прогресса, завершённую проверку без перехода, неотправленный outbox, публикацию без readback и превышение queue-age. Успех продукта — проверенные принятые изменения, частота возвратов/откатов, время review, стоимость принятого результата и вмешательства человека, а не количество созданных агентами задач. Приёмка включает остановку/перезапуск между стадиями без потери и дублирования jobs.

## 4. Минимальные контракты данных

Это описание будущих контрактов, не готовая JSON Schema и не новые зарегистрированные инструменты.

| Запись | Минимальные поля |
| --- | --- |
| CandidateSubmission | project/task/delivery/attempt, repository_id/PR, head/tree/diff-base/target-base, spec/policy/test-plan revisions, artifact manifest refs/hashes, author identity, expected_version, idempotency key |
| ReviewJob | source task/delivery, immutable input key, stage, priority, effective role/profile/data scope, budget reservation, lease/epoch, status, created/deadline times |
| SourceAssessment | exact input key, reviewer session/identity, coverage of requirements/files, finding IDs, evidence/limitations, completed/incomplete, attestation provenance |
| VerificationEvidence | exact input/environment/suite identity, trusted runner/reporting identity, observed assertions, exit codes and PASS/FAIL/NOT_RUN/... for every required check |
| ReviewDecision | combined input/evidence hashes, ACCEPTED/CHANGES_REQUIRED/BLOCKED, applicable findings, unresolved blockers, policy version and coordinator validation |
| TransitionReceipt | predecessor version, verified decision/input key, following job ID, changed state, actor, epoch, event sequence, idempotency and external publication state |

Субъект/полномочия устанавливаются транспортом и broker, не произвольными полями от модели. Криптографический hash доказывает неизменность bytes, но не достоверность теста; для доверия нужны происхождение и изоляция исполнявшего субъекта. Ошибки и payload от repo/issues считаются данными, а не новыми инструкциями.

## 5. Предлагаемое распределение работ

Не добавляем ещё одну огромную top-level задачу «автоматизация review». Основной owner — существующая **SN-030**, интеграционные owners — соответствующие существующие задачи.

| Область уточнения | Owner / связь | Проверяемый результат |
| --- | --- | --- |
| Submission, stage jobs, outbox, input identity | SN-014 + SN-030 | Долговечная, идемпотентная передача и три нормализованных итога |
| Очередь, claims, revisions, priority, pause | SN-015 + SN-030 | Review выбирается штатной Symphony, нет самозапуска/двойного worker |
| Изоляция reviewer и evidence/test runner | SN-016/SN-017 + SN-030 | Read-only исходники, изолированное исполнение тестов, независимое происхождение результата |
| Repair/blocked/anti-loop и бюджеты | SN-030 с существующими policy/budget/recovery owners | Следующая стадия выбирается по правилам, повтор не сбрасывает расход |
| Release и зависимые задачи | Существующие DEP-02–05/PLAN-08 owners | Exact merge/readback, только допустимый следующий task |
| Интерфейс и MCP | SN-031.W04.01/W04.05/W04.06, SN-031.W06 и текущие UI owners | Полный видимый цикл и проверки прав одинаковы в UI/MCP |

Точные изменения dependencies и interfaces.consumes требуют отдельной интеграции в canonical refinement после принятия дизайна. Обязательная проверка — объединённый граф явных dependencies и входных контрактов, не только depends_on. Core domains не должны зависеть обратно от полного SN-030 агрегата или cloud E2E. В этой публикации baseline, spec-index, task IDs, статусы и admission не изменены.

## 6. Дополнительная приёмка

Все AC-REVQ ниже — **NOT_RUN, требования к будущим испытаниям**. Они не прибавляются к числу пройденных тестов bootstrap.

| ID | Сценарий | Критерий |
| --- | --- | --- |
| AC-REVQ-01 | Публикация PR и submit | Одна связанная review-job с точным commit; writer сам не создаёт review session |
| AC-REVQ-02 | Crash до/после DB commit, до ответа | Повтор даёт тот же receipt/job, нет потери перехода |
| AC-REVQ-03 | PR создан, submit потерян | Reconciler сверяет один PR с intent; недостающий handoff явно BLOCKED, не новая публикация |
| AC-REVQ-04 | Дубли webhook/outbox и два scheduler claim | Один действующий stage owner; stale epoch не применяет результат |
| AC-REVQ-05 | Reviewer другого контекста | Подтверждены отдельные checkout/session/rights; автор не выдаёт себе accepted |
| AC-REVQ-06 | Source readonly, тестам нужны временные файлы | Проверки реально проходят в sandbox build workspace; Git-входы и privileged reporter не изменены |
| AC-REVQ-07 | Обязательный тест отсутствует/пропущен/упал | Нет ACCEPTED; code defect и environment BLOCKED классифицируются раздельно |
| AC-REVQ-08 | Поддельный PASS или неверный hash/runner | Неверное provenance rejected независимо от уверенности текста |
| AC-REVQ-09 | Новый HEAD во время review | Прежний результат исторический/superseded; новый commit получает собственную review revision |
| AC-REVQ-10 | Другая target base или изменённый merge composition | Применимые merge-candidate проверки обязательны; конфликтный контракт требует re-review |
| AC-REVQ-11 | CHANGES_REQUIRED | Один repair job, та же ветка/PR, IDs findings, новый commit и новое проверенное решение |
| AC-REVQ-12 | BLOCKED из-за среды при завершённом source assessment | Восстановление/проверки без ненужной повторной реализации и нового model review неизменного входа |
| AC-REVQ-13 | Повтор одного finding, исчерпанный budget | Дедупликация/hold, конечная escalation; review и repair не сбрасывают общий счёт |
| AC-REVQ-14 | Поздний verdict, pause/revoke/cancel | Следующая стадия не запускается вопреки текущей версии и правам |
| AC-REVQ-15 | ACCEPTED и разрешённый release | Следует merge/test/deploy/readback по контракту; соседний dependent не стартует преждевременно |
| AC-REVQ-16 | Неуспешный release или неизвестная запись GitHub | Reconciliation/совместимый rollback/hold, не ложный Done и не повтор записи вслепую |
| AC-REVQ-17 | UI и облачный ChatGPT MCP | Видны одинаковые job/verdict/reason/HEAD и реальные transitions; запрещены self-approval и чужой project |
| AC-REVQ-18 | Полный цикл и перезапуск платформы | implementation → review → repair → review → release → следующая допустимая task без ручного continue внутри делегации |

Фикстуры: два проекта, роли implementer/reviewer/verifier/operator, один заведомый баг и regression, дубликат события, потерянный ответ PR, stale commit/base, недоступная test dependency, истёкший lease при ещё живом worker, авторская попытка подмены test plan. DB-транзакции, trusted runner и минимум один end-to-end cycle должны быть проверены реально; mock-only PASS не закрывает соответствующие критерии.

## 7. Текущее состояние и область этой публикации

Этот документ — предложенная детализация проектного workflow. Он не утверждает, что установленный stock Symphony уже умеет такой local-tracker lifecycle. Ранее проверенные восемь native cases и пустая панель не являются испытанием review queue. Облачные reviews отдельных PR не заменяют будущий собственный роль-ориентированный scheduler.

Не выполнены: новая реализация, admission, reviewer/model session, server write, запуск Symphony, установка, merge/deploy. Не изменяются current GH-4/WORK-01 scope, его разрешение на один запуск и заблокированный перенос контроллера. Отказ этой операции не обходится публикацией данного документа. Прежние BOOT-P01/smoke/results/credentials и DF Assistant вне scope.

После принятия дизайна дополнение необходимо включить в versioned spec-index, уточнить SN-030 и совместные контракты других задач, проверить hashes/coverage/semantic DAG. До этого документ не является молчаливо активированным runtime policy и не разрешает следующую стадию существующей операции.

## 8. Основания и внешние источники

Внутренние источники прочитаны через GitHub на указанном main: docs/ROLE_CONTRACTS.md; SPECIFICATION.md §19 (ROUT/BUD), §21 (AUTO/QUAL), §23 (PLAN), §24 (DEP); TASKS.md SN-014/015/016/017/029/030. Предлагаемые REVQ и AC-REVQ не выдаются за уже существовавшие нормы этих файлов.

Внешние источники прочитаны 23.09.2026 и используются только для двух технических уточнений, не как подтверждение реализации Symphony Next:

- GitHub Docs, About protected branches: поддерживает отклонение устаревших approvals при изменении diff/merge base; настройка branch protection не заменяет наш собственный exact-input gate. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- AWS Prescriptive Guidance, Transactional outbox pattern: совместная запись данных и outbox, возможные повторы сообщений и необходимость идемпотентного consumer. Это шаблон надёжности, не предложение перенести Symphony Next в AWS.
 https://docs.aws.amazon.com/en_en/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html
