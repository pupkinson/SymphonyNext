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

## Native control foundation

The opt-in PostgreSQL/health foundation is documented in
[control-foundation.md](docs/engineering/control-foundation.md).
It remains disabled by default; native tracker, Authentik and product deployment
acceptance are separate milestones.
The legacy agent runtime refuses control enablement or retained database credentials;
a verified OS/container identity boundary is required before running both together.
Permitted children have no `SYMPHONY_CONTROL_DATABASE_URL` and control is disabled.
Linux startup-environment evidence is required; missing evidence blocks execution.

## Authentik protocol source checkpoint

Task1 adds the disabled Config/Oidc/Clock adapter with exact Oidcc 3.9.0 and real
disposable HTTPS regression tests. Targeted GREEN does not complete Task1 or SN-005:
broader coverage, independent review, dependency-compatible protected CI and live
bindings remain required. Native and Cloud attempt histories and current blockers
are retained in [authentik-project-access.md](docs/engineering/authentik-project-access.md).

The separately admitted 2026-10-05 Cloud fixup has 49/0 targeted tests, full CoreTest52/0,
and fixed-seed broad462/0/6 with configured coverage100%. UTF8 response-header values
retain binary bytes, preventing downstream telemetry exceptions; nonUTF8 still fails closed.
Only three retry tests use local empty memory fixtures; their assertions and timing ranges
are unchanged. Independent review, protected trusted checks and live bindings remain required.
Authentication stays disabled; all previous attempt reports and failures are preserved.

The 2026-10-06 queued-expiry repair rechecks credential UTC expiry when the caller
accepts a verified worker result. An expired queued identity returns forbidden even
within the network deadline; a still-valid queued identity remains accepted. Real HTTPS
regressions observed51/1 RED then51/0 GREEN with one token POST and worker cleanup.
Full gate evidence and the unchanged original attempt budget are in the engineering report.
Independent new-HEAD review/trusted checking remain separate; authentication stays disabled.

The separately admitted 2026-10-06 dependency-context continuation adds43 tests:
scoped structural telemetry/log checks over real signed-token HTTPS malformed responses
and scanner controls. Baseline and candidate94/0 pass; makeall507/0/6, coverage100%,
strict Credo and Dialyzer pass. No semantic product RED was reproduced; oidc.ex is
unchanged. [Complete licensed dependency source context](docs/engineering/oidcc-3.9.0-review-context.md) binds the actual
selected Oidcc/Telemetry files; Oidcc selected Hex-source equivalence is verified,
full Telemetry archive equivalence is NOT_VERIFIED. Existing token_type/unknown-field
acceptance is classified explicitly; no stricter protocol contract is added.
Actual client model/effort/speed remain UNKNOWN. History and frozen controls are preserved;
new independent review/trusted native/live acceptance remain separate, auth stays disabled.


TLS fixture attempt20261007 stopped **BLOCKED repair_cycles_exhausted (2/2)**.
Cloud baseline507/0/6,100%; uncommitted candidate509/1/6,100% exposes a charlist/binary
fixture failure in the new positive POST control. The1500ms/<1700ms deadline and
negative TLS-stage/latePOST assertions remain. Full gates/commit/push/newHEAD are
NOT_RUN; auth remains disabled. See [actual evidence report](docs/engineering/authentik-project-access.md).


AUTH-TLS-SOURCE-20261008-NEXT recovered the exact historical TLS draft and fixed
its real socket binary-mode failure. Final Config/OIDC96/0, bounded TLS/positive/
setup-pause controls, strict gates, make all509/0/6 and fixed-seed confirmation
509/0/6 passed with coverage100%. Earlier650ms/readiness failures remain in the
engineering report; cause UNKNOWN. New attempt2/2; publication readback is in
workpad33. Independent review/native check/live acceptance remain NOT_RUN; auth
stays disabled and historical native HOLD is open.


SN005-DEADLINE-POST-BARRIER-20261008 replaces the650ms test's pre-token timing race
with a reference-bound acknowledgement of a complete validated HTTPS POST. Its
response is held past the SAME original deadline; the850ms bound, onePOST and
caller/worker/provider cleanup remain. A signed positive control and separate
discovery/JWKS shared-budget regression pass. Final Config/OIDC101/0; fixed-seed
coverage and make all514/0/6,100%, all stage exits0. TLS1500ms/<1700ms/latePOST0
controls remain intact. Actual commands/hashes and preserved failure history are
in the engineering report. Closed old source attempts (including budget_violation)
and native422 HOLD remain unchanged. Independent new-HEAD review/trusted/live
acceptance remain separate and NOT_RUN; production auth stays disabled.


SN005-OWNER-DOWN-OBSERVER-41D840 repairs the fixture cleanup regression: a surviving
observer receives the actual reference/stage/provider-bound completion outcome.
Owner death must report owner_down; no release must report abandoned. The old
test passed with DOWN handling removed; the repaired test rejects that mutant,
and both cases pass after exact-byte restoration. Config/OIDC101/0 and one full
make all514/0/6,coverage100%,all stage exits0 passed. This is prior closed2/2 plus
one separately admitted additional cycle1/1; historical reports remain. The650ms
POST/shared-budget and stagedTLS controls are byte-unchanged, auth disabled and
native HOLD remains. New independent review/trusted/live acceptance are NOT_RUN;
actual commands, mutation hashes and owned PostgreSQL cleanup are in the report.
# Task2 auth state layer

The optional control source now includes durable one-time login flows, revocable local
sessions, current local rights and an OTP AES-256-GCM TokenVault. Exact local
issuer/subject bindings are required; IdP email/groups/admin claims do not register
users or grant access. Actor values carry no permissions. The new auth migration and
readiness contract are tested only on disposable PostgreSQL, with legacy project
schema compatibility preserved. Authentication remains disabled; browser integration,
IdP eligibility, trusted/native checks and live acceptance are separate open gates.
See [the engineering contract](docs/engineering/authentik-project-access.md).

PR97 repair adds one absolute 750ms operation budget, a fresh time check before
publishing auth results, and one SQL snapshot for session and rights. Clock sampling
tracks UTC/monotonic continuity without requiring identical millisecond elapsed
values. Timeout outcomes stay conservative; authentication remains disabled and
the repaired candidate requires independent review.
