# Review queue — план реализации R1

> Для исполнителей: выполнять последовательно через superpowers:executing-plans. Одна допущенная задача на writer; независимый reviewer получает новую сессию. Этот план не запускает агентов.

**Цель:** implementation → verification → review → repair/release → следующая допустимая задача без ручного «продолжай» внутри действующей делегации.

**Архитектура:** одна БД и один scheduler Symphony. Реализация сдаёт CandidateSubmission, сервер создаёт review obligation, а verdict применяет детерминированная state machine. Доверенное выполнение тестов отделено от reviewer и от издателя результатов.

**Стек:** существующие Elixir/Phoenix/Ecto/PostgreSQL, runner protocol и MCP gateway. Версии и новые зависимости фиксируются только после проверки текущего accepted source; отдельный брокер и новый scheduler не добавляются.

**ТЗ:** `docs/superpowers/specs/2026-09-23-review-queue-design.md` — REVQ-01–22, AC-REVQ-01–18. Пользователь подтвердил приложенный документ 23.09.2026. Его исходный SHA256: `3743a5e11488c8e9f4814ac1612b9df13f152aa3eacdd308d4174103e96231f5`. Репозиторная копия отличается только переносом строки перед последним URL; её SHA256: `75606fb28b78816c13a99998c8ff92ca558f54863a3f238f496e8959eb392cb1`. Слова и требования не изменены. Заголовок о проекте документа сохранён как история; подтверждение зафиксировано здесь.

**База планирования:** `c3c8bce82d148c3e558481644eb5d0a4072fdb6f`. Перед каждой реализацией заново сверить main, собственный task scope и принятые зависимости.

## Общие ограничения

- Ни одна карточка ниже не является допуском: planned, admitted=false, implementation=NOT_IMPLEMENTED, acceptance=NOT_RUN.
- Сохранить baseline, обязательные тесты, full MCP parity и запрет GitHub Actions. Исполнитель не публикует доверенный PASS.
- Новая версия кода требует нового source assessment; старый результат сохраняется исторически. Восстановленная среда при неизменном входе не требует повторного model review.
- Read-only checkout не означает read-only build workspace: тесты получают одноразовые writable scratch/DB, но не credential издателя и не production secrets.
- Общий бюджет исходной задачи включает review/repair; максимум два repair cycles и одна разрешённая смена профиля, если effective policy не строже.
- Продуктовое разрешение ordinary scoped release сохраняется. Текущий WORK-01/GH-4 заканчивается draft PR; этот план не добавляет к нему автоматический merge, review session или следующего агента.
- Ветки, серверные сценарии, прежние BOOT-P01 и smoke не изменяются данным планом. Не обходить отказы другим инструментом или root.

## Организация работ и зависимости

RQ01–RQ05 — последовательные пакеты существующей SN-030, а не новые top-level задачи. Их entry gate сохраняет принятые зависимости SN-003, SN-017 и SN-029. Они добавляют поведение к ранее реализованным SN-014/015, но не заставляют эти базовые задачи ждать SN-030.

RQ06 принадлежит интеграции SN-034, RQ07 — SN-031.W04.05 с W04.01/W04.06, RQ08 — финальной SN-042. SN-030 завершается своим core review contract после RQ05; она не ждёт release/MCP/E2E, которые сами зависят от неё. Финальные milestones обязаны дождаться полного цикла RQ08. Это предотвращает обратный цикл.

В этом PR не переписываются canonical task_overrides, interfaces.consumes или spec-index. После review плана один интеграционный commit должен внести paired explicit overrides с точными expected baseline values и ссылками на этот документ. До этого существующий importer не должен считать пакеты допущенными или реализованными. Такая интеграция проверяет объединённый граф depends_on + consumes, а не только строки зависимостей.

## Общие контракты

`Quality.submit_candidate(actor, command)` возвращает `{:ok, receipt}` или typed error; command содержит task/attempt, PR/repo, immutable source/evidence keys, expected_version и idempotency_key. Actor берётся из аутентифицированного канала, а не из payload.

`Quality.apply_assessment(actor, assessment)` сохраняет отдельный SourceAssessment. `Quality.record_verification(actor, evidence)` принимает только проверенное происхождение runner. `Quality.decide(input_key)` детерминированно объединяет оба вида доказательств и возвращает ACCEPTED / CHANGES_REQUIRED / BLOCKED.

`Quality.apply_transition(actor, decision_id, expected_version)` выполняет проверку epoch, current inputs, паузы, бюджета и делегации; атомарно сохраняет решение, следующий job и outbox. Повтор команды возвращает прежний receipt. Рекомендация модели не является командой перехода.

`Quality.reconcile_publication(publication_intent_id)` читает внешний результат без повторного POST. `Quality.resume_blocked(actor, job_id, expected_version)` продолжает первую непринятую стадию после проверки причины и владения. These names are implementation contracts, not installed tools.

## RQ01 — передача результата и долговечная obligation

