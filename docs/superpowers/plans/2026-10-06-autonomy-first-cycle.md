# Symphony Next: первый автономный цикл — Implementation Plan

> For agentic workers: use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task, only with admitted role-compatible skills. Internal engineering reviews belong to authorized roles; genuine human decisions follow AUT/v1. No skill grants permissions.

**Goal:** договор → задача → исполнитель → независимое review → исправление → разрешённый выпуск → проверяемая контрольная точка, без лишних подтверждений владельца.

**Architecture:** один canonical tracker/scheduler; PostgreSQL state, command journal и transactional outbox. Агенты предлагают команды; policy/release/recovery controllers детерминированно проверяют их и выполняют только разрешённые переходы. External writes имеют устойчивый intent и reconciliation.

**Tech Stack:** существующий Elixir/Mix, PostgreSQL/Ecto, runner adapters, Authentik, GitHub/Coolify, UI/API/MCP. Новые зависимости, версии и production resources не вводятся этим планом.

**Spec:** `docs/superpowers/specs/2026-10-06-scoped-autonomy-design.md` и четыре hash-bound контракта AUT/v1. Baseline v0.5 и MCP-SN031-r2 сохраняются.

**Planning base:** PR82 HEAD `e5dda93f88d2291d0b916142b68705e353fe94b4`, tree `a6a64e90fc8b1fe9e2f02aecb1ff19e87471f32e`. Контракты приняты source reviewer #83; новый план этим verdict не проверен. Статус: written_not_executed, dispatch=false. Все продуктовые AC — NOT_RUN.

## Global Constraints

- «Автономность внутри договора, человек — на согласованных решениях и реальном расширении границ».
- Effective authority = внешние ограничения ∩ договор ∩ роль ∩ задача; применимый deny сильнее allow. Валидный JSON не является authority.
- Договор, lease, exact-source evidence и одноразовый consent различаются. Новая сессия перечитывает договор; новый commit получает новые проверки, не новое согласие с проектом.
- AUT-W01..12 — slices существующих SN owners, не второй исполняемый backlog. Нельзя закрывать целую SN-задачу по выполнению одного slice.
- No GitHub Actions; DF Assistant исключён. Этот этап не меняет AGENTS/PROJECT_RULES/SKILLS_POLICY, project policy, baseline backlog, MCP refinement, protected CI, credentials или службы.
- Наследуемые верхние пределы: один writer; два repair cycles, одна смена профиля; три safe-read attempts с задержками 10/60 секунд. Договор не расширяет верхнюю policy. Новая задача не обнуляет расходы/лимиты цепочки.
- Платный dispatch требует действительного бюджета и атомарного резерва; суммы не придумываются. Requested model/effort/speed не выдаются за observed.
- Missing/NOT_RUN test не равен PASS; source review не равно trusted CI; merge/container running не равно runtime acceptance. Rollback только на известный совместимый predecessor.
- Candidate не изменяет собственный authorizer/trusted suite ради успешной проверки. Historical HOLD не перезапускается сменой инструмента или credentials.

## Review Focus

1. Отзыв или issuer ACL drift между preflight и side effect, поздний ответ worker: W02/W05/W08/W10.
2. Accepted A, затем новый HEAD/base/criteria/toolchain/skills или другое merge tree: W06/W07/W10.
3. Crash после commit до доставки, один key с разным payload, конкурентный последний бюджет: W03/W08.
4. Усечённый context, неизвестный hook/capability, выдуманный observed profile: W01/W04/W05/W07.
5. Reporting milestone одновременно завершает договор; consent устарел; уведомление не доставлено: W09/W11/W12.

## Исходная ситуация и prerequisites

В документальной базе PR82 ещё нет `elixir/lib/symphony_control`. Control foundation существует отдельно в PR14: на source `f16c32764df584291d2bdf95d66a4ef9f57daf83` прочитан `error.ex` и каталог с Repo/Projects/Application/Router/Health/runtime identity. Это не утверждение о merge или полной приёмке PR14.

До кода собрать accepted runtime source: SN-004 Repo/Projects/Error, SN-005 trusted actor/ACL, SN-006/007/010 canonical project/task/graph. Затем по packages потребляются SN-012/014/015 inbox/commands/scheduler, SN-016/017 runner, SN-025/026 ledger/profile, SN-031.W02.02 MCP foundation и SN-032 resource bindings. Отсутствующий prerequisite — BLOCKED, не mock-ready.

