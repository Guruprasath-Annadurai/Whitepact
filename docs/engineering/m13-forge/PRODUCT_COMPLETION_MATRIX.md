# Product completion matrix — partial inventory

| Surface | Classification | Current evidence / limitation |
|---|---|---|
| Signup, local email, login, onboarding | REAL AND VERIFIED | Prior I3 actual HTTP/browser prefix; repeat on Forge pending |
| Shared domain reads | READ-ONLY | Forge cancellation, workspace isolation, malformed payload regressions |
| API-key inventory | READ-ONLY | Forge metadata validation and per-record org_id check against selected session |
| API-key create/rotate/revoke | REAL BUT UNQUALIFIED | Existing UI fixture tests; full customer authority qualification outstanding |
| Agents, root and consent records | READ-ONLY | Existing typed readers; no effective-authority inference |
| Organization rename | BLOCKED | Missing expected-organization/version write precondition |
| Applications and association | BLOCKED | PR #212 contract remains independently unqualified |
| Passkey enrollment and downstream authority chain | BLOCKED | Product origin mismatch; security candidate first-passkey assurance blocker |
| Recovery and audit export preparation | PREPARATION | No qualification of privileged recovery/export execution |
| Full route/button inventory | NOT YET COMPLETED | Continue source review before claiming complete coverage |

Fixtures establish UI behavior only. They do not establish server authorization.
