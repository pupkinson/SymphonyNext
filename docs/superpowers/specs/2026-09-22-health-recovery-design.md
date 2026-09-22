# Symphony Next — автономное наблюдение и восстановление

Дополнение к ТЗ v0.5 · 22 сентября 2026 · архитектурный проект для review

База: `pupkinson/SymphonyNext`, main `30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8`, tree `ef76ae50ceff736e7f481797c40db97c6c52255c`.
Этот документ дополняет, но до принятия не заменяет SPECIFICATION.md, TASKS.md, planning/backlog.json и их манифест. Он не является кодом, установленной политикой, разрешением расширить права или отчётом о выполненных продуктовых тестах. Допуск BOOT-P01 и действующий DF Assistant не изменяются.

## 1. Основание и требуемый результат

Со слов владельца, 22.09.2026 разрыв связи Symphony → промежуточный узел Netcup → Linear привёл к тому, что задача DF Assistant не была подхвачена. Для обнаружения потребовались ручное чтение и анализ консольных логов. Причина и состояние того инцидента здесь независимо не проверялись; устранять или перезапускать DF Assistant этим документом не поручается.

В Symphony Next отсутствие ожидаемой работы должно обнаруживаться автоматически, даже когда процессы живы и HTTP отвечает 200. Система сама собирает диагностику, локализует затронутую зависимость, выполняет заранее разрешённое восстановление, сверяет результат и продолжает допустимую работу. Оператор нужен при исчерпании возможностей восстановления, неизвестном результате внешней операции, угрозе данным или изменении полномочий — не для обнаружения обычного сбоя.

Существующая база уже содержит REL-01–08, OBS-01–05, DIAG-01–10, SN-015, SN-021–024 и SN-041: durable state, наблюдаемость, конечные повторы, watchdog, остановку и reconciliation. Недостающая конкретизация: независимое наблюдение за всей цепочкой, отсутствие запуска при наличии спроса, контур разрешённых recovery-действий и проверяемое автоматическое возвращение к исполнению.

Новый native tracker не требует Linear/Netcup. Проверять нужно реальные зависимости конкретной установки, а не создавать новую обязательную связь с этими сервисами.

## 2. Архитектурное решение

Рассмотрены три подхода: только Docker/Coolify healthchecks; мониторинг внутри основного оркестратора; healthchecks плюс отдельный Health Supervisor и ограниченный Recovery Executor. Выбран третий: первые два не покрывают одновременно зависание scheduler, живой HTTP при остановленном polling и отказ самого control-процесса.

- **Компоненты платформы** публикуют измеримые сигналы здоровья, прогресса и причины ожидания. Они сохраняют локальные watchdog и штатное supervision процессов.
- **Health Supervisor** — отдельный контейнер, identity, ресурсный резерв и persistent volume. Он наблюдает, коррелирует инциденты, выбирает только заранее разрешённую процедуру и проверяет восстановление. Это не второй scheduler: он не выдаёт задания, lease или бюджет агентам.
- **Recovery Executor** — узкий доверенный исполнитель типизированных операций. Проверяет неизменяемую владельцем worker политику, stable resource IDs, полномочия, поколение, cooldown, бюджет вмешательств и отсутствие конкурирующего deployment. Ни модель, ни обычный runner не получают его credentials.
- **Coolify/Docker** обеспечивают контейнерный lifecycle и внешние сигналы. Источник с политикой `restart` и Supervisor не должны конкурировать: одна матрица определяет владельца каждого типа восстановления.
- **Внешний witness** на другом узле контролирует исчезновение всей установки. В основной поставке есть протокол heartbeat и готовый контейнер для второй площадки; платный SaaS не обязателен. Без независимой площадки полный отказ хоста не считается покрытым.

Supervisor должен работать при остановке control и недоступности основной PostgreSQL: отдельный локальный журнал инцидентов/recovery на его volume, bounded spool, собственный канал уведомления. Журнал не подменяет task database и не даёт права создавать claims без неё. Единственный владелец журнала; если его доступность/целостность не подтверждена, автоматические mutation запрещены.