W01 собирает точные принятые baseline/MCP/AUT и относящиеся к работе PR3/10/15/26/79. Pending PR не становится принятой реализацией по ссылке. Проверяется effective graph как union depends_on и interfaces.consumes; исходные paired overrides и acceptance barriers сохраняются. Внутренний DAG этого плана не доказывает корректность всего product DAG.

Работающий source-review scheduler пригоден для проверки документов. Наблюдавшийся failed protected CI отдельно блокирует live acceptance. Этот план не ремонтирует установленный CI.

## Структура и общий TDD-цикл

Все пути ниже — предлагаемые create paths в accepted runtime checkout. Namespace функций: `SymphonyControl.Autonomy`; `Error` — существующий `SymphonyControl.Error`. Каждый указанный `.ex` получает зеркальный тест в `elixir/test/symphony_control/autonomy/<имя>_test.exs`. Это точное правило путей, а не обещание наличия файлов.

Общий return contract: `{:ok, validated_map} | {:error, Error.t()}`. Domain map — закрытый объект AUT/v1/W01, не произвольный payload. Коды: invalid_input, forbidden, not_found, conflict, dependency_unavailable, unknown_outcome. Сервер устанавливает actor; поля модели его не заменяют.

Каждый package выполняет проверяемые шаги:

- [ ] Прочитать accepted source, owner slice, prerequisites и незавершённые попытки; создать свой worktree и ACCEPTED record.
- [ ] Написать перечисленные negative/regression assertions; выполнить targeted command и сохранить настоящую RED. Setup/import failure не считать дефектом продукта.
- [ ] Реализовать перечисленные signatures и инварианты; повторить ту же команду до GREEN, actual exit 0.
- [ ] Выполнить broader quality `make -C elixir all` только в подготовленной разрешённой среде; required native/trusted gates не заменяются unit tests.
- [ ] Related commit/non-force push; сохранить base/head/tree, commands/cwd/environment/UTC/exit/log hashes; независимый exact-source review. Исправления идут в той же repair chain без нового пользовательского approve.

Указанные далее команды — будущие; при подготовке этого плана они не запускались. Прежде чем использовать уже реализованный эквивалент API, зафиксировать его mapping на accepted source; не создавать второй scheduler/ledger/tracker.

## AUT-W01 — Composition и wire protocol

Owners: SN-014, SN-029. Depends: accepted prerequisites. AC: AC-AUT-22.

Files: `elixir/lib/symphony_control/autonomy/source_composition.ex`, `protocol.ex`, `ports.ex` в том же каталоге; `schemas/autonomy-command.schema.json`, `schemas/autonomy-event.schema.json`; зеркальные source_composition/protocol tests.

Interfaces: `SourceComposition.assemble(index, sources)`, `Protocol.decode(bytes, :command | :event)`. Ports определяет callbacks AuthorityPort.resolve/2, ResourcePort.preflight/2, RunnerPort.launch/2, QualityPort.request/2 и readback/1, ReleasePort.merge/2 и readback/1, ProbePort.observe/2. Нет default allow adapter.

- [ ] RED: changed source hash → conflict; неизвестная major version/поле → invalid_input; потерянный MCP source или cycle в union dependencies → отказ до admission.
- [ ] Implement: полный hash-bound source и закрытые payloads всех 13 переходов AUT-TRANSITION/v1; controller/agent events различаются, unsupported refinement не пропускается.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/source_composition_test.exs test/symphony_control/autonomy/protocol_test.exs`.
- [ ] Commit/review: `feat(autonomy): validate composed sources and typed commands`.

## AUT-W02 — Договор и authority

Owners: SN-005, SN-014, SN-020. Depends: W01. AC: AC-AUT-03/04/05/13.

Files: `elixir/lib/symphony_control/autonomy/contracts.ex`, `policy.ex`; `elixir/priv/repo/migrations/20261006000100_add_autonomy_contracts.exs`; `elixir/test/support/autonomy_contract_fixture.ex`; зеркальные contracts/policy tests.

Interfaces: `Contracts.activate(actor, contract, expected_revision, deps)`, `current(project_id, contract_id)`, `revoke(actor, contract_id, expected_revision)`; `Policy.authorize(actor, action, snapshots, now)`.

- [ ] RED: client status=active без authority → forbidden; issuer ACL revoked/lookup failed → no action; applicable deny действует, даже если role grant_ids содержит только allow; expires_at <= now → forbidden; restart сохраняет revision/history.
- [ ] Implement: immutable revisions, current pointer/epoch; trusted AuthorityPort, полная проверка pins/resources/principals/срока/termination. Повторная проверка непосредственно перед side effect. Test-only authority не заменяет SN-005 integration.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/contracts_test.exs test/symphony_control/autonomy/policy_test.exs`.
- [ ] Commit/review: `feat(autonomy): persist revocable scoped contracts`.

