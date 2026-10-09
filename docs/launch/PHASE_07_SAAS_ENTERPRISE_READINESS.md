# Phase 7 — SaaS enterprise readiness

**Gate: CONDITIONAL for code that already exists. BLOCKED for commercial activation.**

This pass did not activate a payment provider, create a subscription, or change prices.

## Already in the candidate

| Area | Where | This session |
|------|--------|--------------|
| Plan field on organizations | migration `0003_add_billing_plan_to_orgs.py` | Not re-run |
| Paddle billing service | `src/responsibleai/db/paddle_billing_repository.py`, `tests/test_paddle_billing_service.py` | Not re-run |
| Web billing routes | `tests/test_web_paddle_billing_routes.py` | Not re-run |
| Invitations and roles | enterprise service | Not re-run |
| API keys | web platform tests | Not re-run |
| Account lifecycle | data governance erasure | Not re-run |
| Audit history | enterprise audit paths | Not re-run |

Provider-specific Paddle code is present. A second, undecided provider must not be wired by guessing. Sandbox behavior belongs in the existing Paddle tests until the owner names a provider.

## Launch-essential gaps that are decisions, not code

See `PHASE_07_COMMERCIAL_OWNER_DECISIONS.md`. Engineering must not invent prices, trials, refunds, or tax.

## Entitlement rule to preserve

A plan change may narrow what a tenant can ask for. It must not widen an agent authority, skip a grant, or bypass the gateway. Billing state is not authority.

## Gate

CONDITIONAL for the presence of sandbox-oriented billing code. BLOCKED for paid launch.
