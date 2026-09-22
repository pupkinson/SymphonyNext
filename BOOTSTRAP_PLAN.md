# Symphony Next — продолжение установленного bootstrap

## Точка продолжения
Установка под отдельным symphony-next UID/GID995 завершена владельцем; Git/ChatGPT login/API read подтверждены отчётом доступа 15:13:21 UTC от 22.09.2026. Исходники и пакет опубликованы, PR #1 открыт. Полный снимок с датами: bootstrap/STATUS.json и bootstrap/RESOURCE_BINDINGS.json. Не переустанавливать runtime и не перевыпускать доступы.

Локальный clone владельца: /var/lib/symphony-next-bootstrap/manual-preparation-v0.5/repository. Он может отставать от PR после coordinator commit: перед работой обычный fetch, проверка dirty state и точного HEAD; без reset/force/повторного импорта. Bootstrap worktree RDC и файлы прежних отказов не являются рабочим каталогом будущего агента.

## Оставшаяся последовательность
1. Проверить исправленный PR #1 на точном HEAD. Narrow snapshot tests и manifest не подменяют независимый review или полный валидатор пакета. Разрешённый merge выполняется после применимых trusted checks, без нового per-deploy согласования.
2. BOOT-P01 — отдельный операционный pilot, не новая реализация SN-001: его единственный артефакт docs/pilots/BOOT-P01-report.md, ограничения и реальные проверки заданы в bootstrap/PILOT_TASK.md. Создание issue без admission label не запускает работу.
3. Под UID995 проверить effective App Server/sandbox и точные writable roots рабочего checkout и .git, Git/network/API операции, identity, отсутствие старого worker и достаточные лимиты. Не читать старый DF HOME/credentials. Нужные права уже provisioned; конкретный отказ не обходить другой identity или ослаблением sandbox.
4. Подготовить точный host WORKFLOW для фактического GitHub issue. Пример в Git — не установленная конфигурация. Шаблон клонирует main; он допустим после появления принятых правил на main. Для другого source ref требуется отдельный exact candidate. Ни при каких условиях не клонировать upstream main без наших правил как рабочую базу.
5. После precheck допустить только один issue, проверить отсутствие других issues с symphony-next-ready, выполнить один bounded запуск существующей новой службы. Один writer, без субагентов, RuntimeMaxSec=1800 и Restart=no. Нет слепых перезапусков.
6. Наблюдать фактический model turn, commit, non-force push, один draft PR и снятие admission. Сопоставить точные SHA и реальную проверку инструмента с отчётом. При блокировке — локальная остановка и sanitized evidence; не продолжать другую задачу.

## Границы зависимостей
SN-001 и прежний package-validator blocker остаются незавершёнными. BOOT-P01 лишь даёт независимое evidence transport/Git/model; не включает tools/validate_package.py, seed_publication.py, host installers или отклонённое чтение upstream client. JSON backlog не читается stock tracker автоматически. После приёмки собственного трекера — один явный cutover, не две очереди одновременно.

Coolify project создан владельцем, но live IDs ресурсов/домена/IdP ещё нужны перед product release. Их отсутствие не требует новых ключей для Git-пилота. Штатный будущий выпуск: PR → trusted exact checks и independent review → scoped merge → Coolify webhook → exact runtime/functional readback. Rollback только на совместимый predecessor; прежняя делегация сохранена.