## 3. Нормативные требования

**HEAL-01 — цель и охват.** Контролировать собственные control/API/UI, native tracker, scheduler, outbox, runner/agent process, MCP adapters, Git, модельные провайдеры, PostgreSQL, хранилище, резервные копии, IdP, прокси/TLS, уведомления, Coolify-интеграцию и Supervisor. Для каждого binding указать `owned`, `shared_external` или `optional`, набор проверок, зависимости, критичность и разрешённые действия. Мониторинг общего Authentik/Coolify не разрешает их перезапуск.

**HEAL-02 — свежесть и причинность.** Сигнал содержит component/project/instance ID, generation, observed_at, last_success_at, sequence/cursor, latency, error class, source и expiry. Слишком старый или недоступный сигнал — UNKNOWN, не HEALTHY и не доказанное отсутствие задач. Отдельно измерять DNS/TCP/TLS/API/auth только для настроенных разрешённых targets; не сканировать сеть. Проверка идёт по реальному маршруту и service identity интеграции, а не через привилегированный обходной путь.

**HEAL-03 — состояния.** Поддержать HEALTHY, DEGRADED, UNAVAILABLE, RECOVERING, QUARANTINED, PAUSED_BY_OPERATOR и UNKNOWN. Инцидент проходит detected → diagnosing → recovering → verifying → recovered либо held. `recovered` требует функционального readback, а не только живого PID. Хранить отдельные `service_recovered`, `task_resumed` и `notification_delivered`; они не эквивалентны.

**HEAL-04 — правильная семантика healthchecks.** Разделить process liveness, readiness локального UI/tracker, execution readiness каждого проекта и heartbeat независимого Supervisor. Публичный health endpoint минимален; детали только по ACL. Сбой Git/модели не должен убирать работающий tracker/UI из прокси. JSON `degraded` с HTTP200 не заменяет failure статус readiness там, где readiness действительно нарушена. Probe не делает restart, не меняет пользовательские данные, не вызывает платную модель. Healthcheck описан в Dockerfile/Compose вместе с реальным probe executable.

**HEAL-05 — контроль поступления задач.** Каждый poll/scan фиксирует attempt, success/error, длительность, полноту ответа и cursor/high-watermark. Ошибка либо частичная выборка не возвращается как пустой backlog. Heartbeat polling обновляется после фактического прохода, не независимым таймером. Durable reconciliation периодически сканирует источник задач и восстанавливает пропущенные события; webhook/внутренний notify — ускорение, не единственный источник истины. Некорректный cursor или regression sequence вызывает диагностику, не silent skip.

**HEAL-06 — контроль отсутствующего запуска и зависания.** Для admitted задачи хранить eligible_since и точную причину ожидания: dependencies, planned start, capacity, quota, budget, manual pause, approval, unavailable binding либо unknown. Если eligibility сохраняется и доступен слот, а lease/attempt не появился в пределах dispatch SLO, открыть `dispatch_stalled`. Нельзя подавлять тревогу только по самоотчёту зависшего scheduler: проверять durable очередь и реальные leases. Для активной стадии отдельно last_heartbeat, last_protocol_event, last_verified_progress, stage_deadline; поток логов не доказывает прогресс, молчание долгого теста не доказывает hang. Нужны stage-specific deadline и признаки завершения/ресурсного потребления.

**HEAL-07 — сквозной canary.** Детерминированное synthetic задание в отдельном test namespace проходит тот же admission/lease/dispatch/ack тракт, но завершается noop runner без LLM, Git write или внешнего business effect. У него низкий приоритет, квота и очистка только собственных fixtures. Canary не заменяет наблюдение production очереди и реальную приёмку модели/PR. Отсутствие задач и неработающий scheduler различаются; при занятой ёмкости canary показывает deferred, не healthy.

