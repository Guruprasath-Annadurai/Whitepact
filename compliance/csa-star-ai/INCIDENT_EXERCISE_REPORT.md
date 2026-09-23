# Incident response tabletop exercise (simulation)

**Type:** Tabletop — **not a real security incident**  
**Date:** 2026-09-23  
**Facilitator:** WhitePact engineering (automated campaign documentation)  
**Participants:** Founder / Security Owner (solo role-play)

## Scenario

1. A **compromised AI agent** connected via MCP attempts a governed tool invocation with a poisoned `_provenance` chain (untrusted `tool_output` claiming an approval already granted).
2. The same session shows **repeated cross-tenant ID guesses** in API paths (simulated 403/404 mix).
3. Monitoring suggests a **possible API key leak** (GitHub secret scanning alert on a test repo — exercise inject).

## Expected WhitePact responses (verified against architecture)

| Step | Expected control | Evidence |
|------|------------------|----------|
| Detection | Authority kernel + governance dispatch deny unprovenanced or untrusted influence | `src/responsibleai/governance/causal_influence.py`, `mcp/upstream_dispatch.py`, tests in `tests/test_tool_trust.py` |
| Containment | Revocation epoch bump + session invalidation paths | `db/revocation_epoch_repository.py`, `tests/test_revocation_kernel.py` |
| Tenant isolation | Org-scoped queries reject cross-tenant reads | `tests/test_tenant_isolation.py` |
| Evidence | Tamper-evident audit hash chain append | Audit log writers in dashboard; **not** immutable storage — see `CAIQ_EVIDENCE_BOUNDARY.md` |
| Communication | Use `INCIDENT_RESPONSE_RUNBOOK.md` customer template (not sent in exercise) | `compliance/INCIDENT_RESPONSE_RUNBOOK.md` |

## Findings

| # | Gap | Severity | Remediation |
|---|-----|----------|-------------|
| 1 | Provider-side WAF/DDoS evidence not in repo | Medium | OA-002 |
| 2 | 24/7 on-call roster not applicable (solo) | Low | Document in ORGANIZATIONAL_CONTROL_REGISTER |
| 3 | Full production log export not exercised in this drill | Medium | Run OA-002 + scheduled log export test |

## Closure criteria for exercise

- [x] Scenario documented  
- [x] Mapped to runbook + code paths  
- [ ] Live production alert routing tested (owner)  
- [ ] Customer comms template dry-run sent to counsel (owner)

**Sign-off:** Founder / Security Owner — pending after OA-002.
