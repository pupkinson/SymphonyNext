---
tracker:
  kind: github
  provider:
    repo: pupkinson/symphony-next
    token: $SYMPHONY_NEXT_GITHUB_TOKEN
    api_url: https://api.github.com
  required_labels:
    - symphony-next-ready
  active_states: [open]
  terminal_states: [closed]
polling:
  interval_ms: 30000
workspace:
  root: /var/lib/symphony-next-bootstrap/workspaces
agent:
  max_concurrent_agents: 1
  max_turns: 8
  max_retry_backoff_ms: 60000
hooks:
  after_create: |
    git clone git@github.com:pupkinson/symphony-next.git .
  timeout_ms: 60000
codex:
  command: /opt/symphony-next-bootstrap/runtime/bin/codex app-server
  approval_policy:
    granular:
      sandbox_approval: false
      rules: false
      skill_approval: false
      request_permissions: false
      mcp_elicitations: false
  thread_sandbox: workspace-write
  turn_timeout_ms: 300000
  stall_timeout_ms: 120000
server:
  host: 127.0.0.1
  port: 4327
---

This is a REVIEWABLE EXAMPLE, not the installed workflow and not a launch instruction.
The repository name is a proposed target, not a discovered resource. Do not activate until
new repo/private/actions/auth/sandbox/egress and admission are verified independently.
The default turn sandbox has network disabled. Before a live task, review its exact
workspace/.git writable roots and scoped network policy against the real task identity;
do not replace this with danger-full-access or a broad HOME mount.
Stock max_retry_backoff_ms bounds a delay, not total attempts. The systemd pilot time limit
is a safety bound, not an implementation of the target product retry/stop contract.

You are assigned {{ issue.identifier }}: {{ issue.title }}.
Read PROJECT_RULES.md, AGENTS.md, SPECIFICATION.md, bootstrap/STATUS.json and the exact
card from planning/backlog.json before actions. Issue body: {{ issue.description }}.
Do not work from stale chat history. Do not replay or delegate a platform-refused write.
Fresh fetch the allowed repository, find prior workpad/branch/PR, and publish ACCEPTED
with exact base/worktree/branch/task/spec/policy. One writer; no subagents or global config edits.
Implement only the admitted leaf task; preserve existing DF Assistant and its credentials.
On missing permission, unknown external outcome or finite retry exhaustion, record a
sanitized diagnostic package and stop. Never claim unrun tests or successful deployment.
Before completing the pilot, remove its admission label through the authorised tracker
operation, verify that readback, preserve workspace/PR and hand off for independent review.
Do not close the issue merely to stop a worker, since terminal cleanup may remove workspace.
Ordinary delegated releases follow the exact-HEAD PR/CI/review/webhook/readback policy;
no per-deploy owner confirmation is needed inside an established delegation.