## AUT-W03 — Транзакции, admission и ledger

Owners: SN-014, SN-015, SN-025. Depends: W02. AC: AC-AUT-09/10/12/20.

Files: `elixir/lib/symphony_control/autonomy/commands.ex`, `outbox.ex`, `admission.ex`; `elixir/priv/repo/migrations/20261006000200_add_autonomy_execution_records.exs`; `elixir/test/support/autonomy_fixture.ex`; зеркальные tests.

Interfaces: `Commands.apply(actor, command, deps)`, `Admission.claim(task_ref, contract_ref, estimate, expected_version)`, `Outbox.deliver(batch_size, deps)`; test-only `AutonomyFixture.seed!(opts)` возвращает project/task/contract/actors/command/deps и независимые DB connections для concurrency.

- [ ] RED: same key/payload → один event и одна obligation; same key/changed payload → conflict; crash после commit до delivery не теряет задачу; stale epoch → conflict; два соединения не резервируют больше approved_minor.
- [ ] Implement: state+obligation+outbox одной PostgreSQL transaction, unique claims, CAS/leases, stable intent. Ссылки на canonical task_ref и общий SN-025 ledger, не второй backlog/счётчик. Reserve/actual/unknown раздельны, repair_chain_id переживает новую task/session.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/commands_test.exs test/symphony_control/autonomy/outbox_test.exs test/symphony_control/autonomy/admission_test.exs`.
- [ ] Commit/review: `feat(autonomy): atomically record transitions and reserve work`.

## AUT-W04 — Planner и role skills

Owners: SN-026, SN-027, SN-029. Depends: W01/W02/W03. AC: AC-AUT-05/15/17/18/20.

Files: `elixir/lib/symphony_control/autonomy/planning.ex`, `skill_registry.ex`; зеркальные tests; `skills/symphony-role-manifest.json`; по одному `SKILL.md` в `skills/symphony-planning`, `symphony-implementation`, `symphony-review`, `symphony-debugging`, `symphony-release-verification`, `symphony-recovery-analysis`, `symphony-arbitration`.

Interfaces: `Planning.propose(actor, proposal, expected_plan_revision, deps)`, `SkillRegistry.resolve(role, manifest_ref, task_context)`.

- [ ] RED: ordinary in-scope engineering choice не создаёт human_request; unknown hash/hook/tool → отказ; unsupported engine/model/effort/speed → отказ; pinned active attempt не меняется при skill update; bounded business ambiguity → PRODUCT_DECISION.
- [ ] Implement: role contract → procedure → manifest; provenance/license/revision/hash и capability preflight. Никакого self-admission. Использовать SN-026/PR79 profiles, не дублировать каталог. Optional arbitrator не запускается без необходимости и не авторизует. Контроллеры не заменяются skills.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/planning_test.exs test/symphony_control/autonomy/skill_registry_test.exs`; отдельные LLM behavior trials фиксируют actual trial counts и не выдаются за unit proof.
- [ ] Commit/review: `feat(autonomy): bind planner and role procedures to contracts`.

## AUT-W05 — Runner и handoff

Owners: SN-016, SN-017, SN-028. Depends: W03/W04. AC: AC-AUT-03/13/19/20.

Files: `elixir/lib/symphony_control/autonomy/runner_dispatch.ex`, `handoff.ex`; зеркальные tests.

Interfaces: `RunnerDispatch.start(lease, context, deps)`, `Handoff.validate(candidate, assignment, evidence)`.

