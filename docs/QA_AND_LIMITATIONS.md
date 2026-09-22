# Проверки и границы доказательств — binding follow-up

## Унаследованные результаты
Первоначальный пакет v0.5 был проверен на 44 task IDs, 266 requirement references, 96 AC и отсутствие циклов. Это historical document validation, не product acceptance. Все product AC остаются NOT_RUN. Исходный пакет и манифест доступны на commit 2e68d041c2de03450a4735c3a560e1a8c165f342.

41 targeted preflight/installer test и native empty-memory smoke были выполнены ранее. Owner installation и доступы позже подтверждены датированными отчётами в bootstrap/STATUS.json. Эти шаги не повторялись при обновлении bindings и не объявляются новым model turn.

## Узкие проверки этой правки
Команда: python3 -B -m unittest discover -s tests -p test_bootstrap_snapshot.py -v

Она проверяет только статические значения repo/token/profile, синтаксис clone hook без его исполнения, датированный installation snapshot, границы OWNER_REPORTED для Coolify, неизменность лимитов и отсутствие admission/секретов. Это отдельные regression tests документации, не реализация ранее отклонённого tools/validate_package.py и не замена его acceptance.

Полные YAML parse, bash -n, JSON parse и sha256sum выполняются дополнительно в локальной среде координатора; это не проверка stock parser, GitHub write или sandbox на 1c-db. Перед публикацией сравниваются изменённые файлы и неизменный SPECIFICATION.md. Результат конкретного запуска/HEAD записывается в PR, не предполагается из наличия команды.

## Не завершено
12 RED-тестов исторического серверного валидатора не устранены этой правкой. Полный suite не объявляется GREEN. Нужны independent review/trusted checks, effective service sandbox, фактический worker model turn/Git/API write, готовый runtime workflow и первый результат BOOT-P01.

Coolify project и отключение Actions — сведения владельца; live resource/IdP/webhook acceptance не получены. Поздние owner install/publication не являются доказательством восстановления первоначальных отказов PUP-179. Их записи в истории сохраняются.

Приложение, native tracker и runners целевого продукта не созданы этой правкой. DF Assistant, systemd, READY, секреты, GitHub Actions и production не изменялись.
