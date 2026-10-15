## PR99 freshness-contract stage — saved, mandatory gates blocked

Owner-approved49999ms interpretation: observation must still be <50000ms at the
actual final decision. Exact49999/50000/50001 product-predicate tests, measured
real HTTPS49000 cache hit/no renewal and held49999 crossing denial are retained.
Canonical design/plan are unchanged; this is explicit owner-approved test scope.
Admission: https://github.com/pupkinson/SymphonyNext/issues/33#issuecomment-6153858886

Current combined148/0; exact related446/1 (unchanged login-begin positive refusal,
cause UNKNOWN). Standard make NOT_RUN while related is RED; no current full
coverage/Dialyzer or all-gates claim. Code/source/patch/evidence saved, NO_NEW_HEAD.
Authdisabled/activationfalse; independent review NOT_RUN, findings still OPEN.
See docs/engineering/authentik-project-access.md for exact inputs, first failures,
budget lineage and cleanup limits. All preceding report text is retained as history.

---

> PR99 integration continuation: mandatory gates remain **NOT GREEN**; no new HEAD was published. Exact back-channel status regressions, raw key metadata and initial Repo handoff controls are retained. Current failures, UNKNOWN standard-make interruption and cleanup limits are in [the engineering report](docs/engineering/authentik-project-access.md). Auth activation remains false; independent review is NOT_RUN. Previous reports below remain dated history.

> Task4 T4-R1–R6 repair candidate: auth stays disabled; mandatory gates and independent verdict are pending.
> Local session/credential bounds now accompany current Store reads through final protected response and callback cookie decisions.
> Signed logout retains exact millisecond/native bounds inside the existing atomic transaction; invalid handler requests use400.
> Cache capacity includes in-flight reservations, and a lifecycle owner preserves prior authorizers across Access restarts.
> LOGIN still returns to `/`; post-logout keeps the separate exact operator HTTPS URI, including non-root paths.
> See [the current repair evidence and limitations](docs/engineering/authentik-project-access.md).

# Symphony Next — пакет ТЗ и задач v0.5

Цель: самостоятельно размещённый на Coolify многопроектный оркестратор автономной разработки, с Authentik, собственным трекером, несколькими агентами/моделями, мобильным управлением и ChatGPT/MCP. Существующий DF Assistant не меняется.

## Task4: current access and logout — source only

Task4 adds current local project/platform permissions, a bounded IdP-observation
cache, session-bound CSRF and local/RP/signed back-channel logout. Owned real HTTPS
and PostgreSQL fixtures exercise login, permitted reads and revocation. Production
activation remains false; installed Authentik semantics, browser/two-tab revocation,
UID/ingress isolation and trusted/native release gates belong to Task5.
See [the engineering report](docs/engineering/authentik-project-access.md).

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

The remaining PR97 F2 repair anchors the last measured Clock sample to native
monotonic time. The caller releases a result only while both its original750ms
budget and object/credential lifetime still permit it, including delayed sample
delivery or processing. Confirmed consumption remains durable. Independent review
of this new candidate is pending; auth stays disabled and native HOLD remains.


## Task3: browser login в собственной HTTPS fixture

На принятом Task2 (`71bd5ff84d80327b83bbed50a494269fc254f478`) добавлен путь
begin → OIDC redirect → callback → один настоящий HTTPS token exchange →
подтверждённая локальная session → защищённая cookie → Authenticate.
Положительное HTTP-чтение проверяется только собственной fixture: server callback
обращается к её HTTPS provider, затем отдельный authorizer читает текущий локальный grant.
Session, email, группы и IdP admin claims сами по себе прав не дают.

Production auth остаётся выключенной: Config.activation_allowed? возвращает false,
Access по умолчанию отказывает, logout handlers пока denied. JSON по несекретному
пути SYMPHONY_CONTROL_AUTH_CONFIG не выбирает callbacks и не обходит activation gate.
Ремонт R1–R7 ограничивает auth ingress HTTP/1.0/1.1 с единственным Content-Length
до 32KiB или без body; transfer framing закрывается до чтения, HTTP/2 auth stream
отклоняется reset. Общие 5s включают первый Clock, чтение body и limiter;
ошибки сохраняют Conn. Первый login учитывается в выданном binding, а session
проверяется Store в вызывающем Login перед выдачей. Явный invalid manifest
останавливает startup; callback/backchannel paths проверяются до listener admission.
После LOGIN callback redirect остаётся фиксированным `/`. Отдельный операторский
`post_logout_uri` сохраняется точно: допустимый HTTPS same-origin URI может иметь
non-root path. Это не добавляет logout endpoint или landing-page в Task3.
Это локальное закрытие auth framing, не обновление Bandit и не устранение его
advisories для других routes/applications; перед release нужно отдельное disposition.
Task4 eligibility/logout и Task5 реальный Authentik/HTTPS/browser, production isolation,
independent exact-HEAD review и trusted/native/live acceptance остаются отдельными gates.
Это не полный SN005 и не выпуск. Предыдущие отчёты выше сохранены как история.
Сценарий, команды и ограничения: [Task3 engineering report](docs/engineering/authentik-project-access.md).


## Task4 R6/N1: non-destructive effective authorizer (2026-10-14)

