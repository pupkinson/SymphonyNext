# GH-24: bounded immutable-source contract repair

BASE `06f2bb716af887b4f1cc52b1f850b0608bf81076`, tree
`97890dad460556c9ec0c8a95d309fa370df07c7d`. Single writer; transport
source repair 2/2, profile changes 0/1. Spec v0.5 and verified composition
0.5+MCP-SN031-r2 remain authoritative. This is CI maintenance, not admission
or completion of SN-003. ACCEPTED record: GH-24 issuecomment-5966326890.

The owner observed `review_source_only` with inputs.json only and a terminal
hold. The offending argument and number of reads are UNKNOWN. A reproduction
shows a legitimate added-file/base or deleted-file/head request aborts review.
Do not identify that reproduction as the proven cause of the live hold.

1. Add genuine RED tests for absent verified versions, coverage, finite request
   budget, advertised path union, unsafe arguments and sanitized diagnostics.
2. Return an explicit unsuccessful tool response for a known missing version.
   Advertise exact verified paths and head/base aliases. Keep unknown paths,
   namespace/thread mismatches, executable tools and insufficient source fatal.
   Persist bounded typed denial diagnostics in the new attempt's hold data.
3. Expand actual pinned Codex 0.155.1 fake-provider probes: added/deleted misses
   followed by real reads, strict negative reasons and direct-only source tools
   under bundled gpt-6-astra metadata. No paid model or credential access.
4. Prepare a single-use owner helper. Validate the exact installed recovery
   package/policy, parent proof, historical rows plus the new exact terminal hold,
   retained images, fresh receipt bytes, keeper isolation, binary, daemon and seed.
   Stage only this accepted delta; run offline native probe; change only policy
   installed_revision; recheck before commit. Preserve backups, proofs, old rows,
   receipts and keepers. Never start a unit, rebuild an image or publish a check.
5. Run targeted/full Python tests and diff checks, publish one draft PR and obtain
   one independent exact-HEAD read-only source review through the existing queue.
6. Owner handoff uses tmux, stop-only service control, pinned fetch/helper once,
   completion proof and daily budget readback. At most one corrective live CI
   launch. A new terminal hold ends this bounded source repair; no replay or
   profile escalation. A trusted check requires actual exact-HEAD publication.

Before installation, abandon only this change if necessary. After an uncertain
package/policy transition, preserve claim and backup and remain paused; no
automatic rollback or restart. Privileged/live actions are NOT_RUN by the writer.
