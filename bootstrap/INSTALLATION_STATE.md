# Состояние отдельной установки — BLOCKED перед owner adoption

## Подтверждено
На 1c-db установлен самостоятельный набор pinned runtime bytes: Symphony v0.0.3 и полный Codex0.155.1. Он не использует HOME или авторизацию текущего DF Assistant. Native CLI и запуск с пустым memory tracker проверены; HTTP200, ноль workers; probe штатно остановился, порт4327 закрылся.

Подготовлен и протестирован offline installer с фиксированными targets для нового системного пользователя symphony-next, /opt/symphony-next-bootstrap, /etc/symphony-next-bootstrap, /var/lib/symphony-next-bootstrap и отдельного systemd unit. Он не должен выдавать sudo/Docker, создавать READY или запускать/включать службу. Его privileged execution в этой итерации не выполнялся.

## Текущая блокировка
Запись владельческой команды установки через RDC была отклонена защитой платформы. Это отдельный наблюдаемый отказ; его причина не установлена. Команда не распространяется в этом пакете, и отклонённая операция не передаётся другому агенту, root, encoding или инструменту для обхода. Требуется поддерживаемое разрешение/восстановление именно этой операции, а не повторное согласование бизнес-цели.

Отдельно отклонена запись нового серверного валидатора пакета; implementation отсутствует, RED tests остаются незавершёнными. Оба события добавлены к PUP-179.

## Последующая приёмка после снятия технического ограничения
Независимо проверить новую OS identity, root-owned runtime/config, отсутствующие sudo/Docker supplementary groups, limits и закрытый admission. Проверить sandbox/egress без чтения DF secrets, затем отдельно provision новый GitHub repo/scoped authorizations и model login. Обязательны actual Git/PR/model-turn/readback; native empty smoke их не заменяет.

Установка bytes в engineering staging не называется готовой изолированной системной службой. Установленные ранее артефакты сохранены, DF не изменён, новый autonomous worker не запущен.
