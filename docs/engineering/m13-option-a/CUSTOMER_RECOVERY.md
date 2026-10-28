# Recovering from isolation infrastructure refusal — Option A

This contract retains strict at-most-once approval consumption. It adds no reset,
lease, administrative bypass or automatic retry endpoint.

## Customer and API behavior

The execution endpoint can return HTTP503 with code
`ISOLATION_RUNTIME_UNAVAILABLE`. Inspect `execution_status`; HTTP503 alone never
proves that no work occurred.

|Observed state|Meaning|Permitted next action|
|---|---|---|
|BLOCKED, durably recorded before nonce admission|The attempt could not start. Its approval is CONSUMED and its execution nonce is unspent.|Repair infrastructure, then submit a fresh authorized request. Obtain every human approval required by current policy.|
|UNKNOWN, or missing/unconfirmed outcome|Execution or its durable accounting is uncertain.|Reconcile the original attempt through the approved operator process before deciding whether another request is safe.|

Never replay a consumed approval. An unspent nonce does not restore it. Do not
replace a request merely because its HTTP response was503 or its acknowledgement
was lost. Confirm the original attempt's evidence and outcome first. If outcome
persistence failed, the response is conservative UNKNOWN rather than a claim
that a BLOCKED record was persisted.

## Fresh authorized request

1. Identify the original tenant, approval, evidence and execution outcome. Retain
   their identifiers; do not alter or delete the failed attempt.
2. For proven BLOCKED only, resolve the infrastructure fault without relaxing
   isolation. Resubmit the intended action through the existing governed tool
   entry point, `POST /api/v1/governance/tools/call`, with the caller's current
   credential, explicit purpose and current authorized agent where applicable.
3. The normal request path must recheck credential/identity, tenant admission,
   consent/root/delegation authority, current policy and revocation. A new request
   is not automatically entitled to the old decision.
4. If current policy requires approval, use the newly returned approval ID.
   Authorized humans resolve it through
   `POST /api/v1/web/approvals/{id}/resolve`, with their authenticated session,
   organization administrator role, CSRF and applicable distinct-human quorum.
   Missing, duplicate or requester-self votes do not satisfy policy.
5. Execute the new approved ID through
   `POST /api/v1/web/approvals/{id}/execute`. Authority, action binding, expiry and
   revocation are checked again before durable nonce admission. The old approval
   remains CONSUMED throughout.

These are existing endpoints. This document grants no new authority or identity
assurance. A reusable credential still requires legitimate IDENTITY_VERIFIED
assurance; email/passkey or ordinary OIDC/SAML login alone does not supply it.

## Operator reconciliation

For UNKNOWN, lost acknowledgements, process crashes or failed outcome writes,
preserve the last committed approval/evidence/nonce relationships and inspect
the existing durable execution intent, container identity and recovery records.
Use only the already-authorized recovery/Store B process. An ordinary customer
or administrator must not mark an uncertain operation unexecuted, mint a bypass
grant, reset an approval or authorize duplicate side effects based on an
unconfirmed absence. If authoritative reconciliation evidence is unavailable,
keep the attempt unresolved and escalate to the authorized recovery operator.

## Evidence limits

The HTTP replacement tests use the existing test-only identity/authority fixtures.
Two use a mocked backend to verify protected routing and persistence. A third
requires actual Docker for the fresh approved attempt, with unisolated execution
disabled; it is not genuine provider assurance. Execution results must be
reported separately, and preparing that test is not a passing native result. The independently
reviewed7814c944 native/PG16 evidence remains distinct from canonical customer
acceptance. M13 remains OPEN; global production remains NO-GO.