**HEAL-08 — независимый Supervisor.** Другой процесс/контейнер, собственные healthcheck, persistent volume, clock/deadline, лимиты, минимальные read credentials и отдельный транспорт оповещения. Он стартует без доступной основной БД, классифицирует её отказ и не зависит от рабочего endpoint scheduler. Должна сохраняться диагностика после смерти control. Его собственный отказ замечают контейнерный lifecycle и внешний witness. Взаимные бесконечные рестарты Supervisor/Executor запрещены.

**HEAL-09 — типизированное восстановление.** Допустимые операции: reconnect конкретного binding; recreate собственного connection pool/consumer; request_reconcile существующему scheduler; drain/interrupt конкретного attempt; restart точно указанного принадлежащего установке process/resource; redeploy принятого exact artifact; restore совместимого известного predecessor. Операция имеет prepare/preconditions, durable intent, idempotency key, execute, readback и postconditions. Shell, arbitrary URL, wildcard resource и произвольное исправление конфигурации отсутствуют. Каждому действию назначены минимальная область воздействия и критерий успеха.

**HEAL-10 — пределы восстановления и один владелец.** Счётчики переживают смерть control/Supervisor, redeploy и restart. Максимум одна mutation на resource generation; общий incident key объединяет проекты с общей причиной. Начальный профиль: до двух Supervisor restarts на компонент за 15 минут, до трёх за час; после лимита quarantine и alert. Нативные container/process restarts также учитываются в общей диагностике и не дают бесконечных циклов работы. На запуске компонента persistent gate проверяет ручной stop/quarantine до платных операций; если нативный runtime продолжает рестарты, компонент не делает model/внешние write и не объявляется восстановленным. Runtime restart ownership и возможность окончательно прекратить цикл проверяются на фактическом deployment backend.

**HEAL-11 — возобновление без дубликатов.** После восстановления сети не запускать задачу заново без проверки admission, spec/policy revision, budget, cancellation, действующих lease/epochs, незавершённых PR/deploy и локальных dirty outputs. Для не начатой задачи — один первый claim. Для оборванной — восстановление безопасной сессии либо новый attempt только после прекращения/ограждения старого и сохранения evidence. Старые approvals не переносятся. Не обещается exactly-once для сторонних систем; используется идемпотентность или authoritative readback. UNKNOWN эффект не лечится повтором.

**HEAL-12 — приоритет ручных и защитных остановок.** PAUSED_BY_OPERATOR, emergency stop, permission/auth failure, changed task scope, approval wait, budget exhaustion и неизвестный внешний эффект не снимаются health-recovery. Транспортный stopped_dependency может автоматически перейти к reconciliation после свежей стабильной проверки по принятой политике. Это не отменяет DIAG-03/08: остановленная попытка не оживает сама, уведомление или таймер не создают новый допуск.

**HEAL-13 — локализация и подавление каскадов.** Не перезапускать всех клиентов при отказе внешнего provider/IdP/сети. Сначала проверить причинную зависимость и текущий deployment; независимые проекты продолжают работу. Recovery lease сериализуется с release lock и operator action. Coolify Application restart нельзя выдавать за restart одного Compose-container: backend capability обязан явно указывать реальную гранулярность и blast radius. Если доступен только перезапуск всего bundle, он допустим лишь по отдельной заранее утверждённой bundle policy после оценки всех затронутых задач; иначе hold.

**HEAL-14 — полномочия и trust boundary.** Recovery service не получает root/privileged container/raw Docker socket. Работает через проверенный typed provisioner/ограниченный management adapter с fixed IDs и allowlist verbs. Наличие Coolify API не доказывает project-scoped права: фактическую гранулярность токена проверить. Если провайдер предоставляет более широкий token, он хранится только в изолированном доверенном Executor, не выдаётся Supervisor/агентам; Executor независимо проверяет allowlist и actor, не принимает arbitrary HTTP. Нет API mutation при недоступной policy/ledger. Операции общей инфраструктуры и host reboot запрещены по умолчанию.

