# Контракты стадий

## Planner
Вход: accepted spec revision, project policy, repository capabilities и data policy. Выход: versioned DAG с requirement coverage, leaf verification, dependencies, budgets и milestone composition. Не получает root или полномочия на самодопуск. Недостающие бизнес-решения задаёт до начала исполнения. Отсутствующие инфраструктурные signals записывает как UNKNOWN/BLOCKED, а не угадывает.

## Implementer
Вход: одна admitted leaf task, exact base/worktree, versioned context и разрешённые инструменты. Выход: минимальная правка, regression/verification, actual checks, related commit/PR и evidence. Не является своим reviewer или источником доверенного CI PASS. Не меняет policy/acceptance ради зелёного результата.

## Reviewer
Новый read-only контекст на exact candidate HEAD с accepted spec/task, diff и результатами. Проверяет исходные условия, отрицательные cases, безопасность, сохранение тестов и непредусмотренные изменения. Выход: typed findings/accepted-for-release либо needs-changes. Он не владеет секретами deploy и не меняет candidate branch.

## Release verifier
Проверяет независимые checks/review, scope/delegation/resource IDs и current PR HEAD. Выполняет разрешённый merge через bounded capability, наблюдает штатный webhook и отдельно устанавливает deployed identity/health/function. При нарушении — known-compatible rollback либо recovery hold. Human approval нужен для выхода из scope/прав, а не каждого обычного release.

## Важная граница bootstrap
Эти роли описывают будущую автоматизацию. Установленный stock runtime сам по себе не реализует новый broker, trusted CI, persistence или мобильную панель. Пилот не создаёт их наличием файла WORKFLOW.
