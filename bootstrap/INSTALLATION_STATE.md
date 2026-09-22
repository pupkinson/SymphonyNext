# Состояние отдельной установки — установлен, рабочий пилот не запущен

Снимок фактов от 22.09.2026, не текущая проверка работающего сервера. Перед запуском нужен новый readback.

## Установка и доступы подтверждены
Владелец выполнил установщик 22.09.2026 в 14:24:05 UTC. Независимый readback в 14:25:46 UTC подтвердил пользователя symphony-next (UID/GID995, nologin, без дополнительных групп), root-owned runtime в /opt/symphony-next-bootstrap, отдельные /etc и /var/lib, совпадение 51 файла и unit. Symphony v0.0.3 и полный Codex0.155.1 сохранены, повторной установки не требуется.

Отчёт доступа в 15:13:21 UTC и его независимое чтение в 15:17:00 UTC: Git read PASS, отдельный ChatGPT login Codex без model turn, GitHub repo/issues GET PASS. Последнее наблюдение службы: inactive/dead/disabled, MainPID=0. Токен остаётся в root-only runtime.env; значение не включено в пакет.

Владелец опубликовал исходный main и docs/specification-v0.5. Initial HEAD 2e68d041c2de03450a4735c3a560e1a8c165f342, parent 1c0fb6c8e8ef9031a2c861e62af5f9e66cee39cb; PR #1 создан координатором. Это доказательство owner Git push и coordinator PR, не Git/API write внутри worker.

Coolify project o1l7c2rybr9r2asqipcbedps сообщён владельцем. Окружения, application/destination, Authentik client и webhook пока не проверены. Все bindings: RESOURCE_BINDINGS.json.

## Что осталось до первого пилота
Принятый source с правилами; точный issue и его sandbox/workspace/.git; effective App Server policy под UID995; GitHub API write и отзыв admission; выбранный разрешённый model profile, лимиты и bounded runtime. Текущий host workflow по последним данным остаётся disabled-memory, не этим Git-примером. Не создавать READY по факту обновления документов.

Операционный пилот BOOT-P01 определён отдельно в PILOT.json/PILOT_TASK.md, admission=false. Он не реализует общий валидатор и не закрывает SN-001. Product backlog не меняется.

## История не удалена
Первоначальные отказы PUP-179 и staging-состояние сохранены в Git на initial HEAD, в этих же STATUS.json/INSTALLATION_STATE.md. Последующие действия владельца не означают исправления платформенного отказа. tools/validate_package.py и seed_publication.py не реализуются и не переигрываются в этой правке. Независимые разрешённые операции не объявляются глобально запрещёнными.

Старый DF Assistant вне области работ. Runtime install, owner login, Git publication, worker model turn и acceptance продукта — разные контрольные точки.