**HEAL-15 — разные сбои.** Для transient read/connection сохранить три попытки и 10/60 секунд из DIAG-03; 429 — Retry-After/deadline; 401/403/schema/security mismatch — hold без restart storm. После исчерпания task retries монитор может продолжать дешёвые readiness checks с cooldown, без model calls и повторения неясных writes. Дорогая модель не является средством починки сети. Нестандартную программную неисправность оформлять задачей с воспроизведением: agent patch → tests/review → обычный webhook release, а не live-edit собственных правил восстановления.

**HEAL-16 — ресурсы, конфигурация и данные.** Disk/inodes/connection saturation/OOM, restart count, backup freshness/restore verification и истечение TLS/service credentials наблюдаются отдельно. Очистка только помеченных disposable caches по retention; dirty workspace, pending evidence, backup и пользовательские данные не удаляются. Увеличение квот, изменение ACL/firewall, автоматический restore с потерей новых данных и downgrade несовместимой схемы запрещены. При возврате известной версии одновременно проверить desired Git state, config generation и schema compatibility. Root cause UNKNOWN показывается честно.

**HEAL-17 — доказательства до вмешательства.** Перед restart по возможности собрать bounded sanitized logs, exit/OOM reason, component versions, timings, dependency graph, affected tasks и текущие процессы/leases. Ограничить сбор deadline: диагностика не задерживает срочную остановку. Локальный journal хранит причины, action ID, кто/какая policy разрешили, результат readback и ссылку на artifact. Model summaries необязательны, под бюджетом и вне управляющего контура; logs — недоверенные данные, не команды.

**HEAL-18 — телефон и уведомления.** Раздел «Состояние системы» и карточка инцидента доступны в PWA: где сбой, какие задачи затронуты, последняя успешная проверка, что восстановлено, причины hold, использованные попытки и следующее действие. Отображать свежесть каждой записи. По умолчанию уведомления: существенный сбой, исчерпание recovery, восстановление; дедупликация без спама на каждый retry. Отправка не зависит от основного scheduler/outbox; при его отказе Supervisor использует собственный spool и отдельно настроенный канал. `sent`, `delivered` и прочитано различаются. Нет связи — локальное сохранение и later delivery, без обещания доставки. Перед unattended acceptance требуется испытанный внешний канал; режим только local inbox явно обозначен ограниченным.

**HEAL-19 — переносимая поставка.** Supervisor, Executor, probes, policy defaults и журнал входят в поставку GitHub → Coolify → Docker. На свежем поддерживаемом сервере после подключения GitHub App, задания домена/секретов/identity и Deploy не нужны ручные systemd units, фиксированный UID995, копии файлов с 1c-db или root-сценарии наблюдения. Существующий Authentik подключается по конфигурации; secrets не возникают из репозитория. Templates подтверждают отсутствие циклического depends_on, чтобы Supervisor запускался при неготовом control/DB. Обновление control не уничтожает recovery ledger. Настройки runtime и внешнего witness доступны через документацию/мастер, а не скрытый host bootstrap.

**HEAL-20 — предел отказоустойчивости.** Сервис на полностью отказавшем хосте не может восстановить этот хост сам. Для обнаружения — witness на другом failure domain, проверяющий HTTPS и heartbeat с expiry; outage external target не является доказанным полным server crash. Автоматический power cycle требует отдельного защищённого инфраструктурного controller и явной политики, в MVP по умолчанию выключен. Базовый local self-hosted режим работоспособен без SaaS, но UI обязан показывать, что full-host coverage не настроено. Coolify на том же физическом узле не считается независимым witness.

## 4. Начальные измеримые параметры

Параметры ниже — предлагаемые настройки для целевой приёмки, не результаты текущей установки. Оператор может менять их versioned policy, агент не может.

