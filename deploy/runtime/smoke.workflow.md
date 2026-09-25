---
tracker:
  kind: memory
polling:
  interval_ms: 1000
workspace:
  root: /var/lib/symphony/workspaces
agent:
  max_concurrent_agents: 1
  max_turns: 1
codex:
  command: /usr/bin/false
server:
  host: 127.0.0.1
  port: 4327
---

Offline container packaging fixture. The memory tracker has no issues.
No tracker credentials, tools, model session or production workflow is supplied.
This fixture does not certify SymphonyNext product readiness.