The two Application environment authorizer values remain operator/default
configuration. Managed authentication keeps its active generation and writer
inside AuthorizerBindings; Projects and RuntimeIdentity select their effective
authorizer through its bounded resolver. Install, Access restart, release and
component shutdown do not overwrite either base value. Direct trusted put/delete
changes the base value, which becomes effective after confirmed managed release;
it does not grant new managed authority while the binding is active.

Unknown or failed managed lookup denies. A lifecycle sentinel identifies the
component, not a permission; unexpected component loss remains closed until
explicit new lifecycle startup. Actor/session/current membership checks and
production activation remain unchanged. Explicit legacy fixture callbacks retain
their base-authorizer behavior.

The owner-authorized causal baseline demonstrated the old lookup/write loss
(6 failures); scoped new lifecycle controls passed16/0 before this candidate's
final suites. Full results and exact publication are recorded in owning #33.
This is an author candidate pending independent source review and runtime
qualification, not Task5 admission or release approval. Historical A148/1 and
B020 remain failed with unresolved causes. The existing specification, PR79/82/84,
autonomy within its contract and multi-server task addressing remain in force.

## R6/N1 continuation: identity-barrier fixture compatibility (2026-10-14)

The owner approved a test-only adaptation of the two runtime-identity lifetime
regressions to separate operator defaults from managed authorizer selection.
These trusted fixtures retain Task4 and pass the exact external capture
`Eligibility.confirm/4`; the binding owner is deliberately inactive. The real
HTTPS observer, current local grants, receipt, Validity and final HTTP guard stay
in use. The existing wrapper delegates real authorization before holding the
snapshot. This lifetime coverage is separate from unchanged managed N1/R6 tests.

Prior exact-input related evidence was reused as compatibility RED, not a new
security failure. Scoped controls passed24/0; full continuation qualification
and any later result-only documentation seal are recorded in owning #33.
Production source is byte-frozen to158529de. Historical A148/1 and B020 remain
unresolved; independent review and release/Task5 gates remain separate.

Continuation result-only seal: full owning T1 67/1 exit2 (new frozen standalone
transport failure, HTTP status not obtained); exact related T2 465/0 exit0.
T3 NOT_RUN_T1_RED; broader lint retains10 frozen remarks. Bootstrap12/MCP11 and
static/body checks are separate author evidence. SOURCE_SNAPSHOT_ONLY,
INDEPENDENT_REVIEW_PENDING; no release or historical failure closure.


2026-10-15 — T4-N2/P1 + STYLE author candidate: effective authorizer decisions
carry a unique lifecycle revision through raw selection and callback acceptance
in Projects/RuntimeIdentity. Callbacks keep their original request process and
HTTP deadline; lookup250ms remains a separate delivery bound. Operator defaults,
legacy/graceful lifecycle, current grants and protected identity controls remain.
Fresh final T1 92/0, T2 490/0, ordinary make856/0/6 unchanged skips with100%
coverage/Dialyzer0 errors, strict lint and Python12/11 passed. First make failed
coverage99.82%; cycle2 removed duplicate inner callback catches, retaining the
original consumer error boundaries. First failures and historical results remain.
Prepared-cache isolation was breached during early setup; pre-bytes and some old
exit/reap observations remain UNKNOWN. Author GREEN does not erase that hold.
Independent review of the new exact HEAD is required. NOT_ACCEPTED_FOR_TASK5 /
NOT_RELEASE_APPROVAL / DO_NOT_MERGE. Full causal matrix, style-only equivalence,
input/output seals and limits are appended to docs/engineering/authentik-project-access.md.


2026-10-15 — R6-TIME author candidate adds a fresh closing native-time check after
complete binding-state validation. Selection retains its original lookup limit;
callback acceptance retains only the original HTTP deadline, with nil context
unchanged. Descriptor/lifecycle/defaults and both consumers are byte-preserved.
Actual direct RuntimeIdentity/Projects causal controls: old4 semantic RED plus4
positive controls; fixed8/0. Standard native regressions run without the one-off
observer. Fresh T1 98/0,T2 496/0,ordinary make862/0/6 with100% coverage and
Dialyzer0,strict lint,T4 Python12/11 passed. Full causal times/diff/source/limits
and first failures are appended to docs/engineering/authentik-project-access.md.
Prior prepared-cache process hold and UNKNOWN remain; current preparation004
also had inherited HOME despite own cache paths, then corrected/rechecked.
This is not independent acceptance or Task5/release approval. DO_NOT_MERGE.

### PR99: B/C test-harness candidate, 2026-10-15

Denis explicitly authorized a prospective split of the staged TLS test contract:
original1500ms deadline/no late POST and independent full real TLS5000ms controls,
including setup800. FIFO helper cleanup now uses real Python readiness, one3000ms
cleanup budget and explicit child wait/reap. Product code remains unchanged.
Author results: scoped11/0, T1 98/0, T2 503/0, Python12/0 and11/0.
Ordinary make FAILED at five new Credo findings; coverage/Dialyzer NOT_RUN.
This is WIP / NOT_ACCEPTED / DO_NOT_MERGE; independent B/C review is required.
[Contract mapping and evidence](docs/engineering/authentik-project-access.md).
Historical run2 remains FAILED, A503 remains UNKNOWN; auth remains disabled.