| Параметр | Начальное значение / ограничение |
| --- | --- |
| Heartbeat runner | 5 секунд; потеря lease — существующий предел 30 секунд |
| Component scan | 15 секунд; probe timeout до 5 секунд; три последовательных отказа; обнаружение постоянного сбоя ≤60 секунд в проверенном capacity envelope |
| Stale poll success | 60 секунд либо provider-specific SLA; blocked/failed состояние вместо пустой очереди |
| Dispatch stuck | 60 секунд непрерывной eligibility при доступном слоте; scan ≤15 секунд, обнаружение ≤75 секунд от eligibility |
| Execution hang | Deadline/прогресс по стадии; одно общее «нет логов N секунд» запрещено |
| Canary | Один раз в 5 минут; без платных model calls; low priority; deferred при исчерпанном слоте |
| Connectivity recovery | Три попытки суммарно: t0, +10 секунд, +60 секунд после второй; далее stop и readiness-only мониторинг не чаще раза в минуту |
| Подтверждение восстановления | Два успешных целевых probe с интервалом 15 секунд плюс reconciliation; один HTTP200 недостаточен |
| Supervisor restarts | ≤2 на компонент за 15 минут и ≤3 за час; durable счётчики и quarantine |
| Первое оповещение | Попытка отправки ≤15 секунд после подтверждения инцидента; успешная доставка измеряется отдельно |
| External heartbeat | 30 секунд, expiry 120 секунд; вне основного failure domain |

Intervals используют monotonic clock; durable deadlines и UTC timestamp восстанавливаются без сброса бюджета. Скачок часов или устаревший sequence не даёт ложного healthy/второго lease. Resource ceilings Supervisor определяются нагрузочным тестом; они отдельны от квот агентных runner, чтобы они не вытесняли монитор.

## 5. Новые критерии приёмки

Все сценарии NOT_RUN. Они выполняются на изолированных fixture-ресурсах, не путём поломки работающего DF Assistant.

| ID | Реальный тест | Требуемый результат |
| --- | --- | --- |
| AC-97 | Разорвать/blackhole соединение настроенного tracker adapter через тестовый промежуточный узел | Обнаружение по реальному пути ≤60 секунд; ошибка не становится empty backlog; incident/evidence сохранены |
| AC-98 | Остановить polling loop, сохранив HTTP200 и живой процесс | Stale-poll incident, reconnect/restart только владельца loop; не ложный HEALTHY |
| AC-99 | Потерять webhook/внутреннее уведомление после сохранения задачи | Периодическая reconciliation находит задачу; один attempt, без ручного kick |
| AC-100 | Оставить admitted eligible задачу и свободный runner без claim | dispatch_stalled ≤75 секунд; очередь/leases сверены независимо от заявления scheduler |
| AC-101 | Pause, future scheduled task, blocked dependency, занятые слоты, approval или исчерпанный бюджет | Явная причина ожидания; нет ложного зависания, самовольного resume или перезапуска |
| AC-102 | Зависший agent, длинный здоровый тест, поток повторяющихся логов | Различение liveness/progress/deadline; bounded stop зависшего; длинный разрешённый тест не убит по тишине |
| AC-103 | Вернуть связь после трёх отказов | Стабильные probes, reconciliation, один допустимый запуск; старый stop/budget не сброшен |
| AC-104 | Убить control и отдельно отключить PostgreSQL | Supervisor продолжает работу/журнал/уведомление; новых claims без БД нет; recovery только разрешённого scope |
| AC-105 | Убить Supervisor во время recovery и поднять его снова | Журнал/счётчики сохранены, действие сначала reconciled; Executor не выполняет его повторно без readback |
| AC-106 | Потерять ответ после создания PR/deploy и вернуть старого runner | Найден прежний результат/owner; stale epoch rejected; второй внешний эффект не создаётся |
| AC-107 | Повторяющееся падение, redeploy между попытками | Durable restart budget, quarantine; нативный restart не разрешает новые LLM-вызовы; нет бесконечного recovery storm |
| AC-108 | 401/403, изменённая schema, ошибочный token; отдельно 429 | Auth/schema hold без перезапусков; rate limit следует Retry-After; права не расширены |
| AC-109 | OOM, заполнение диска/inodes и одновременная задача другого проекта | Локализация и остановка новых работ; допустимая cache cleanup; сохранены dirty/evidence/data; независимый проект не перезапущен |
| AC-110 | Race restart/deploy/manual stop; новый SHA и несовместимая схема | Один action owner, stale command rejected, no forced rollback/restore; protected stop не снимается |
| AC-111 | Canary и обычные healthchecks при заблокированном billing endpoint | Ни одного оплачиваемого запроса/внешнего write; canary использует реальный scheduler тракт, а не отдельный fake queue |
| AC-112 | Просроченные metrics, другой project ACL, недоступная primary DB | UNKNOWN/возраст в UI, нет cross-project утечек; локальный tracker не скрыт из-за отказа модели |
| AC-113 | Выключить весь тестовый хост | Внешний witness обнаруживает отсутствие heartbeat; без witness ограничение явно отражено; host reboot сам не делается |
| AC-114 | Отключить основную outbox и отдельно канал уведомления | Независимый Supervisor spool; попытки/неуспех видны; после восстановления одно доставленное уведомление без новых задач |
| AC-115 | Установка на другой поддерживаемый сервер через GitHub App/Compose/Deploy | Monitor/Executor/probes запускаются по поставке после задания необходимых параметров; без ручных root/systemd/UID995; реальный recovery тест проходит |
| AC-116 | Повторный deploy и restore backup в отдельном окружении | History/paused/quarantine/лимиты сохранены; все admission при restore закрыты; нет двух владельцев очереди |

