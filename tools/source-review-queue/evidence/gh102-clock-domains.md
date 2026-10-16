# GH102 native clock-domain repair — 16 October 2026

Historical clock-stage evidence below is preserved. The later GH60 correction
replaces total intent->comment->label file order with intent-before-both;
individual coherence, application clocks and strict post-hold proof stay intact.
Current contract: [gh102-delivery-refresh.md](gh102-delivery-refresh.md).

Admission6210951994: same writer6185510750, branch feat/sn102-executor-profile-20261015,
base efa75ed8674534d28be9a0b318a7d40108fe6658. New3candidates,0handed at
preparation. Start07:57:45UTC/source cutoff09:27:45/handoff09:57:45UTC.
Independent review≤90min/candidate. All old2/2+2/2+2/2/history/windows retained.
No installation/pilot admission.

Owner's actual GH25/device2050 metadata locates the failed label.at<=filemtime
conjunct. JSON07:56:02.283405000 follows mtime07:56:02.279697559 by3707441ns
and precedes ctime07:56:02.283697727 by292727ns on2October. All three individual
metadata records and intent→receipt→label order pass. Later GH25/DELETE/hold/
review gates did not run: global runtime convergence is NOT established.

Existing7fa0ee predecessor writer reproduced16/16old HOLDs on fresh1c-db/rdc997
files in an allowed workspace/device2065, not runtime2050. Unsupported
application-time↔inode-time comparisons existed in all three label,DELETE-intent
and delivery-hold clauses. Linux inode timestamp granularity is documented at
https://docs.kernel.org/filesystems/multigrain-ts.html ; exact runtime filesystem/
kernel clock implementation is not attested by this experiment.

## Minimal change and preserved proof

delivery() captures one wall-clock instant and converts integer microseconds
to an aware datetime, without float rounding or an arbitrary tolerance. JSON
timestamps are compared to that instant and to other application timestamps;
file timestamps are independently compared to observed now and other files.

| Record/check | Candidate condition |
| --- | --- |
| label-removed.at | valid aware timestamp≤captured wall clock |
| DELETE-intent.at | valid aware timestamp≤label.at and≤captured wall clock |
| retained delivery-hold.at | valid aware timestamp≤label.at and≤captured wall clock |
| all canonical files | same-FD bytes/stat; same device/single link;0<mtime≤ctime≤observed now |
| intent→receipt→label files | ordered mtime AND ctime |
| DELETE file | mtime/ctime≤label file metadata |
| retained hold file | BOTH mtime AND ctime strictly before replaced comment receipt |
| equal/ambiguous post-hold proof | unchanged HOLD |
| unknown/missing/corrupt/stale/body/result/generation proofs | unchanged HOLD |

No journal retiming/deletion/replay/fake proof, schema/role contract or notification
writer is introduced. queue.py/execution.py/predecessor bytes and Controller,
intake/drain/reviews/disposition/seal AST remain unchanged. Trusted live
queue-written canonical journals/coherent clocks remain the provenance boundary;
copied/retimed confirmations do not establish it.

## Qualification

Baseline285PASS/0skips/11.842s, logSHA2bb73670eceddc9470e93380115171e58092cf09292544a283643725722d058c.
Permanent new16tests pre-patch:16tests/27expected Hold errors/exit1,
logSHA4427332bf56cc90a077e33593f5ed29cea7b31878ceba0ca0fe32b80ae93f5ea.
An initial fixture naming error was corrected before the sealed RED/product patch.
Targeted16PASS/0.434s, logSHAa1ecdc78097b432b3e1bf282bb8a38cde9b246230f4cdf7adef2701e3d306203.
Full301PASS/0fail/errors/skips/12.693s, all285prior tests retained, including
actual repository/video/Git modes/objects and intake/review/artifact coverage.
Full logSHA3c88ef35dd4ab8edd739e8c560a0c41dc4c9cd797249ee6425773a330a256f7e.

New tests cover original16native metadata samples and the owner clause, legacy/
developer, each of the three bad clock comparisons, real writer/recovery,
check/apply/rollback state preservation, future JSON, equivalent timezones and
exact wall-clock equality vs1ns future, unknown writes/missing proof, retained
hold/stale receipt, future/reversed/multi-link/cross-device file metadata.
No existing test was changed, skipped or removed.

Native1c-db qualifier uses unchanged SHA-pinned writer functions extracted as
AST definitions, without module initialization/auth/main. Real writes/fsync/
replace to NEW owned temporary files; all API replies remain local doubles.
- First16direct deliveries PASS, all16JSONat>mtime; reportSHA
  1c947bc4bd026eab38e1d6918b74b35c6305896cb1a98b26f09161b93195a47e,
  full same-tool readback/hash MATCH, evidence/gh102-clock-native-qualified.json.
- Extended32PASS:8direct,8DELETE,8lost-POST-ack,8lost-DELETE-ack.
  All32JSONat>mtime;16unknown/stale intermediate states blocked before actual
  GET reconciliation, exactly1POST and applicable DELETE once per case.
  Server reportSHA0ab4806cd5dfd082749f182c5f5fd1d601ae50b3b8e9bde677ffa3de3cc9a088,
  path /srv/rdc-workspace/handoffs/sn102-clock-source-20261016-d49ov737/sn102-fs-chronology-140h4pvy/report.json.
  Initial detailed readback returned tool error; status/error details were not
  retained by that failed orchestration. Later same-tool readback completed;
  full report SHA MATCH. The full32report is retained in qualification inputs,
  outside the source tree to preserve the32MiB real-repository admission limit.
  Recovery sleeps20ms ONLY in fixture to ensure strict replacement ordering;
  there is no20ms runtime tolerance, server clock change or gate relaxation.
- Extended utility first draft missed stat in its extracted namespace and
  failed before qualification; its fresh directory is retained. Corrected
  driver then completed32/32 without product changes.

These are native writer/filesystem fixtures on device2065, NOT runtime2050
or a live agent/service transition. No external notification/model calls,
runtime journal changes, apply/rollback or pilot104/105 were performed.
Candidate updaterSHA b070e6b4cbd049d9957368702d18c48684144d97738685d49d332f78c4edea5c.
Fresh full published-tree qualification follows publication; native full queue
check/installation/readback remains a separate owner step.

## Review and packaging

New exact-HEAD independent review must explicitly give native_clock_domain plus
4285700019/4281361556/4281361568 PASS; packager now requires all four. This is
a stronger packaging admission, without changing live queue/profile semantics.
No prior verdict is reused for the new HEAD. Full suite and actual full tree/
untouched video objects/modes must remain verified.

Build a NEW immutable reviewed archive after acceptance. Preserve efa75ed
archive/root staging and all earlier REVIEW_BLOCKED archives. Later owner
procedure must use a NEW private root directory and actual7fa0ee predecessor.
Never restore an old state snapshot. Native update/rollback and104/105 remain
NOT_RUN; source evidence does not waive current journal/filesystem gates.

