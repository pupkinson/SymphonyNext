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

## Что сделано сейчас
Отдельный pinned runtime уже физически установлен в engineering staging на1c-db и проверен нативным smoke. Системная identity/служба требуют owner adoption, разработка не запущена. Сами будущие UI/tracker/runners не реализованы.

## Запуск
Начать с BOOTSTRAP_PLAN.md. Обычный deploy внутри нового project delegation уже разрешён, повторно согласовывать его не нужно. GitHub/Authentik/Coolify/model secrets не передаются в чат или Git.

## Блокировки
PUP-250: create-repository capability; PUP-179: конкретная отклонённая запись серверного валидатора; PUP-37: отсутствующие в текущей беседе Coolify actions. Не обходить отказ другой identity/tool/delegation. Эти записи относятся к управлению интеграциями, а не создают обязательную зависимость нового продукта от Linear.

Проверку документов не путать с product acceptance. Все96 AC — требования к будущему испытанию; сейчас они NOT_RUN. Подробности в docs/QA_AND_LIMITATIONS.md.
