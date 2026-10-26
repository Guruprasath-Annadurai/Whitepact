# M12-C customer contract consumption and ownership

GLOBAL PRODUCTION NO-GO. This is product preparation, not M13 or security approval.

## Verified references

Recovered product successor: `9bc83a12e3894a2458d0c8544f8df7534ca14916`,
tree `93a9fb2bdd379928be3b70482628d94facd99e74`, parent
`1a116b956d4d0619c2f83ea230d3a9db21adc7e0`. Normal publication and GitHub
commit-object verification succeeded on 15 October 2026. Exact-head M12 review
38687453917 (four jobs), SDK review 38687454111 (four jobs) and Go review
38687454104 (one job) succeeded. Python M12 totals: 613 on each Python version.
These results do not validate subsequent M12-C edits.

Local M12-S repository `/Users/ag/.gemini/antigravity/scratch/whitepact-m12s`:
`15e0c62409d83934445f1832e53c2aa6d218137a`, tree
`f338687100609cf53522300087a4c00bf3d71100`, clean when inspected.
Its parent is the published product baseline `1a116b...`; it is not integrated.
The named remote M12-S branch was absent when checked. No security commit was
copied, merged, cherry-picked or changed.

The supplied M10-R reference `7514a23a31c518873fb2a8f81014e77dd6287965`
is absent from the product object database. Actual `/Users/ag/wp-int` HEAD is
`7514a23a3c8ba8fc5f27c758fe637752609e010e`. They must not be conflated.

## Exclusive write ownership

Codex: frontend evidence consumer, prepared read-only customer status/inventory
consumer, their unit/browser regressions and generated frontend distribution.
Antigravity: authority service/router, root assurance, consent verification,
delegation, revocation, repositories, execution, signing and policy enforcement.
No security-owned source changes are authorized by this document.

## Prepared consumer, deliberately not activated

`web/src/lib/customerAuthorityReader.ts` consumes only these existing M12-S GETs:

- `/api/enterprise/organizations/{org_id}/authority/status`
- `/api/enterprise/organizations/{org_id}/authority/agents`

The address derives from a supplied authenticated-session context, never a form
tenant selector. This is not a browser security boundary: the server must still
derive and validate the principal and tenant. Existing `api()` supplies session
credentials. Payloads have no client authority fields. Response tenant mismatch,
malformed flags, duplicate agent IDs and malformed status fail closed. Output
is an allowlisted view, not the complete response or secrets. `reportedActive`
and `reportedActiveDelegation` are server reports, not an ALLOW decision or an
execution grant. Missing/error routes remain errors, not fake empty inventories.

There is no production-route import, no mutation method, no fallback fixture,
and no bootstrap token or signing secret storage. Unit fixtures prove consumer
behavior only, not real integrated customer acceptance.

## Exact security-owner decisions still required

1. Root assurance: M12-S initiate request exposes `require_identity_assurance`
   defaulting to false; its executive verdict leaves IdP/WebAuthn policy open.
   Codex will not select an assurance policy or represent session membership as
   independent owner verification.
2. Recovery: initiate replaces the outstanding ceremony record. No stable
   read-only pending-ceremony lookup or lost-response reconciliation contract is
   documented. The UI cannot safely invent repeat issuance or recovery.
3. Public-key possession: the supplied completion example uses a placeholder
   public-key string. A key algorithm label is not proof of private-key possession.
   Approved ceremony provenance and verifier requirements must be explicit.
4. Status: docs allow ANALYST, while actual service `_verify_tenant_and_role`
   permits OWNER/ADMIN. `has_active_authority` is computed from non-revoked row
   presence; it must not be presented by the client as proof that a particular
   action, current consent validity or an external effect is authorized.
5. Lifecycle: agent registration/list/disable and delegation exist locally;
   no application CRUD/ownership/association, credential-reference rotation or
   policy-assignment lifecycle HTTP contract was located in this router.
6. Acceptance: bootstrap tests configure SQLite and create user, organization and
   session through repositories/services. They are not the required fresh HTTP
   signup → verified owner → real executor → distinct-human approval → revocation
   journey. Existing assertions must not be promoted to G2/G3/G4 acceptance.

Request Antigravity review and a stable published contract for these gaps. This
file is a handoff artifact, not evidence of delivery through an external agent
channel or of reviewer acceptance. G2/G3/G4 and G10 remain BLOCKED. No M13 entry.
