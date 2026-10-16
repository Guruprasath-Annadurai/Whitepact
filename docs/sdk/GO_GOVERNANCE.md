# Go governance SDK (repository candidate)

Import the repository Go module's `raiclient` package. Package publication and
remote module-install qualification are separate gates; this is not a new release.

```go
client := raiclient.New(raiclient.Options{
    BaseURL: "https://your-whitepact-host.example",
    APIKey: os.Getenv("WHITEPACT_API_KEY"),
    Timeout: 10 * time.Second,
})
response, err := client.CallTool(ctx, "supported_tool", arguments, "approved-purpose")
if err != nil {
    // MutationUncertainError: never retry automatically. Reconcile first.
    return err
}
switch response.State() {
case raiclient.GovernanceSucceeded:
    // Explicit, conservative server response classification; not a new grant.
case raiclient.GovernancePending:
    // Inspect actual approval_id; authorized distinct approvers vote server-side.
case raiclient.GovernanceUnknown:
    // Effect may have happened. Do not execute again; inspect evidence.
default:
    // Denied, quarantined, failed or malformed: no completion claim.
}
```

## Canonical contracts

| Operation | Existing route | Requirements |
|---|---|---|
| CallTool | POST /api/v1/governance/tools/call | Org-scoped ANALYST+ bearer; name/arguments/purpose only |
| GetPolicy | GET /api/governance/policy | Persisted policy, not permission to execute |
| ListPendingApprovals | GET /api/governance/approvals?limit=1..200 | Pending only; no invented status filter |
| GetApprovalVotes | GET /api/governance/approvals/{id}/votes | Actual quorum/votes |
| ResolveApproval | POST /api/governance/approvals/{id}/resolve | ADMIN+; APPROVED or DENIED; not execution |
| ExecuteApproval | POST /api/governance/approvals/{id}/execute | ADMIN+; server resumes exact reviewed arguments with fresh authority |
| RevokeDelegation | POST /api/governance/delegations/{id}/revoke | ADMIN+; server performs cascading revocation |
| ListGovernanceEvidence | GET /api/governance/evidence?limit=1..200 | Tenant-scoped existing records |
| GetEvidenceAttestation | GET /api/governance/evidence/{id}/attestation | Existing attestation, not a claim of a digital signature |

There is **no standalone HTTP execution-grant minting/consumption endpoint** in
this baseline. Go cannot implement one without a canonical backend contract.
No local authority, nonce, policy evaluation, risk calculation or retry algorithm
is introduced. SDK requests never send an authoritative organization ID.

## Lost acknowledgement and reconciliation

Each request is one-shot, including approval resolution/execution and revocation.
Transport failure, deadline, response-body failure/malformed mutation response,
or HTTP 5xx returns `MutationUncertainError`. Its cause preserves deadline/cancel
sentinels or a typed `GovernanceHTTPError`, not arbitrary transport credential text.
UNKNOWN in a valid JSON response remains UNKNOWN, not completion or denial.

Do **not** blindly resend the mutation. Retain the actual approval/evidence IDs
already received, query the tenant-scoped pending/vote/evidence endpoints, and
have an authorized operator reconcile the effect against durable evidence and
the downstream system. An absent record is **not** proof of no effect. If no
identifier was received, the SDK cannot fabricate one or guarantee automatic
correlation. Reconciliation is manual until a stronger canonical backend contract
exists. A fresh consequential action requires fresh server authorization.

Server approval replay rejection is tested separately from SDK one-shot behavior;
it is **not** an idempotency promise for arbitrary tool-call retries. HTTP 401/403/
409 are surfaced, never converted into completed actions. Redirects are refused.
No browser session or UI authorization substitutes for bearer role/authority.

## Qualification limits

Native Go/TCP/PostgreSQL tests use supported test-user onboarding and two distinct
browser approvers. The Go executor uses an explicitly labeled internal ADMIN
fixture, not proof of production ADMIN credential issuance. Core enforcement
and Antigravity P0 qualification remain independent. Production remains NO-GO.
