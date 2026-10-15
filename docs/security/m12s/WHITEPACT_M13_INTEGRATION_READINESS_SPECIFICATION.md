# WHITEPACT — M13 INTEGRATION READINESS SPECIFICATION

**Document ID:** WP-M12S-M13-013  
**Classification:** INTEGRATION CONTRACT & HAND-OFF DIRECTIVE  
**Date:** 2026-10-15  
**From:** Antigravity — Principal Security Architect  
**To:** Codex — M12 Product Integration & M13 Unified Qualification Leads  
**Status:** **READY FOR REVIEW & DASHBOARD BINDING**

---

## 1. PURPOSE & SCOPE OF INTEGRATION

With Milestone M12-S complete, the security foundation for customer root authority, explicit scoped consent, and agent delegation is fully established. This specification establishes the formal hand-off rules, interface boundaries, and acceptance gates for Codex to bind the user interface and SDKs in Milestone M13.

---

## 2. API INTEGRATION INTERFACES FOR CODEX

Codex owns the customer workflow UI, onboarding dashboards, and agent management consoles. Codex should consume the following verified endpoints:

```
+----------------------------------------------------------------------------------------------------------+
|                                    Customer Authority API Endpoints                                      |
+----------------------------------------------------------------------------------------------------------+
| POST /api/enterprise/organizations/{org_id}/authority/bootstrap/initiate   | Starts 2-step ceremony     |
| POST /api/enterprise/organizations/{org_id}/authority/bootstrap/complete   | Submits Root PK & Consent  |
| GET  /api/enterprise/organizations/{org_id}/authority/status               | Queries active root/epoch  |
| POST /api/enterprise/organizations/{org_id}/authority/root/{root}/revoke   | Owner emergency revocation |
| POST /api/enterprise/organizations/{org_id}/authority/agents               | Registers agent (NO auth)  |
| POST /api/enterprise/organizations/{org_id}/authority/agents/{a}/delegations| Issues attenuated grant   |
| POST /api/enterprise/organizations/{org_id}/authority/agents/{a}/disable   | Disables agent + revokes   |
+----------------------------------------------------------------------------------------------------------+
```

### UI Presentation Rules for Codex:
1. **Never Show Agent as "Authorized" Upon Registration:**
   The UI must visually separate "Agent Registered" from "Delegated Authority Granted". A newly registered agent must display a prominent badge: `Needs Delegated Authority`.
2. **Explicit Consent Acknowledgment:**
   During organization onboarding, the dashboard must present a clear, non-prechecked consent modal specifying allowed action types, target resource patterns, and intended purpose.
3. **Emergency Revocation Button:**
   The organization settings page must feature a red `Revoke All Agent Authority` action for Organization Owners, protected by a confirmation modal requiring typed organization slug confirmation.

---

## 3. INTEGRATION TESTING HARNESS & FIXTURES

Antigravity provides pre-packaged test helpers and fixtures for Codex:
- **`tests/test_customer_root_authority_bootstrap.py`:**
  - `_create_authenticated_customer_owner(client)`: Provisions a verified organization owner with authenticated session cookies and CSRF tokens.
  - End-to-end journey demonstration showing initiation, completion, agent registration, delegation, and execution resolution.
- **Mock vs. Live Database:**
  - Fast developer loop: Runs against in-memory SQLite (`uv run pytest tests/test_customer_root_authority_bootstrap.py -o addopts=""` completes in ~3.5s).
  - Pre-merge gate: Runs against PostgreSQL 16 container (`TEST_DATABASE_URL="postgresql+asyncpg://wp:wp@127.0.0.1:55433/postgres"`).

---

## 4. MERGE GATES & RELEASE CONDITIONS FOR M13

Before PR #203 or any subsequent M12/M13 pull request can be merged into `main`:
1. **Zero Regression Gate:** Full test suite passes without flags.
2. **P0-08 Invariant Gate:** Zero epoch drift on additive delegation grants.
3. **Tenancy Gate:** All cross-tenant test fixtures pass cleanly.
4. **No-Go Gate:** Maintain `GLOBAL PRODUCTION NO-GO` until founder sign-off on Root Assurance and Multi-Admin Quorum policies.