## 6. Декомпозиция без перепроектирования существующего DAG

Это delta для review, не импорт в активную очередь. Существующие 44 задачи и AC-01–96 сохраняются. Предлагаются пять новых задач, итог после принятия — 49 задач и 116 AC; до принятия канонические счётчики v0.5 не меняются.

### SN-045 — Health contracts и обнаружение незапущенной работы
Зависимости: SN-004, SN-006, SN-014, SN-015, SN-016, SN-022.
Требования: HEAL-01–07. Результат: registry, раздельные health endpoints, freshness/cursors, backlog reconciliation, eligibility age и noop canary. Расширить SN-015 сигналами scan/claim/dispatch, не создавать scheduler заново.
Предлагаемые файлы: elixir/lib/symphony_control/health/{signals,registry,progress}.ex; elixir/test/symphony_control/health/progress_test.exs.
Проверки: AC-97–102, AC-111–112. Tests создают durable task без event, замораживают polling loop, оставляют здоровый HTTP; доказывают один claim и отсутствие ложных incident для paused/capacity blocked. Commands: `cd elixir && MIX_ENV=test mix test test/symphony_control/health/progress_test.exs`. Команды ещё не выполнялись.

### SN-046 — Независимый Supervisor, journal и внешний heartbeat
Зависимости: SN-045, SN-023, SN-024.
Требования: HEAL-08, HEAL-10, HEAL-20. Результат: отдельный процесс/container с persistent recovery journal, healthcheck и optional witness transport; ни task claims, ни credentials writer.
Предлагаемые файлы: supervisor/, deploy/supervisor.compose.yaml, supervisor/tests/recovery_journal_test.exs. Конкретный runtime supervisor закрепить ADR до реализации, не создавать новый технологический стек без необходимости.
Проверки: AC-104–105, AC-107, AC-113. Integration gate поднимает fixture, останавливает control/DB/Supervisor по очереди; проверяет journal, budget, owner и external expiry. Обязательный артефакт — machine-readable fault timeline с generation/exit/status; отсутствие test runtime означает BLOCKED, не PASS.

### SN-047 — Recovery Executor и безопасное автоматическое продолжение
Зависимости: SN-046, SN-021, SN-025, SN-032, SN-034.
Требования: HEAL-09, HEAL-11–16. Результат: versioned runbooks и typed capability поверх существующего provisioner/reconciler; locks, budgets, readback, retry/restore/rollback rules и автоматический resume только допустимого stopped_dependency.
Предлагаемые файлы: elixir/lib/symphony_control/recovery/{policy,actions,verifier}.ex; elixir/test/symphony_control/recovery/actions_test.exs; deploy/recovery-capabilities.json.
Проверки: AC-103, AC-106–110. Реальные controlled lost-ack, partial restart/deploy, worker resurrection, permission denial, чужой target и неподдерживаемая гранулярность Compose. Commands: `cd elixir && MIX_ENV=test mix test test/symphony_control/recovery/actions_test.exs`. Ни root/Docker socket, ни Coolify blanket token у worker.