- [ ] RED: native isolation запрещает чтение control credentials, не только очищает env; stale lease не публикует результат; missing exact tuple или NOT_RUN+exit0 → invalid_input; requested profile не становится observed.
- [ ] Implement: штатный SN-016/017 RunnerPort, отдельные worktree/process/context, фиксированные tool/network/time limits. Не выдавать host socket/root. Агент создаёт candidate evidence, не trusted status; новая сессия перечитывает действующий договор без переноса старого разового consent.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/runner_dispatch_test.exs test/symphony_control/autonomy/handoff_test.exs`; затем отдельная native isolation приёмка.
- [ ] Commit/review: `feat(autonomy): dispatch isolated workers with fenced handoff`.

## AUT-W06 — Автоматическая защищённая проверка

Owners: SN-003, SN-030. Depends: W02/W03/W05. AC: AC-AUT-06/08/23.

Files: `elixir/lib/symphony_control/autonomy/quality_gateway.ex`, `quality_evidence.ex`; зеркальные tests.

Interfaces: `QualityGateway.request(candidate, contract_ref, deps)`, `QualityEvidence.verify(receipt, candidate, trusted_policy)`.

- [ ] RED: обычный новый B/test получает fresh check без ручного редактирования target; permitted dependency update получает fingerprint новой среды; forged receipt/wrong issuer/SHA/missing required stage → отказ; candidate edit trusted suite не проходит обычным путём.
- [ ] Implement: source-generic typed QualityPort и независимый trusted runner, не изменения установленных frozen profiles. Защищённая suite/runner policy вне writable candidate, candidate tests выполняются отдельно без credentials. Preserved regression requirements и review не дают удалить проверки ради PASS. Missing real QualityPort → unavailable, не mock success. Новый controlling-plane release отдельно принимает независимый verifier; исторические HOLD не сбрасываются.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/quality_gateway_test.exs test/symphony_control/autonomy/quality_evidence_test.exs`; реальная protected integration обязательна сверх doubles.
- [ ] Commit/review: `feat(autonomy): request source-bound independent quality evidence`.

## AUT-W07 — Review и repair chain

Owners: SN-028, SN-030. Depends: W03/W04/W05/W06. AC: AC-AUT-02/06/07/08/09/19.

Files: `elixir/lib/symphony_control/autonomy/reviews.ex`, `repair_chain.ex`; зеркальные tests.

Interfaces: `Reviews.submit(actor, verdict, expected_version, deps)`, `RepairChain.schedule(findings, chain, deps)`.

- [ ] RED: ACCEPTED A не принимает B, создаётся ровно одно review B; CHANGES_REQUIRED создаёт repair той же chain без approve; self-review/truncated source → отказ; docs acceptance не требует fictitious deploy, но смена deliverable_type после runtime failure запрещена.
- [ ] Implement: единые SN-030/PR10 obligations через W03. Tuple связывает repo/task/criteria/base/head/tree/policy/context/toolchain/skills/evidence. Reviewer — независимая сессия/trust boundary, не просто другая модель. Missing required tests/source → BLOCKED. Arbitrator не подменяет verdict или policy.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/reviews_test.exs test/symphony_control/autonomy/repair_chain_test.exs`.
- [ ] Commit/review: `feat(autonomy): drive independent review and bounded repair`.

## AUT-W08 — Recovery и reconciliation

Owners: SN-021, SN-022, SN-023, SN-024. Depends: W03/W05/W07. AC: AC-AUT-10/11/12/13.

Files: `elixir/lib/symphony_control/autonomy/recovery.ex`, `reconciliation.ex`; зеркальные tests.

Interfaces: `Recovery.next(incident, chain, snapshots, now)`, `Reconciliation.observe(intent_ref, deps)`.

- [ ] RED: lost response после provider commit → readback, только одна mutation; unavailable readback → HELD; restart сохраняет cooldown/counters; auth/policy denial не меняет credentials/tools; late revoked worker не меняет authoritative state.
- [ ] Implement: конечные limits Global Constraints, same chain accounting, stop-intake/fence до уведомления. At-least-once delivery с дедупликацией, не обещание exactly-once внешнего API. Late outcome записывается без восстановления полномочий. Независимые ветви продолжаются при отсутствии общего риска. PR3 health использует тот же recovery owner.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/recovery_test.exs test/symphony_control/autonomy/reconciliation_test.exs`.
- [ ] Commit/review: `feat(autonomy): recover with durable limits and reconciliation`.

