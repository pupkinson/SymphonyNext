# Symphony Next — обязательные правила исполнения v0.5

## Канонические документы и решение владельца
Читать SPECIFICATION.md, planning/backlog.json, TASKS.md, policies/project-policy.json и bootstrap/STATUS.json. Последние голосовые решения включены в v0.5: автономный release в выделенном проекте разрешён, индивидуальное повторное согласование обычного deploy не требуется. Не возвращать blanket-запреты из v0.4. Подготовительные runtime scripts не являются готовым продуктом.

## Запрет пересечения с DF Assistant
Никаких изменений или чтения секретов DF Assistant, /home/programmer, старых Codex/Symphony config/workspaces, чужих GitHub/Coolify ресурсов. Новый bootstrap и целевой продукт имеют разные роли: bootstrap создаёт форк; новый продукт не обновляет работающего исполнителя незаметно.

## Исполнение задач
CURRENT STATE → TARGET → DELTA → CHANGE → VERIFY → ACCEPT. Fresh fetch → exact base/HEAD → свой worktree → RED/regression или проверяемый non-defect target → минимальная правка → targeted/broader checks → related commit/non-force push → PR → независимый review и trusted checks exact HEAD → delegated merge → штатный Coolify webhook → независимый runtime/functional readback. Не включать GitHub Actions.

Один writer в bootstrap. Planner предлагает DAG, но не выдаёт себе credentials и не запускает рой. Reviewer не правит проверяемый код и не подписывает собственную реализацию. Developer credentials не дают право писать trusted CI status или менять locked acceptance suite. Отсутствие CI signal — BLOCKED, не PASS.

## Доступы и команды
Не расширять root/sudo/Docker/socket/API scopes. Secrets не писать в Git, ответ модели, общий log, artifact, stdout или issue. Имена scopes берутся из accepted resource manifest. Capability refusals классифицировать; не повторять отказ через иной tool/credential/encoding/root/delegation. PUP-179 фиксирует конкретные отвергнутые записи валидатора и владельческой команды установки, а не объявляет все операции Symphony неисправными.

## Ошибки и остановка
Read-only transient network: всего три попытки (первая сразу, вторая через 10 секунд, третья через 60 секунд после предыдущей), затем stop. Auth/policy error не исправляется повторами. Для429 учитывать Retry-After и общий deadline. Unknown write сначала сверить; без signal — hold, не повтор mutation. Stop не требует подтверждения владельца и выполняется локально для своей process group, даже если уведомление недоступно. Code repair: максимум два цикла и одна смена профиля в пределах сохранённого бюджета.

## Готовность и release
Task accepted только по фактическим assertions/evidence. Milestone требует интеграционной проверки состава. Runtime readback включает exact commit/image/config, схему, health и функцию на контролируемых тестовых данных. Auto rollback — только на подтверждённый совместимый predecessor; несовместимость БД не разрешает destructive restore. Merge/deployment finished/running container не равны Done.

## Первый запуск
Seed admission выключен. Сначала отдельная OS/container identity, новый GitHub repo и scoped authorizations, policy/transport/Sandbox preflight. Установленные stock Symphony и Codex не дают target-продукту durable retry/approval/persistence. Stock pilot ограничивается временем и одной задачей, Restart=no; неизвестные blocked/retrying задачи перед повтором разбираются. Runtime production/actions вне подтверждённого нового project manifest недопустимы.