### SN-048 — Мобильное состояние системы и независимые alerts
Зависимости: SN-045, SN-046, SN-047, SN-012, SN-035, SN-037.
Требования: HEAL-17–18. Результат: protected incident timeline/evidence/controls в PWA и отдельная доставка Supervisor без control outbox.
Предлагаемые файлы: elixir/lib/symphony_control_web/live/health_live.ex; elixir/test/symphony_control_web/live/health_live_test.exs; tests/e2e/health_mobile.spec.ts.
Проверки: AC-112, AC-114. Телефонный viewport; primary API down, channel down, reconnect, ACL revoke, одно уведомление и stale badge. Commands: `cd elixir && MIX_ENV=test mix test test/symphony_control_web/live/health_live_test.exs`; E2E harness фиксируется с существующим UI тестовым стеком, не имитируется текстовой проверкой.

### SN-049 — Переносимая Docker-поставка и приёмка recovery
Зависимости: SN-047, SN-048, SN-038, SN-039.
Требования: HEAL-19 и сквозная проверка HEAL-01–20. Результат: versioned Compose/health policies/мастер конфигурации плюс воспроизводимая fault suite на втором сервере. Повседневная установка не требует нынешних bootstrap сценариев.
Предлагаемые файлы: deploy/compose.yaml; docs/operations/health-recovery.md; tests/acceptance/health_recovery/; docs/acceptance/fresh-coolify-install.md.
Проверки: AC-115–116 и AC-97–114 интеграционно; артефакты содержат исходный SHA/image/config, фактические delays/attempts, provider call count, лог восстановления и результат на телефоне. Административные fault операции только на выделенных fixture IDs.

### Обновления существующих задач после принятия delta
SN-015: stale polling/queue/dispatch signals и loss-of-notify reconciliation.
SN-021–024: reuse reconciliation, diagnostic/retry contracts и local watchdog; переносимые счётчики и различение recovery процесса/задачи. Не реализовывать их второй раз.
SN-032–034: scoped restart/readback capabilities, подтверждённая гранулярность, recovery/release locking и совместимый rollback.
SN-035/037/041: health/incident UI, независимое оповещение, метрики и runbooks.
SN-039: включить recovery journal/policy/holds в backup/restore, а не только task DB.
SN-042: добавить зависимость SN-049 до приёмки unattended milestone. SN-043/044 наследуют эту зависимость через SN-042; не создавать цикл.
BOOT-P01 остаётся самостоятельным ограниченным пилотом и не ждёт реализации всего будущего self-healing продукта.

## 7. Публичные основания и границы

Сверено 22.09.2026. Это документация поставщиков, не проверка версии текущего Coolify владельца.

- Coolify healthchecks: https://coolify.io/docs/applications/configuration/health-checks — readiness, Traefik routing и healthcheck в Compose/Dockerfile. Это не готовый детектор остановившегося бизнес-процесса.
- Docker restart policies: https://docs.docker.com/engine/containers/start-containers-automatically/ — restart реагирует на exit/daemon lifecycle, сам unhealthy не равен restart. Владельцы перезапуска не должны конфликтовать.
- Coolify notifications: https://coolify.io/docs/core/notifications/events — события контейнеров, сервера, диска, backup и каналы. Не доказывает detection semantic task stall или доставку при отказе самого Coolify.
- Git-backed Compose: https://coolify.io/docs/applications/builds/docker-compose — versioned services, builds, volumes, checks и Git automation; не обещает автоматически минимальные API-права или атомарную замену отдельного сервиса.

Изменение требований оформляется отдельным review. Никаких рабочих рестартов, выдачи прав, настройки сигналов или прикладного fault injection в текущих DF Assistant/Symphony/Coolify этим документом не выполнено.
