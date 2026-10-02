# Linear issue-status response boundary

TRK-05/TRK-13 continuation on source-accepted PR41 (19bcfad). This integrates
one decoded HTTP/GraphQL response with the unchanged StatusMap; it is NOT a
complete transport, polling adapter, scheduler integration or authentication layer.
PR41 is not merged; this feature branch retains it unchanged as its parent.

## Interface and ownership

`LinearIssueStatus.extract(http_status, decoded_body, binding, state_mapping)`
returns `{:ok, safe_fields}` or a fixed error. No request, mutation or admission
is performed. Only the authenticated Linear transport may call this function:
passing a user-authored map cannot prove source authenticity or access rights.
The transport must bound the response bytes, decode JSON with string keys, tie
it to its actual HTTPS request/credential/binding revision, and ensure freshness.

Binding is a plain internal map with EXACTLY these atom keys: workspace_id,
team_id, issue_id (mandatory UUIDs), project_id (mandatory key, UUID or nil).
IDs are normalized by hexadecimal text case. Extra keys are invalid_binding,
not ignored project-filter typos. They are expected scope, not secrets or claims
from the response. State mapping is the existing StatusMap UUID/category scheme.

## Expected selected response fields

The transport's single GraphQL query must select `organization { id }` and
`issue(id: $issueId) { id archivedAt team { id } project { id }
state { id team { id } } }`. This is a documented shape requirement, not an
executed live query. Organization belongs to the same authenticated response;
state.team, issue.team, workspace and exact issue ID must match the pinned
binding. A project filter is enforced when non-nil; without one, nil or any
well-formed returned project ID is allowed. Missing keys are not treated as nil.

The pure decoder cannot prove upstream data are truthful, that credentials grant
scope, or that a response was not replayed. Live schema/permissions validation,
query construction, transport deadlines/retries/byte limits, pagination and
persistent binding generation remain separate integration work. A null issue
maps to not_found only AFTER workspace matching; that is not proof of deletion.

## Failure order and safe output

1. Invalid binding always returns invalid_binding.
2. HTTP401/403 -> forbidden;429 -> rate_limited;500..599 -> unavailable.
   Other non-200 integer HTTP codes100..599 -> unexpected_http_status;
   invalid code types/range -> invalid_response. Raw error text is not returned.
3. HTTP200 must have a plain decoded map. Absent errors or an empty errors list
   can proceed; any nonempty proper list of up to256 entries -> graphql_error.
   An invalid/overlong/improper errors container -> invalid_response. A nonempty
   error list never accepts partial data, irrespective of individual messages.
4. Require complete data/organization/issue/team/state/project shapes and UUIDs.
   Cross-workspace/team/project/requested-issue mismatch -> scope_mismatch.
5. archivedAt must be an explicit nil or parseable ISO8601 timestamp<=64bytes.
   A valid timestamp -> archived (not completed); invalid type/text -> invalid_response.
6. Delegate state_id and all mapping validation to StatusMap.linear/2. Preserve
   unknown_status and invalid_mapping outcomes; no display-name fallback.

Successful output has exactly provider=:linear,workspace_id,team_id,project_id,
issue_id,state_id,category. It excludes body text, source error messages, display
names, tokens and execution/admission/approval fields. Unrelated GraphQL fields
are ignored; missing required fields and partial struct-shaped maps are denied.
No Atom/string conversion is performed on untrusted keys.

## Tests and evidence

24 new ExUnit cases exercise actual integration with StatusMap; the combined
subset includes its unchanged62 cases. Initial test helper naming collided with
Kernel.binding/0 and failed compilation; that setup error was fixed before the
genuine RED:86tests/24failures on the missing module. The implementation passed
86tests/0failures. Formatting and final explicit-load execution are recorded
separately in the task evidence directory, not represented as protected CI.

Only three new files are scoped: this document, linear_issue_status.ex and its
test. No existing source, dependencies, test thresholds, CI, server services or
credentials change. No earlier refused TaskRef/SessionAccess/GitHubIssueStatus,
cache/full-suite/CI operations are retried. Tests use synthetic response fixtures;
full Mix suite, Dialyzer/coverage, live Linear and deployed function acceptance
remain NOT_RUN. A separate fresh source reviewer must inspect exact HEAD.

Source reference: Linear's official Getting started documentation, read
2026-10-02, https://linear.app/developers/graphql — HTTP200 partial errors,
UUID model IDs, team-based issues and archived resources. SDK reference:
https://linear.app/developers/sdk-fetching-and-modifying-data — organization.
These are API references, not evidence of successful access to a user workspace.