## AUT-W09 — Human decisions и milestones

Owners: SN-010, SN-012, SN-020, SN-022, SN-029. Depends: W02/W03/W04/W07/W08. AC: AC-AUT-14/15/16/18/21.

Files: `elixir/lib/symphony_control/autonomy/human_decisions.ex`, `milestones.ex`; зеркальные tests.

Interfaces: `HumanDecisions.request(actor, request, deps)`, `resolve(actor, decision, expected_version, deps)`, `Milestones.evaluate(project_id, milestone_id, evidence, deps)`.

- [ ] RED: «продолжать?» внутри договора не создаёт human gate; один intent → один inbox item; changed payload/key → conflict; expired/replayed consent и stale owner ACL → отказ; no response никогда не значит approve; report_only продолжает, кроме contract termination.
- [ ] Implement: десять причин AUT-HUMAN/v1, exact delta/options/evidence/deadline/scope. PRODUCT_DECISION честно отражает существенную неопределённость после bounded analysis. Secrets/MFA только через защищённый личный интерфейс. Resolve перепроверяет identity/ACL/state/payload/срок/одноразовость/preflight. Недоставка уведомления не отменяет durable hold.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/human_decisions_test.exs test/symphony_control/autonomy/milestones_test.exs`.
- [ ] Commit/review: `feat(autonomy): enforce meaningful human gates and milestones`.

## AUT-W10 — Release и runtime acceptance

Owners: SN-032, SN-033, SN-034. Depends: W02/W03/W06/W07/W08/W09. AC: AC-AUT-01/02/11/13/23/24.

Files: `elixir/lib/symphony_control/autonomy/release.ex`, `runtime_verification.ex`; зеркальные tests.

Interfaces: `Release.begin(candidate, target_ref, deps)`, `reconcile(intent_ref, deps)`, `RuntimeVerification.accept(observation, acceptance_ref, deps)`.

- [ ] RED: missing receipt/changed head/base/criteria/policy/target/incompatible migration блокирует merge; merge/container-running без function остаётся VERIFYING_RUNTIME; wrong image/config/schema/revision не даёт ACCEPTED; без совместимого predecessor rollback не выполняется.
- [ ] Implement: typed expected-head GitHub merge, normal Coolify webhook, intent/readback и fixed functional ProbePort. Отличающееся итоговое merge tree требует применимых проверок итогового артефакта; review A не переносится молча. Разрешённый acceptance target берётся из manifest, не DF Assistant. Revocation допускает только отдельно разрешённую cleanup; destructive restore запрещён обычной rollback policy. Self-update контроллера — отдельный защищённый release.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/release_test.exs test/symphony_control/autonomy/runtime_verification_test.exs`; затем live GitHub/webhook/image/function evidence.
- [ ] Commit/review: `feat(autonomy): release only verified artifacts and observe function`.

## AUT-W11 — UI/API/MCP parity

Owners: SN-031, SN-035, SN-036. Depends: W01/W02/W03/W09/W10. AC: AC-AUT-14/16/18/21.

Files: `elixir/lib/symphony_control/autonomy/command_service.ex`, `http_adapter.ex`, `mcp_adapter.ex`; `elixir/lib/symphony_elixir_web/live/autonomy_decision_live.ex`; `elixir/test/symphony_control/autonomy/channel_parity_test.exs`; `elixir/test/symphony_elixir_web/live/autonomy_decision_live_test.exs`; зеркальные unit tests adapters.

Interfaces: `CommandService.execute(actor, envelope, deps)`; `HTTPAdapter.handle/3`, `MCPAdapter.handle/3` только нормализуют transport и используют CommandService. LiveView использует тот же service и sanitized views.

