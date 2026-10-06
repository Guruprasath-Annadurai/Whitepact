# Final authority path — engineering proof map

**Status:** ENGINEERING EVIDENCE (not Antigravity PASS).  
**Lineage anchor:** M3 `620399b`, M4 audit `52d9b3c` (frozen).

| Stage | Module(s) | Persistence | Trust boundary | Fail-closed behavior | Tests |
|-------|-----------|-------------|----------------|----------------------|-------|
| Constitution | `responsibleai/governance/constitution*.py`, policy engine | Policy store / DB | Tenant | DENY on unresolved policy | `test_governance_*`, web policy tests |
| Identity | `responsibleai/enterprise/identity*`, web auth | `web_users`, sessions | Session vs API key | Invalid creds → no grant | `test_iam_adversarial_matrix.py`, SCIM lifecycle |
| Authority | `responsibleai/governance/authorize_execution`, RBAC | Grants, roles | Org/tenant | Missing role → DENY | `test_mcp_ws2_authority_matrix.py` |
| Intent | `ActionRequest`, MCP tool args | Request payload | Client → gateway | Schema / policy mismatch → DENY | MCP matrix, SDK contract |
| Policy | `WhitePactRuntimeGateway`, policy SPA API | DB policies | Admin-configured | APPROVAL_REQUIRED path | `test_web_policy_management.py` |
| Capability graph | Tool registry, upstream fingerprints | Registry DB | Server allowlist | Target drift → DENY | `test_mcp_ws2_*` upstream tests |
| Risk | Risk scoring hooks in governance | Audit metadata | Internal | Elevated risk → approval | Phase governance tests |
| Approval | Approval contracts, quorum | Approval records | Human quorum | Expired / rejected → no grant | Customer journey e2e, web tests |
| Judgment | `GovernanceDecision`, `DecisionResult` | Evidence-bound | Gateway | DENY sticks | SDK governance tests |
| Short-lived execution grant | Nonce / grant repos | `execution_nonce*`, PG | Time-bounded | Expired → fail | `test_phase7a_authority_kernel.py` |
| Isolated execution | Workers, upstream executor | Outbox / attempts | Executor sandbox | UNKNOWN on transport loss | `test_mcp_ws2_upstream_reconciliation.py` |
| Evidence | Evidence store, API | Evidence IDs | Immutable refs | Missing evidence → no retry authority | `test_sdk_governance_reconciliation_m3.py` |
| Audit | SIEM export, audit log | NDJSON / DB | Tenant export | SIEM down → no extra authority | `test_siem_delivery_m3.py`, M4 chaos |
| Revocation | `revocation_kernel`, break-glass | Epoch / suspension | Global per principal | Stale grant rejected | `test_revocation_kernel.py`, M5 stress matrix |

## Bypass protections

- Enterprise MCP trust domain blocks ungoverned stdio (`responsibleai/mcp/trust_domain.py`) — `test_mcp_ws2_authority_matrix.py`
- Restore admission chokepoint — `test_restore_admission_chokepoint.py`
- Legacy static surface retirement (M2) — `test_ws3_static_surface_inventory.py`

## Gaps (honest)

- Live cloud origin bypass: static checks only until staging drill (`test_m4_cloud_origin_static.py`).
- Some journey steps documented in runbooks as **draft** — see `KNOWN_LIMITATIONS.md`.
