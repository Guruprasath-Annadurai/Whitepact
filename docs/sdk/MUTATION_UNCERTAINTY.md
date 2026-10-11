# SDK completion and ambiguous mutations

The Python and TypeScript SDKs are clients, not execution authority. `completed` / `isCompleted`
describe the server-returned execution result, not permission for another action.

## Actual response producers

`src/responsibleai/dashboard/app.py:governance_call_tool` returns `{tool, result, outcome_status}`
after execution. `OutcomeStatus` in `governance/outcome.py` includes SUCCEEDED, FAILED, ERRORED,
DENIED, BLOCKED and UNKNOWN. `mcp/governance_integration.py` emits explicit error envelopes for
denial, quarantine and approval-required decisions. Synthetic acknowledgement loss emits
`governance_unknown_outcome`. Legacy result envelopes may omit outcome_status or return null.

Only a result envelope with no conflicting markers is completed. Explicit outcome/status markers
must be SUCCEEDED. ALLOW is a decision, not proof of execution. UNKNOWN, DENY/DENIED,
REQUIRE_APPROVAL, QUARANTINE, FAILED, PENDING, unrecognized markers and malformed envelopes
are never completion. Nested tool error/is_error/isError markers also prevent completion.
The raw response is retained; no backend authority decision is synthesized.

## Lost response / timeout contract

Unsafe mutations are sent once. Transport exceptions, timeout (including body timeout), lost
acknowledgement, malformed success responses, redirects and HTTP 5xx do **not** prove the mutation
failed to happen. They must be treated by the caller as an **unknown observation**, not success
or certain failure. Existing transport/request exceptions remain exceptions; no automatic write
retry occurs. GET retries do not authorize retrying a mutation. No backend idempotency guarantee
is asserted for these endpoints.

1. Stop the action. Do not automatically resubmit, run the underlying tool directly, or mark it
   completed. Retain non-secret operation context and canonical IDs already returned, if any.
2. If an evidence ID exists, use `get_evidence(id)` / `getEvidence(id)` on the existing authenticated
   evidence endpoint. If an approval ID exists, inspect existing approvals and evidence. A ledger
   or approval record is not by itself proof of a downstream effect: inspect its outcome/provenance.
3. If the response was lost before IDs were received, these SDKs have no universal lookup-by-request
   or recovery endpoint. Request operator reconciliation using available tenant-scoped evidence and
   downstream state. An empty query result is not proof of non-execution. Human reconciliation may
   be required; uncertainty remains until independently established.
4. Only after reconciliation may a separately authorized new action be considered. Do not reuse
   an old permit or assume a retry has an idempotent effect. An UNKNOWN response does not authorize
   a new execution. Commercial entitlement and infrastructure state are not execution authority.

No new backend endpoint, stable idempotency key, automatic replay or exactly-once guarantee is
introduced by this client contract. Do not record credentials or raw secret-bearing arguments in
reconciliation logs. Exact configured-key redaction is not general server-secret sanitization.
