# Symphony Next — установка и запуск отдельного экземпляра

## Фактическое состояние
На 1c-db проверен owner preflight пользователя programmer. Его старое окружение не копировалось. Под rdc в отдельный каталог загружены и проверены official Symphony v0.0.3 и полный Codex0.155.1. CLI0.155.1 и native empty-memory HTTP smoke прошли; probe остановлен, порт4327 закрыт. Это не авторизованный model turn и не готовый целевой продукт.

## Уже подготовленные пути
- Engineering repo: /srv/rdc-workspace/repos/symphony-next-bootstrap.
- Isolated worktree: /srv/rdc-workspace/worktrees/symphony-next-bootstrap-20260922.
- Runtime: /srv/rdc-workspace/installations/symphony-next-bootstrap/runtime.
- Runtime manifest: /srv/rdc-workspace/installations/symphony-next-bootstrap/runtime-manifest.json.
- Offline owner installer: /srv/rdc-workspace/worktrees/symphony-next-bootstrap-20260922/owner_install.py.

## Текущий шаг установки заблокирован
После подготовки и тестов запись owner-команды через RDC была отклонена защитой платформы. Привилегированная установка ещё не выполнялась. Команда не включена в пакет и не переотправляется для обхода; подробности в bootstrap/INSTALLATION_STATE.md. Текущий отказ не доказывает неисправность stock Symphony и не отменяет согласованный release. Нужно поддерживаемое восстановление конкретной операции, после которого выполняется bounded owner adoption и независимый readback.

## Условия до оплачиваемого пилота
1. Authoritative readback installation-status.json и unit/config; отдельная identity, HOME/volumes/limits, проверка отсутствия доступа к DF. Реальную сетевую изоляцию и sandbox проверяют до выдачи READY marker.
2. Новый private GitHub repository с сохранённой историей/лицензией upstream, GitHub Actions disabled, отдельная repo-scoped SSH identity и отдельный repo-scoped tracker access. Авторизация Codex выполняется отдельно под новой identity; старый auth.json не копируется. Токены не отправлять в этот чат.
3. GitHub capability create-repository отсутствует в текущем connector (PUP-250): использовать поддерживаемую ограниченную capability после её появления либо штатное однократное создание владельцем. Не заимствовать широкий постоянный PAT.
4. Coolify/Authentik resource IDs, destination, network и bounded release/readback actions получают отдельным authoritative preflight. В этой беседе Coolify actions отсутствуют; это не означает, что сервер Coolify неисправен. Площадку/IdP заново не выбираем.
5. Подтвердить весь app-server contract на новом UID, реальные Git fetch/feature push/PR, native tracker auth и test status. Никакой «установлено = готово».
6. Устранить точный platform source-write refusal PUP-179 поддерживаемым способом. Не поручать новому агенту обходить отказ записи tools/validate_package.py. Seed SN-001 остаётся blocked/admission=false до снятия его собственных blockers; это не глобальный запрет независимых действий.
7. В отдельном GitHub repo материализовать одну допущенную leaf issue с уникальной label; прочитать её обратно и убедиться, что нет других admitted issues. JSON seed не читается stock adapter автоматически. В label не попадают старые PUP/DF задачи.
8. На exact рабочем workflow заменить disabled memory tracker реальным GitHub adapter. Запуск ограничить одной задачей/одним writer/30мин, Restart=no. Observe actual model turn and result; no blind restart of blocked/unknown attempt.

## Источник против собственного трекера
Для bootstrap временно используется штатный GitHub Issues adapter на pinned upstream. Target-продукт хранит задачи у себя и не требует Linear. После готовности native tracker: закрыть bootstrap intake, дождаться/остановить своего worker с readback, импортировать backlog с mapping, сверить PR/внешние эффекты, переключить одного владельца очереди. Остановленную rollback-копию bootstrap не удалять.

## Автодеплой
План не вводит повторных подтверждений каждого деплоя. После привязки нового project manifest и доверенных проверок: PR → exact checks/review → scoped merge → GitHub push/webhook → Coolify deploy → exact runtime/functional acceptance. Rollback только при доказанной совместимости схемы/данных. Отсутствующие права или CI/readback не заменяются arbitrary root/manual deploy.
