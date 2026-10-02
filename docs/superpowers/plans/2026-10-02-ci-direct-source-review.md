# Direct immutable-source review transport

ACCEPTED GH24 scope: https://github.com/pupkinson/SymphonyNext/issues/24#issuecomment-5961990497
Source base `38ead3172e536e04dbfded60adc3ca0651607f38`, tree
`c40a32acb18ca3b228aa41a3b6a69af3c4e7ba17`. One writer in branch
`fix/ci-review-source-direct-20261002` and its separate worktree. Rules v0.5,
composition `0.5+MCP-SN031-r2`; no backlog admission or completion.

## Evidence and target

The saved live review held before reading any source: gpt-6-astra reported
`code-mode host is disabled`, read_count=0, source_bytes=0, no findings.
Codex rust-v0.155.1's bundled model metadata selects code_mode_only before
feature flags. Its source supports direct_only_tool_namespaces: they remain
direct and are omitted from the nested code-mode surface.

Keep the pinned binary/model, disabled code-mode host, read-only sandbox, empty
execution environments, source/path/budget checks and exact-identity verdict
gate. Put only read_source in a dedicated direct namespace. No host execution,
authentication access, worker/profile/quality or journal/controller changes.
Explicitly set agents.enabled=false, multi_agent_v2=false and sleep_tool=false:
the actual model's metadata also forces multi-agent v2 before the old feature
fallback. No collaboration call is invoked during diagnosis or testing.

## Verification and limits

1. Reproduce the native failure with the installed hash-pinned 0.155.1, bundled
   gpt-6-astra metadata and fake localhost provider in a fresh UID997 workspace.
   No account/login or real model request; synthetic transport evidence only.
2. RED regressions: direct source configuration, canonical namespace protocol,
   both exact source versions, denied paths/namespaces/events and source gate.
3. Implement the minimum namespace change. Native GREEN proves advertised
   source spec accepts JSON directly, excludes nested source wrappers and reads
   both versions without enabling the host. Keep old capability cases and test
   failed/forbidden code-mode attempts, no canary leakage or execution tools.
4. Run targeted and full CI Python checks, Python 3.10 grammar and diff check.
   Capture complete logs with exit codes and hashes.
5. Publish a separate draft PR and one independent exact-HEAD read-only source
   review through the existing Symphony queue. At most two corrective source
   cycles; no model/profile switch. Server preparations/held attempts retained.

Protected installation, corrective live attempt and activation require a
separate concrete bounded transition. This plan does not authorize them.
Timer remains disabled; no claims removed, trusted status, merge or deployment.

## Primary source

- https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/models-manager/models.json
- https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/tools/mod.rs
- https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/features/src/feature_configs.rs
- https://github.com/openai/codex/blob/rust-v0.155.1/codex-rs/core/src/tools/spec_plan.rs

Rollback before installation: preserve the candidate and evidence; installed
38ead317 remains stopped. A native fixture pass is not a live review or check.

## Observed verification

Native RED output: code-mode host is disabled, no fixture source returned;
diagnostic assertion exit0, evidence SHA256
`96e6059f3746ba6f9f40843cb51834b0228c9b6244144cfc45f41c3e178a3c9e`.
Native GREEN: nine cases, exit0; both catalogs read head and base, outside paths
and unread READY hold, no collaboration/execution command tools advertised,
disabled-host execution returns no canary. Log SHA256
`64d021089635b3453eb756ae7ccea342f64a15524f48acf331d0badd62fa27c4`.
Local full CI suite: 182 tests, 181 passed, one existing native isolation skip,
exit0, captured log SHA256
`76a32caa75954f5d050daffc86f65c852a5b7b6a82203e94cae07f8ee8903057`.
Live model review, owner installation/activation and protected check NOT_RUN.