**Owner:** SN-030. **Входы:** accepted SN-003/SN-017/SN-029 и общие команды SN-014. **Выходы:** submit_candidate, reconcile_publication, CandidateSubmission, ReviewJob, outbox.

**Файлы:** `elixir/lib/symphony_control/quality.ex`, `elixir/lib/symphony_control/quality/submission.ex`, `elixir/lib/symphony_control/quality/outbox.ex`; отдельная Ecto migration в `elixir/priv/repo/migrations`; тест `elixir/test/symphony_control/quality/submission_test.exs`.

- [ ] RED: в настоящей PostgreSQL две конкурентные команды одного key должны вернуть один delivery_id/review_job_id. Другой payload при том же key — conflict. Crash после commit до ответа не теряет обязательство.
- [ ] Реализовать транзакцию submission + job/obligation + outbox; UNIQUE по immutable input key и ограниченному command key. Не держать транзакцию открытой во время GitHub HTTP: сохранить intent, затем readback и compare-and-set локальной версии.
- [ ] Проверить PR создан / submit потерян, неверный repo, неполный handoff, повтор webhook и отказ БД. Ни один случай не создаёт повторный PR или ложный ACCEPTED.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/submission_test.exs --trace`; затем scope diff и один related commit.

## RQ02 — единая очередь и применимость версии

**Owner:** SN-030. **Вход:** RQ01 и scheduler/leases SN-015. **Выход:** claim role job, superseded revision, scheduling priority без второго scheduler.

**Файлы:** `elixir/lib/symphony_control/scheduler.ex`, `elixir/lib/symphony_control/quality/queue.ex`, `elixir/lib/symphony_control/quality/input_key.ex`; тест `elixir/test/symphony_control/quality/queue_test.exs`.

- [ ] RED: два claim дают один owner; writer ещё жив — reviewer не запущен; pause/revoke между claim и dispatch запрещает запуск; lease expiry не доказывает смерть процесса.
- [ ] Реализовать claim/fencing через существующий scheduler. Review предпочитается новой обычной реализации в проекте; emergency и fairness между проектами сохраняются.
- [ ] Проверить новый HEAD/target base, позднее решение, повтор outbox и запрет зависимости review от Done родительской задачи. Repair создаёт следующую revision, а не цикл бизнес-DAG.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/queue_test.exs --trace`; scope diff; commit.

## RQ03 — независимый reviewer и доверенные тесты

**Owner:** SN-030. **Вход:** RQ02 и SN-016/017. **Выход:** separate source session, immutable checkout, VerificationEvidence и независимое происхождение его публикации.

**Файлы:** `elixir/lib/symphony_control/quality/reviewer.ex`, `elixir/lib/symphony_control/quality/verification.ex`, `ci/acceptance-policy.json`, `ci/review-verifier.sh`, `schemas/evidence.schema.json`; тест `elixir/test/symphony_control/quality/verification_test.exs`.

- [ ] RED: writer публикует PASS или runner с неверным source/suite/image — rejected. Source checkout readonly, тест создаёт scratch/временную БД — успешно, Git-вход неизменён.
- [ ] Реализовать детерминированные проверки до paid review; ограничить runner сеть/файлы/тайм-аут. Credential издателя не передавать исполняемому PR-коду. Публиковать только проверенный результат exact source.
- [ ] Проверить FAIL, NOT_RUN, ERROR, SKIPPED и policy-backed NOT_APPLICABLE; отсутствие regression направляет repair, неисправная среда — BLOCKED. Новый reviewer не получает скрытую историю implementer, push/merge/deploy права или собственный выбор authority.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/verification_test.exs --trace`; реальные runner/isolation assertions отдельно от unit fixtures; commit.

## RQ04 — структурированное решение и защищённый переход

**Owner:** SN-030. **Вход:** RQ03. **Выход:** apply_assessment, record_verification, decide, apply_transition и TransitionReceipt.

**Файлы:** `elixir/lib/symphony_control/quality/assessment.ex`, `elixir/lib/symphony_control/quality/decision.ex`, `elixir/lib/symphony_control/quality/transition.ex`, `schemas/review-result.schema.json`; тест `elixir/test/symphony_control/quality/decision_test.exs`.

- [ ] RED: чистый source assessment + NOT_RUN обязательного теста даёт BLOCKED; свободный текст/emoji/exit0 не даёт ACCEPTED; stale input или epoch не создаёт следующего job.
- [ ] Реализовать отдельные SourceAssessment и VerificationEvidence, итоговую тройку verdict и атомарный compare-and-set переход с outbox. Все findings имеют устойчивые IDs и проверяемые evidence.
- [ ] Проверить clean assessment + позднее достоверное PASS неизменного входа: один завершённый review, без второго model call. Изменение spec/policy/coverage проверяет применимость заново. Recommended action не исполняется как произвольная команда.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/decision_test.exs --trace`; commit.

## RQ05 — repair, BLOCKED и пределы циклов

**Owner:** SN-030. **Вход:** RQ04, existing budget/recovery domains. **Выход:** repair job, appeal, classified block/resume с общим бюджетом.

