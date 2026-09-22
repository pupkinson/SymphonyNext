# Symphony Next — пакет ТЗ и задач v0.5

Цель: самостоятельно размещённый на Coolify многопроектный оркестратор автономной разработки, с Authentik, собственным трекером, несколькими агентами/моделями, мобильным управлением и ChatGPT/MCP. Существующий DF Assistant не меняется.

## Состав
- SPECIFICATION.md — полная согласованная редакция требований, включая голосовые решения об автономном release и диагностике.
- TASKS.md — 44 задачи с зависимостями, fixtures, assertions, evidence и границами.
- planning/backlog.json — канонический seed для импорта; dispatch/admission выключены.
- planning/traceability.json — владельцы266 requirement references и96 критериев приёмки.
- PROJECT_RULES.md, AGENTS.md, SKILLS_POLICY.md, docs/ROLE_CONTRACTS.md — правила и стадии исполнения.
- BOOTSTRAP_PLAN.md, bootstrap/INSTALLATION_STATE.md и bootstrap/STATUS.json — установка, фактические проверки и оставшиеся gates.
- bootstrap/WORKFLOW.github.example.md — неактивный пример pinned stock workflow; не копировать в live без проверки binding/auth/policy.
- schemas/backlog.schema.json — схема seed; MANIFEST.sha256 — целостность текстовых материалов.

## Фактическая точка продолжения
Owner installation под symphony-next UID/GID995 завершена; Git read, отдельный ChatGPT login и GitHub API read подтверждены датированными отчётами. Исходники и пакет опубликованы в pupkinson/SymphonyNext; PR #1 открыт. Последнее наблюдение службы — inactive/dead/disabled; новый worker не подтверждён как запущенный. Это не live health-check на момент будущего чтения.

Актуальные привязки и доказательства: bootstrap/RESOURCE_BINDINGS.json, STATUS.json и INSTALLATION_STATE.md. Исторические установочные формулировки в исходном TASKS.md описывают ранний снимок: создание repo/identity больше не является невыполненным owner шагом. Это не закрывает SN-001 или product tasks.

## Следующий пилот
bootstrap/PILOT.json и PILOT_TASK.md описывают BOOT-P01: один stock worker, один файл отчёта, реальный Git/tool/PR путь, без product implementation, без повторения отклонённых операций. Admission выключен. 44 product tasks, SPECIFICATION.md и их acceptance не пересматриваются.

## Проверки и выпуск
python3 -B -m unittest discover -s tests -p test_bootstrap_snapshot.py -v

Narrow snapshot tests не означают готовность runtime или полный GREEN; детали в docs/QA_AND_LIMITATIONS.md. MANIFEST.sha256 обновляется вместе с изменёнными материалами; исходный архив v0.5 остаётся неизменным историческим артефактом.

Существующая делегация scoped auto-release сохранена. Нужны exact checks/review и привязанные Coolify ресурсы, а не повторное согласование каждого обычного deploy. Значения секретов не передавать в Git/чат. tools/validate_package.py и прежний seed_publication.py не реализуются этой правкой. Существующий DF Assistant вне работ.
