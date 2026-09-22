# Проверка пакета и граница доказательств

22.09.2026: независимая read-only проверка документов стандартными jsonschema и graphlib подтвердила JSON schema, уникальность44 task IDs, отсутствие циклов/неизвестных dependencies, соответствие digest полного ТЗ и seed, покрытие266 requirement references и96 AC. Admission выключен для всех seed tasks. Проверка относится к документам, не к целевому продукту.

Серверный tools/validate_package.py отсутствует: его запись отклонена платформой (PUP-179). 12 заранее созданных RED-тестов остаются незавершённой работой. Код этой отклонённой реализации не переносился другим инструментом и не включён в архив как готовый validator. Команды валидатора в карточках — будущий acceptance target, не доступная команда этого пакета.

41 проверка preflight/runtime-installer/owner-installer выполнена отдельно и прошла. Эти результаты не обозначают зелёный полный suite после добавления RED-тестов валидатора. Native Symphony smoke поднял пустой memory tracker на4327, HTTP200 и0 workers; процесс завершился штатно, порт закрыт. Никаких auth credentials или model calls этот smoke не использовал.

Не подтверждены: privileged owner adoption, новый GitHub repository, scoped credentials, paid model turn, feature push/PR, non-Actions CI, Coolify/Authentik provisioning, production acceptance. Exact resources/account capabilities устанавливаются перед запуском; неизвестные IDs не подставлены из DF Assistant.

Готовый документ не даёт агенту доступ к root/Docker/API. Физическая установка bytes отдельно от запуска с новыми credentials и отдельно от приёмки всего продукта. Существующий DF не изменялся; недоступность его старого loopback endpoint не доказывает, что весь сервис остановлен.

Systemd static verify с фактически установленным staging ExecStart завершился exit0; службу команда не запускала. Диагностика содержала предупреждения о чужих host units (netplan permissions/snapd RestartMode), не об этом candidate. Проверка под конечной identity после owner adoption остаётся отдельной.

Позднее также отклонена запись owner installation command через RDC. Исполняемая команда удалена из доставляемого пакета; служба под новой identity не установлена и не запущена. Подготовленный ранее installer сохраняется на сервере, но не выдаётся как обход отказа.
