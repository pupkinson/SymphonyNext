# BOOT-P01 — первый проверяемый stock worker

Статус: PREPARED, admission=false. Это операционная проверка нового экземпляра, не реализация SN-001 и не переисполнение отклонённых инструментальных операций. Только GitHub issue с этим явным ID может использовать этот контракт вместо product backlog. Открытое issue без symphony-next-ready не допущено.

## Цель и единственный артефакт
Один worker штатного Symphony под symphony-next UID995 создаёт docs/pilots/BOOT-P01-report.md с фактической проверкой собственных инструментов, публикует один feature commit и один draft PR. Подтверждаем не обещание в prompt, а цепочку от выполнения модели до независимого GitHub readback. Не перепроектировать продукт, не составлять новый backlog, не исправлять валидатор.

## До допуска — работа координатора/оператора
Принять точный source с нашими правилами; проверить отсутствие старого worker и других допущенных issues; установить issue-specific WORKFLOW с точными workspace/.git roots; испытать effective sandbox, model profile и доступы под UID995. READY, служба и host WORKFLOW не меняются исполнителем этой задачи. Нет blanket ожидания закрытия PUP-179 для любой независимой операции, но ранее отвергнутые операции не входят в pilot.

## Работа исполнителя
1. Прочитать PROJECT_RULES, AGENTS, SPECIFICATION, RESOURCE_BINDINGS и этот контракт. Найти собственный workpad/ветку/PR; при незавершённой прежней попытке сообщить состояние, не сбрасывать работу. Через разрешённый Git-профиль получить fresh base. В workpad опубликовать ACCEPTED с issue, UID, session (если реально доступна), source HEAD, workspace и разрешённым единственным output path до изменений.
2. Реально выполнить `id -u`, `git rev-parse HEAD`, `git rev-parse --show-toplevel`, `git status --porcelain=v1` в своём workspace. Для Git использовать process-only профиль из workflow; коммиты с process-only user.name=SymphonyNext Agent и user.email=symphony-next@localhost. Не менять global config и не печатать env/auth/raw logs.
3. Через штатный github_api прочитать только собственный repo (ID1381693716) и это issue; опубликовать и прочитать один workpad comment. Не пробовать API чужого проекта для проверки отказа. Если инструмента/права нет, записать точный безопасный blocker и завершить без обхода.
4. Создать только `docs/pilots/BOOT-P01-report.md`. Обязательные разделы: Identity; Source; Commands; Results; Limits; Next action. Каждая проверка имеет command, UTC timestamp, реальный exit code/HTTP status и короткое sanitized observation. Отсутствующий факт обозначить UNKNOWN. Логин не объявлять model/tool acceptance; факт model turn сверяет координатор по runtime отдельно.
5. Выполнить `git diff --check`, проверить список изменённых файлов равным одному разрешённому пути. Не запускать product suite или отсутствующий общий валидатор для этого docs-only pilot. Сделать обычный commit/non-force push в `pilot/BOOT-P01`. Создать один draft PR в принятый base; при timeout сначала искать существующий PR по exact head/base, не создавать повтор.
6. В workpad записать exact HEAD/tree/base, PR и фактические результаты. Не вставлять будущий commit SHA внутрь самого коммита как будто он заранее известен. Удалить только свою admission label, прочитать issue повторно, оставить issue открытым и workspace сохранённым для review. Не делать merge/release из этой операционной проверки.

## Приёмка координатором
GitHub raw commit/compare подтверждают parent/base, только один output file, exact head/tree, один PR. Workpad write/read выполнен именно server token через worker, не ChatGPT connector. Runtime показывает фактическую модельную сессию и завершение единственного исполнителя; label отсутствует, чужие ресурсы не затронуты. Полная цепочка не объявляется PASS только по отчёту модели. Результат не закрывает SN-001, product suite или весь bootstrap.

## Сбои и остановка
Read-only transient operations: три попытки максимум с ожиданиями10/60 секунд; auth/policy ошибка без повторов. Неопределённый write сначала сверить; при отсутствии readback остановиться. Не удалять работу. Если снять label нельзя, завершить свою сессию и указать blocker; координатор проверяет остановку, а установленный RuntimeMaxSec ограничивает процесс. Это не доказательство durable recovery upstream. Никаких новых агентов, root/sudo/Docker, скачивания skills, изменения секретов, старого DF, Coolify deploy или расширения policy.

Scoped auto-deploy всего нового проекта остаётся разрешённым при выполненных gates; отсутствие deploy в этой конкретной диагностической задаче не отменяет это решение.
