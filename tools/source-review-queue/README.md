# GH87: immutable paged source-review candidate

## Scope
Source candidate only; not installed. The persistent source-review queue and
protected CI are separate components. Workpad GH87, PR90. Denis supplied the
original and authorised the repair. No installed file, service, credentials,
frozen CI, old claims, model/profile settings or DF Assistant resource changes.
The existing --install-start command is NOT an updater or an instruction to run.

## Paged source contract
Opt-in snq-review/v2 adds context_sources pinned to head/base paths and blobs.
Before model reservation, collect both changed versions, scope documents,
documented HEAD spec-index groups and explicit context refs. Verify exact
repository/head/base/tree, complete PR diff, hashes/path/mode; deduplicate
identical blobs with aliases. Unknown URLs/Markdown are not followed. The only
tool snq_source_read(source_id,page) serves a preloaded immutable store, not
host filesystem/network/commands. All required pages and a matching final
store/receipt are mandatory. Delivery does not prove the model understood them.

Legacy v1 format and MAX_PACKET650000/PROMPT670000 remain. v2 bounds:
source2MiB, blob500000, index100000, page8192, calls400, result bodies4MiB,
documents256/aliases600/explicit refs64. No extra model turns or funds.
Paged include_mix_reference=true is unsupported; v1 retains it.

## Independent findings and repairs
GH91 on bf1e891 found three HIGH source defects: unbound report, incomplete
RPC frame on EOF, and repeated start replies replacing bindings. Repair1 bound
report lifecycle and request identities and added partial-frame detection.
GH92 on 7d41937 closed report binding and repeated replies, but identified:
HIGH server-EOF-first skipping unread client tail; MEDIUM client half-close
mistakenly rejecting a still-open fragmented server message.

Repair2 changes only proxy relative to 7d41937. Each stream has its own EOF
state; only its own buffer is checked when it closes. Reading continues until
both streams are closed within the unchanged deadline. Child exit or server
EOF alone is not success. Missing closure records RPC_TRANSPORT_NOT_CLOSED;
partial frame records RPC_PARTIAL_FRAME_EOF. The healthy pipe fixture now
actually half-closes the client, as intended by the single-session lifecycle.
Malformed legacy sequences are deliberately rejected, not preserved as API.

## Actual author verification
Run from this directory:

    python3 -B -m unittest discover -s tests -v

69 tests, zero failures/errors/skips, exit0, Python3.13.5. Python3.10 grammar
checked for all seven Python files. No existing test case removed. Three new
EOF regressions first failed on unchanged repair1, then passed after repair2.
They use real subprocesses/socketpairs and a selector wrapper to control event
order, not fake read/EOF values. An initial RED harness timeout was corrected
before changing production code; both logs are retained as different evidence.

Repair2 candidate SHA256:
113039678f00d4f2d909ab434de995beb3de01038de4d9242c26c1162ddfc581.
Corrected RED log SHA256:
69306e3179c96600a7349083f52bcf68c201f62b2116dd2d36e1e83e272e1802.
Full GREEN log SHA256:
28fea938c5d3945e000258452dc9d8aab5bd263280b56c673f75c60aafb66feb.
The historical full queue suite was not supplied;69 is this package's suite.
Fake GitHub/auth/quota and fake Codex peers are not actual provider acceptance.

## Native evidence and remaining gates
A real scratch Codex client completed one thread/turn and one source-page call
against a localhost fixed-response fixture on predecessor7d41937/ad5e4eba.
Child/helper exits0, two local HTTP requests, no credentials or real model calls.
Warnings were observed but their text was not captured in that first smoke.
This is predecessor component evidence, not a test of this repair2, production
permissions or the installed Symphony lifecycle. Fresh native and independent
source checks of repair2 remain separate gates, recorded in the PR/workpad.

No native schema-generation or other specifically refused operation is replayed
or delegated. No owner auth files are read/copied. Complete real PR84 review,
controlled installation and activation are not established by this source PR.
Do not replace /opt files or edit installed.json just to suppress verification.
Before actual installation, rollback is leaving this candidate unused.
EOF gating requires the upstream client to close its input after the final turn;
it holds, within the existing deadline, instead of inventing a clean shutdown.