**Файлы:** `elixir/lib/symphony_control/quality/repair.ex`, `elixir/lib/symphony_control/quality/blocked.ex`, `elixir/lib/symphony_control/quality/appeal.ex`; тест `elixir/test/symphony_control/quality/repair_test.exs`.

- [ ] RED: повтор findings создаёт ровно один repair job текущей delivery. Новый commit получает новое review; замечание без нового evidence и exhausted budget приводит к hold, не расходной петле.
- [ ] Реализовать группировку блокеров, сохранение ответов автора по finding ID, прежний PR/branch и агрегированный task budget. Scope expansion — предложение, не самодопуск.
- [ ] Проверить environment/auth/quota/unknown-outcome отдельно. Resume не повторяет уже принятую реализацию. Appeal не удаляет finding и не перебирает модели до согласия.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/repair_test.exs --trace`; core SN-030 не объявлять готовым без RQ01–RQ05.

## RQ06 — выпуск и разблокировка зависимой задачи

**Owner:** SN-034. **Вход:** принятый core SN-030/RQ05 и собственные prerequisites SN-034. **Выход:** release eligibility и dependent evidence gate.

**Файлы:** `elixir/lib/symphony_control/releases.ex`, `elixir/lib/symphony_control/quality/release_gate.ex`; тест `elixir/test/symphony_control/quality/release_gate_test.exs`.

- [ ] RED: ACCEPTED не разблокирует dependent, требующий deployed functional evidence. Изменившийся target branch требует merge-candidate checks. Потерянный merge response не порождает второй write.
- [ ] Реализовать независимую release identity, expected HEAD, сохранённый exact manifest, webhook correlation и readback. Existing ordinary scoped delegation не требует нового human approval каждого deploy.
- [ ] Проверить docs/no-deploy applicability, failed deploy, совместимый rollback и запрещённый destructive restore. Source review сохраняется даже при неуспешном release; task Done не присваивается.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/quality/release_gate_test.exs --trace`; native release acceptance — отдельная реально выполненная fixture, не unit mock.

## RQ07 — единая история в UI и облачном ChatGPT

**Owner:** SN-031.W04.05; координация W04.01/W04.06. **Вход:** RQ05/RQ06 и собственные accepted MCP prerequisites. **Выход:** capability registry, UI↔MCP parity review operations.

**Файлы:** `elixir/lib/symphony_control_web/live/review_queue_live.ex`, `elixir/lib/symphony_control/mcp/tools/quality.ex`; тест `elixir/test/symphony_control/mcp/review_queue_parity_test.exs`.

- [ ] RED: reader не отправляет verdict, author не становится своим reviewer; другой project скрыт. UI/MCP читают одни job IDs, exact HEAD, три результата и причину ожидания.
- [ ] Реализовать read/submit/request-review/findings/appeal/pause/resume поверх общей domain logic, без второго трекера и без универсального privileged shell.
- [ ] Проверить реальный wire-каталог и mapping, concurrent version conflict, revoke между preview/commit. Пакет плагина описывает flow, но не выдаёт себе authority.
- [ ] GREEN: `cd elixir && MIX_ENV=test mix test test/symphony_control/mcp/review_queue_parity_test.exs --trace`; фактический cloud ChatGPT сценарий входит в RQ08.

## RQ08 — полный цикл, перезапуск и контроль зависания переходов

**Owner:** SN-042, совместно SN-041 и MCP W06. **Вход:** RQ01–RQ07 и собственные QA/milestone prerequisites. **Выход:** evidence на AC-REVQ-01–18 и наблюдение переходов.

**Файлы:** `test/e2e/review-cycle.spec.ts`, `elixir/lib/symphony_control/observability/review_progress.ex`, `docs/acceptance/review-queue-evidence.json`.

- [ ] RED: намеренный дефект проходит implementation, получает CHANGES_REQUIRED, исправляется и проходит новое review. Restart между стадиями не создаёт дубль writer/job/publication.
- [ ] Проверить candidate без review, review без прогресса, решение без transition и застрявший outbox. Recoverable причины дают bounded reconciliation; unknown состояние не объявляется успехом.
- [ ] Реально выполнить merge/deploy/readback допустимой fixture и запуск следующего dependent, затем cloud ChatGPT read/write/denied. Код/тесты/UI должны ссылаться на один accepted input и одну историю.
- [ ] GREEN: `npm exec --offline -- playwright test test/e2e/review-cycle.spec.ts`; сохранить UTC, versions, source/image, assertions, exit codes, artifact hashes, limitations. Ни один NOT_RUN не становится PASS от наличия файла evidence.

## Проверка и передача плана

Восемь пакетов являются детализацией будущей реализации. Команды выше пока NOT_RUN. До paid dispatch необходимы review плана, согласованная canonical composition и accepted prerequisites. Проверить coverage всех 22 требований и 18 AC, отсутствие обратных зависимостей, точность каждого paired override и сохранение policy. Затем реализовывать по зависимостям, с отдельными review задачами после готовности этого механизма; до её готовности применяются существующие независимые проверки.