- [ ] RED: единая матрица прав/payload/version/expiry/revocation выдаёт одинаковый domain result во всех каналах; reconnect/два устройства не применяют решение дважды; agent MCP caller не отвечает за human-only challenge; mobile view не показывает secrets/raw errors.
- [ ] Implement: существующий authenticated actor transport, никакого неподключённого public endpoint. MCP foundation — SN-031.W02.02; полный MCP-SN031-r2 остаётся обязательным. W10 не ждёт downstream full MCP W06: иначе цикл через release. В интерфейсе goal/stage/blocker/options/evidence, не shell.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/channel_parity_test.exs test/symphony_elixir_web/live/autonomy_decision_live_test.exs`; live SSO/mobile checks отдельно.
- [ ] Commit/review: `feat(autonomy): share decisions across authenticated channels`.

## AUT-W12 — Сквозная приёмка и fault matrix

Owners: SN-042, SN-044. Depends: все W01..11. AC: все AC-AUT-01..24.

Files: `elixir/test/symphony_control/autonomy/first_cycle_test.exs`, `fault_acceptance_test.exs`; расширить `elixir/test/support/autonomy_fixture.ex`; `docs/engineering/autonomy-first-cycle-acceptance.md`.

Interface: test-only `AutonomyFixture.run_cycle!(scenario, opts)` с обязательным mode=:controlled или :live; dossier содержит source/contract/policy/skills/runtime identities, actual exits, event chain, ledger, review provenance, human reasons и unmet prerequisites.

- [ ] RED: задача проходит настоящий repair и review нового SHA, functional deploy; unnecessary_human_approvals == 0; после restart сохраняются история и договор, duplicate external effects отсутствуют; missing live dependency нельзя назвать PASS.
- [ ] Implement controlled integration на реальном PostgreSQL с process crash/concurrency и явно обозначенными provider doubles. Отдельный live model/repo/CI/Coolify/SSO run не подменять первым. Заранее известный дефект inject только в acceptance fixture; отдельно model-driven сценарий без предписанного verdict.
- [ ] GREEN: `cd elixir && mix test test/symphony_control/autonomy/first_cycle_test.exs test/symphony_control/autonomy/fault_acceptance_test.exs`; затем live dossier с actual commands и 24 AC outcomes.
- [ ] Commit/review: `test(autonomy): prove end-to-end repair and release without redundant approval`.

## Контрольные точки и доказательства

**M-AUT-CORE / report_only:** W01..05, договор/план/worker/handoff, PostgreSQL concurrency/restart. Это не готовность live release.

**M-AUT-LOOP / report_only:** W06..09, review → repair → новый review, authority denials/recovery без лишних approve.

**M-AUT-FIRST-SERVICE / human_decision:** W10..12, действительный разрешённый сервис и функция, dossier на всех каналах. Пользователь оценивает согласованный продуктовый результат; конкретные критерии берутся из договора, не придумываются агентом.

Один начальный договор, как минимум один реальный repair, новый exact-source review и functional readback. До decision checkpoint нет лишних human approvals; genuine scope/budget/MFA/неопределённость не скрываются. Reporting milestone не разрешает задачи после окончания договора.

Все 24 AC проверяются при fault-injection: дубликат, иной payload, stale lease, неизвестный write, отзыв, пропавший context, изменённый source, last-budget race, failed notification. CONTROLLED_INTEGRATION и LIVE_ACCEPTANCE имеют разные статусы. Behavior corpus skills включает in-scope bugfix, scope expansion, prompt injection, reviewer disagreement, missing context, MFA и budget exhaustion; число trials и фактические модели записываются, unit tests не считаются гарантией поведения LLM.

План не закрывает полные SN-042/044, baseline/MCP/TRK/model/health requirements. Перед dispatch нужен assembled exact-source index и actual prerequisites; ownership map — не готовый task-refinement importer.

## Выпуск, rollback и границы текущего этапа

Handlers/skills сначала disabled-by-default в отдельном acceptance project. Контролирующий слой не аттестует собственное обновление. До его принятия действующие frozen CI profiles/receipts/HOLD сохраняются. Внешние IDs/доступы/бюджет проверяются фактически до live запуска; их отсутствие — конкретный blocker, не новое согласование уже принятой цели.

До merge откат означает оставить candidate неприменённым; после миграций только известный совместимый predecessor. Stop intake/fence/evidence обязательны. Никакого destructive restore по обычной delegation.

Этот документ и карта — план, не product implementation. При их подготовке выполняются только structural/hash/coverage/internal-DAG checks. Full product DAG, Elixir/native/protected CI, runtime skills и 24 продуктовых AC не исполнены. Отдельное source review нового плана указывает собственный exact HEAD и не наследует ACCEPTED от контрактов.
