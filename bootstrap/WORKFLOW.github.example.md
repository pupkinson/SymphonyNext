---
tracker:
  kind: github
  provider:
    repo: pupkinson/SymphonyNext
    token: $GITHUB_TOKEN
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
    env -u GIT_SSH -u GIT_SSH_COMMAND -u GIT_CONFIG_COUNT \
      GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0 \
      /usr/bin/git --no-pager \
      -c include.path=/etc/symphony-next-bootstrap/gitconfig \
      -c core.hooksPath=/dev/null -c core.fsmonitor=false \
      clone --template= git@github.com:pupkinson/SymphonyNext.git .
  timeout_ms: 60000
codex:
  command: /opt/symphony-next-bootstrap/runtime/bin/codex -c 'cli_auth_credentials_store="file"' app-server
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
Bindings match bootstrap/RESOURCE_BINDINGS.json. GITHUB_TOKEN is supplied by the existing
root-only host environment file; never copy its value into this repository or model context.
The existing service sets HOME and CODEX_HOME for UID995. No global configuration is changed.

Do not activate this example unchanged. The default turn sandbox keeps network disabled.
Before admission, bind the exact issue workspace and its .git to an explicitly reviewed
sandbox policy and verify the effective restrictions under UID995. Do not interpolate
issue variables into YAML configuration: this example only templates the Markdown prompt.
No broad HOME write scope or danger-full-access is authorised. Git shell commands must use
the same process-only env/Git profile as the clone hook; never fall back to a different key.
Use explicit process-only user.name/user.email for commits; do not change global Git config.

The cloned base must contain the accepted PROJECT_RULES.md and SPECIFICATION.md.
Until PR #1 is independently accepted and present on main, this main-cloning example
cannot be admitted. A different source ref requires its own exact reviewed candidate.
Stock max_retry_backoff_ms limits delay, not attempt count. The existing 1800-second
systemd limit and Restart=no bound the pilot; they do not implement durable target recovery.

You are assigned {{ issue.identifier }}: {{ issue.title }}.
Read PROJECT_RULES.md, AGENTS.md, SPECIFICATION.md and bootstrap/STATUS.json.
For a product task read its exact card in planning/backlog.json.
For the explicit operational BOOT-P01 task read bootstrap/PILOT.json and
bootstrap/PILOT_TASK.md instead; it is not completion of SN-001 or a bypass of its blocker.
Issue body: {{ issue.description }}.
Do not replay or delegate a platform-refused write. Do not use the old DF Assistant.
Find prior workpad/branch/PR, then publish ACCEPTED with exact base/workspace/task/policy
before changes. One writer; no subagents, service changes, credentials or global config edits.
Apply only the admitted task delta. Never run another product task because one is blocked.
On missing permission, uncertain external effects or exhausted bounds, record a sanitized
error and stop. No blind retry of writes, unrun PASS, self-review approval or fabricated CI.
Before finishing, remove the admission label through the authorised tracker operation and
verify it is absent; preserve workspace/PR for independent review. Do not close the issue
merely to stop execution, since terminal cleanup may remove the workspace.
Ordinary delegated releases keep the exact-HEAD checks/review/webhook/readback policy;
there is no new per-deploy owner confirmation inside an established project delegation.
