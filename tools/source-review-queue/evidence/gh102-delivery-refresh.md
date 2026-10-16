# GH60 receipt refresh — 16 October 2026

Owner24h extension6222244874; same writer6185510750/branch/PR103. Start18:35:10UTC;
cutoff17Oct18:04:56UTC, handoff18:34:56UTC. Candidate2bdcc review6222604076 was independently
rejected; corrective3/3 is the final allowed candidate. All old2/2+2/2+2/2,
windows/reviews/results/archives remain history. Review≤90min; no install/pilot.

## Contract and corrective finding

Owner6215538843: all15GH60inode predicates/label.at<=wall PASS, receipt<=label
mtime/ctime FALSE. Intent3Oct07:03:03.894980568Z, label07:03:08.291175811Z,
receipt07:21:03.642196769Z. Later GH60gates UNKNOWN; historical cause unproven.

Pinned7fa0ee and candidate deliver() replace a receipt after unique-comment GET,
then read labels. Interruption preserves an independent earlier label proof.
Both proofs must follow comment intent; neither must follow the other.

Candidate2's separate reviewer found equal JSON-clock times can conceal an old
label before a retained hold after a fresh receipt/label-GET interruption. Both
unchanged writers reproduced it:8probes,2unexpectedPASS. Final correction adds
ONLY held.mtime<label.mtime AND held.ctime<label.ctime to the existing strict
hold-before-comment requirement. Both proofs must independently postdate hold;
equal/coarse metadata HOLD. No tolerance/retiming/replay/schema/profile change.
All other guards/intake/drain/reviews/artifact AST and queue/execution unchanged.

## Tests and retained evidence

Candidate2's15new tests:8expected RED failures on e92, then316fullPASS/0skips.
RED SHAe7d5da767c114d6753d88f5d9466e6c3d150703f33e97c85a06b82bd814f4885;
fullSHA2ec4c6d70634f807903b787ccc3bb21f6dccbc1bdb2a44b262a5eb25a6831cc2.
Whole bdcc tree221files/33551952bytes/allGitobjects+modesMATCH/0omissions.
Native16oldHOLD/newPASS fixtures, API doubles/device2065/notruntime2050;
reportSHA7bfcd0dfdb6b6102ed4348c5c9d3ce46cea0625c7ac1b7a199c99512c4d849f1,
updaterf22a6948/driverf3225b68. Full bytes/provenance retained in qualification.

Four permanent corrective tests (both actual writers) allRED on bdcc: stale
label with equal JSON times, successful recovery, each equal/reversed inode clock independently.
RED logSHAb0fae7d376c0f4b21531ce7466f51317e6135b22c396fe57bf25de42d57229c2.
Then19targetedPASS/1.265s; all320PASS/0errors/failures/skips/15.686s,exit0;
fullSHA6c63d0969b3f0ec4839f6dded49f86d238eb42086b459be05075e854fd905af8.
Real local fsync/replace, no inode edits except explicit coarse-metadata double,
no API writes replayed, state unchanged, service double0events on HOLD/recheck.
UpdaterSHAb62d9c2fa7be565d2bd2c5fa7e9076d2e098ca3faca00498f9bfcc8eec3043dc.

## Handoff limits

Require fresh exact-HEAD independent receipt_refresh/native_clock_domain/
4285700019/4281361556/4281361568 PASS, full unchanged-cap repository check,
new immutable packet bound to actual4-file predecessor, delivery/readback.
Keep candidate2failure, e92NATIVE_HOLD, efa and olderREVIEW_BLOCKED archives.
Native fixtures/unit doubles are not live agents, global quiet or installation.
Updater never repairs/replays journals; future owner root check can still HOLD.
