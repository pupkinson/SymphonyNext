# BOOT-P01 worker evidence

## Identity

- Task: GH-2 / BOOT-P01 in `pupkinson/SymphonyNext`, repository ID `1381693716`.
- VERIFIED at 2026-09-22T20:39:31Z: `id -u` returned `995`; `pwd` returned `/var/lib/symphony-next-bootstrap/workspaces/GH-2`.
- Sole worker; no additional agents. Authorized profile: `gpt-6-astra`, reasoning `low`. Effective runtime model/session identity is UNKNOWN to this report and requires observer evidence.
- Owner-authorized admission applies to this exact operational pilot. The committed `admission:false` remains a preparation snapshot.

## Source

- Base: `30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8`.
- Source tree: `ef76ae50ceff736e7f481797c40db97c6c52255c`.
- Branch: `pilot/BOOT-P01`, created from that exact base after workpad publication/readback.
- PROJECT_RULES and SPECIFICATION versions: `0.5`; policy schema: `symphony-next-policy/v1`; pilot schema: `symphony-next-operational-pilot/v1`.
- Read PROJECT_RULES.md, AGENTS.md, bootstrap/PILOT.json, bootstrap/PILOT_TASK.md, policy and skills policy; resource bindings read from bootstrap/RESOURCE_BINDINGS.json. Specification output was partially truncated; the explicit BOOT-P01 operational exception is the task contract, not product backlog admission.
- Initial checkout was detached and clean. No local or remote pilot branch, prior workpad or matching PR was found.

## Commands

Every Git invocation uses this process-local prefix (abbreviated `G` below):

```text
git --no-pager -c include.path=/etc/symphony-next-bootstrap/gitconfig -c core.hooksPath=/dev/null -c core.fsmonitor=false -c credential.helper=
```

Times are UTC observation times; grouped commands have an aggregate shell exit unless explicitly recorded individually.

| UTC | Command / operation | Actual exit / HTTP | Observation |
| --- | --- | --- | --- |
| 2026-09-22T20:39:31Z | `date -u +%Y-%m-%dT%H:%M:%SZ`; `id -u`; `pwd`; `G rev-parse HEAD HEAD^{tree} --show-toplevel`; `G status --porcelain=v1`; `G branch --list` | shell 0 | UID995, exact source/tree/workspace, empty status, no pilot branch |
| 2026-09-22T20:39:31Z–20:39:48Z | stock `github_api` GET repository, issue 2, issue 2 comments, branches, PRs with `state=all&head=pupkinson:pilot/BOOT-P01` | each HTTP 200 | Correct repo/issue, open, admission label present, no prior workpad/branch/PR |
| 2026-09-22T20:39:31Z–20:39:48Z | `G fetch --no-tags origin refs/heads/main` | 0 | Only this repository's main fetched |
| 2026-09-22T20:39:48Z | `G rev-parse FETCH_HEAD FETCH_HEAD^{tree}` | shell 0 | Exact approved source and tree |
| 2026-09-22T20:40:10Z | stock `github_api` POST issue 2 comments; GET comment 5783795809 | HTTP 201; HTTP 200 | One BOOT-P01-ACCEPTED record created and read back before file changes |
| 2026-09-22T20:40:10Z–20:40:21Z | `G switch -c pilot/BOOT-P01 30b29e7970d64ecadf0e5c1d8d5e3b1230952ba8` | 0 | Branch created |
| 2026-09-22T20:40:21.678868Z | `G rev-parse HEAD HEAD^{tree} --show-toplevel` | 0 | Exact approved source/tree/workspace |
| 2026-09-22T20:40:21.695255Z | `G status --porcelain=v1` | 0 | Empty before report creation |
| 2026-09-22T20:40:21.716710Z | `G diff --check` | 0 | Baseline whitespace check; final report check still pending at this snapshot |

Initial combined documentation `cat` returned exit 1 because `RESOURCE_BINDINGS.md` was absent; repository search located `bootstrap/RESOURCE_BINDINGS.json`, which was subsequently read with exit 0. No authorization error occurred.

## Results

VERIFIED: real shell execution, exact identity/source/clean checkout, fresh main fetch, stock GitHub API reads and workpad write/read. Workpad: https://github.com/pupkinson/SymphonyNext/issues/2#issuecomment-5783795809.

This report is the sole intended file delta. Final report whitespace/scope checks, commit/push, remote SHA readback, draft PR and label removal occur after this snapshot; their actual outcomes, exact resulting HEAD/tree and report hash belong in the same workpad. They are not claimed here in advance.

INFERRED: the successful tool round trip supports operational tool availability for this worker; it does not establish product or runtime readiness.

## Limits

UNKNOWN: independent runtime model/session verification, final service stop/observer cleanup and monetary cost. Eight-turn and 1800-second bounds are authorized usage limits, not a measured price cap. Network access is not an egress allowlist.

BLOCKED: full acceptance pending independent observer verification. Product tests NOT_RUN; SN-001 and historical refused operations remain separate. No dependencies/installers, policy/workflow/service/READY changes, merge, deployment or other repository operations are part of this pilot. No credentials or environment were read or published.

Rollback state: no product/runtime mutation to roll back; preserve this workspace and the unmerged evidence branch/PR. No rollback has been executed.

## Next action

Complete the authorized final checks and one commit/non-force push/draft PR; update the existing workpad with exact evidence and remove only `symphony-next-ready`, reading issue 2 back and leaving it open. Independent observer then verifies the exact commit/PR and runtime evidence and stops the service.
