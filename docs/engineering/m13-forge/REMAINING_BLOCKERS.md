# Defects and remaining work

| Priority / source | Reproduction / impact | Owner / dependency | Disposition / evidence |
|---|---|---|---|
| P1 `web/src/features/dashboard/DomainPage.tsx` | Delayed previous workspace read can replace current view | Codex | Fixed in Forge: keyed workspace state + cancellation; `forge-domain-reads.test.tsx` |
| P2 `web/src/features/api-keys/ApiKeysPage.tsx` | Malformed scopes crash list; unchecked metadata retained | Codex | Fixed in Forge: explicit metadata projection; `forge-key-inventory.test.tsx` |
| P1 I3 actual ceremony | Product RP/origin mismatch blocks registration | TITAN-1 | Historical reproducible blocker, not repaired here |
| P1 PR #212 first passkey | Password session cannot satisfy ADD_PASSKEY assurance | TITAN-1 | Prior actual browser 403; independent fresh owner fix required |
| P1 organization PATCH | Cookie-selected tenant lacks expected-org/version precondition | Backend owner | Rename remains disabled |
| P1 PR #212 capabilities/disablement | Effective authority and transactional qualification incomplete | TITAN-1 / TITAN-2 | Application integration blocked |
| P1 historical DCO / security lint | Protected unsigned ancestor; security-owned lint failures | Original owner / TITAN-2 | No waiver, history rewrite or forged attestation |

Fix commits are the Forge signed checkpoints containing these changes; draft PR receipt supplies exact hashes. API-key records include org_id and now require a matching selected session tenant; shared domain endpoints still lack a consistent tenant envelope. Full route inventory, fresh SDK/CI/browser/Linux/security acceptance are not yet completed. M14/M21 remain unauthorized.
