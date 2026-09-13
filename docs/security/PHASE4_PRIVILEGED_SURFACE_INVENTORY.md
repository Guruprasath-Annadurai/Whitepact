# WhitePact Enterprise Phase 4: Privileged Surface Inventory
## Canonical Surface Classification & Risk Tier Mapping

**Document:** `docs/security/PHASE4_PRIVILEGED_SURFACE_INVENTORY.md`
**Branch:** `feature/enterprise-iam-phase4`
**Status:** CANONICAL INVENTORY COMPLETE

---

### Executive Summary

In WhitePact Enterprise Phase 4, the **Enterprise IAM, Privileged Access & Sovereign Recovery** subsystem establishes the authoritative privileged-control plane surrounding the Phase-3 Global Trust Fabric and platform services.

This document provides the exhaustive inventory of all control-plane mutations, administrative interfaces, and high-risk operations across the repository, mapping each surface to its:
1. **Risk Tier** (`PRIVILEGED_STANDARD`, `PRIVILEGED_HIGH`, `PRIVILEGED_CRITICAL`)
2. **Step-Up / Reauthentication Requirement**
3. **Four-Eyes / Separation-of-Duties Requirement**
4. **Break-Glass Eligibility**
5. **Durable Control-Plane Evidence & Attribution Record**

---

### Constitutional Invariants
1. **"NO PRINCIPAL GAINS ADMINISTRATIVE POWER MERELY BECAUSE IT REQUESTED IT."**
2. **"NO WHITEPACT OPERATOR MAY SILENTLY BECOME A CUSTOMER'S ROOT AUTHORITY."**
3. **"EMERGENCY ACCESS IS TEMPORARY AUTHORITY, NOT A PERMANENT BYPASS."**
4. **Never collapse:** Authenticated into Authorized, Admin into Root, or Platform Operator into Customer Owner.

---

### 1. Risk Tier Definitions

| Risk Tier | Scope & Impact | Authentication & Authorization Requirements |
| :--- | :--- | :--- |
| **`PRIVILEGED_STANDARD`** | Read operations on sensitive governance state; routine administrative modifications within org operational boundaries (e.g. creating routine API keys, updating budgets). | Valid authenticated session; active role check (`ADMIN` or `OWNER`); active session freshness within standard window (12 hours). |
| **`PRIVILEGED_HIGH`** | Operations modifying tenant trust boundaries, deleting entities, modifying security policies, rotating root keys, granting JIT privileged access, or enrolling MFA. | Fresh Step-Up reauthentication within narrow window (e.g. 15 minutes); active role check; single-use action nonce; JIT grant or explicit delegation if required. |
| **`PRIVILEGED_CRITICAL`** | Irreversible, destructive, or sovereign root-level mutations: root recovery, sovereign root transfer, tenant deletion, IdP configuration destruction, emergency break-glass activation. | Fresh Step-Up reauthentication (MFA / WebAuthn / hardware-attested token, ≤5 minutes); Four-Eyes approval (independent approver != requester) OR N-of-M cryptographic guardian threshold challenge; epoch bump and session revocation. |

---

### 2. HTTP Route Surface Inventory

#### A. Identity, Authentication & API Key Lifecycle (`src/responsibleai/dashboard/app.py`)

| Method & Route | Risk Tier | Step-Up Required | Four-Eyes Required | Break-Glass Allowed | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST /api/web/auth/login` | UNPRIVILEGED | No | No | No | Interactive credential presentation. |
| `POST /api/web/auth/logout` | UNPRIVILEGED | No | No | No | Session termination. |
| `POST /api/web/api-keys` | `PRIVILEGED_STANDARD` | No | No | No | Routine API key creation. |
| `POST /api/web/api-keys/{key_id}/rotate` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | API key rotation; invalidates old key lineage. |
| `DELETE /api/web/api-keys/{key_id}` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | API key revocation. |
| `POST /api/orgs/{org_id}/keys` | `PRIVILEGED_STANDARD` | No | No | No | Admin API key creation. |
| `DELETE /api/orgs/{org_id}/keys/{key_id}` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Admin API key revocation. |
| `POST /api/orgs/{org_id}/keys/{id}/mfa/enroll` | `PRIVILEGED_HIGH` | Yes (15m) | No | No | Multi-factor authentication enrollment. |
| `POST /api/orgs/{org_id}/keys/{id}/mfa/verify` | `PRIVILEGED_HIGH` | Yes (15m) | No | No | Verification of MFA enrollment token. |
| `DELETE /api/orgs/{org_id}/keys/{id}/mfa` | `PRIVILEGED_HIGH` | Yes (5m) | No | Yes | MFA factor disenrollment/reset. |
| `PUT /api/orgs/{org_id}/sso` | `PRIVILEGED_CRITICAL` | Yes (5m) | Yes | Yes | Modifies IdP configuration / SSO requirement. |
| `PUT /api/orgs/{org_id}/mfa` | `PRIVILEGED_HIGH` | Yes (15m) | No | No | Enforces org-wide MFA requirement. |

#### B. Organization & Sovereign Authority (`src/responsibleai/dashboard/app.py`, `src/responsibleai/iam/`)

| Method & Route | Risk Tier | Step-Up Required | Four-Eyes Required | Break-Glass Allowed | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST /api/orgs` | `PRIVILEGED_STANDARD` | No | No | No | Tenant creation ceremony. |
| `DELETE /api/orgs/{org_id}` | `PRIVILEGED_CRITICAL` | Yes (5m) | Yes | No | Irreversible tenant teardown. |
| `PUT /api/orgs/{org_id}/authority-ceiling` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Modifies tenant autonomy/authority ceiling. |
| `PUT /api/orgs/{org_id}/autonomy-budget` | `PRIVILEGED_STANDARD` | No | No | No | Updates monthly autonomy budget. |
| `POST /api/iam/root/transfer` | `PRIVILEGED_CRITICAL` | Yes (5m) | Yes | No | Sovereign root authority transfer. |
| `POST /api/iam/root/recover` | `PRIVILEGED_CRITICAL` | Yes (5m) | N-of-M Guardians | No | Emergency sovereign root recovery ceremony. |

#### C. Enterprise Governance & Policy Engine (`src/responsibleai/dashboard/app.py`)

| Method & Route | Risk Tier | Step-Up Required | Four-Eyes Required | Break-Glass Allowed | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `POST /api/governance/policy/rules` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Policy rule addition. |
| `DELETE /api/governance/policy/rules/{rule_id}`| `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Policy rule deletion. |
| `POST /api/governance/policy/reorder` | `PRIVILEGED_HIGH` | Yes (15m) | No | No | Rule priority re-ordering. |
| `POST /api/governance/workflow-rules` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Workflow rule modification. |
| `POST /api/governance/approvals/{id}/resolve` | `PRIVILEGED_HIGH` | Yes (15m) | Yes (4-Eyes) | No | Dual-custody action resolution. |
| `POST /api/governance/approvals/{id}/execute` | `PRIVILEGED_HIGH` | Yes (15m) | Yes | No | Executing dual-custody authorized action. |
| `POST /api/governance/delegations` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Delegating administrative/agent authority. |
| `POST /api/governance/delegations/{id}/revoke`| `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Revoking delegation authority. |
| `POST /api/governance/authority-passports/{id}/revoke` | `PRIVILEGED_HIGH` | Yes (15m) | No | Yes | Immediate passport revocation. |

#### D. SCIM 2.0 Identity Management (`/scim/v2`)

| Method & Route | Risk Tier | Step-Up Required | Four-Eyes Required | Break-Glass Allowed | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `GET /scim/v2/ServiceProviderConfig` | UNPRIVILEGED | No | No | No | SCIM discovery. |
| `GET /scim/v2/Users` | `PRIVILEGED_STANDARD` | No | No | No | SCIM user query. |
| `POST /scim/v2/Users` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM user provisioning. |
| `PUT /scim/v2/Users/{id}` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM user replacement. |
| `PATCH /scim/v2/Users/{id}` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM user update / deactivation. |
| `DELETE /scim/v2/Users/{id}` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM user deprovisioning. |
| `GET /scim/v2/Groups` | `PRIVILEGED_STANDARD` | No | No | No | SCIM group query. |
| `POST /scim/v2/Groups` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM group creation. |
| `PATCH /scim/v2/Groups/{id}` | `PRIVILEGED_HIGH` | Bearer SCIM Token | No | No | SCIM group membership sync. |

---

### 3. MCP Tools Surface Inventory (`src/responsibleai/mcp/tools.py`)

All 30 existing MCP tools in `TOOL_DEFS` are evaluated. MCP tools are client-facing or workload-facing tools:
- None of the standard 30 MCP tools perform unauthenticated administrative root actions.
- Administrative MCP tool wrappers (e.g. `rai_org_status`, `rai_webhook_status`, `rai_incident_log`) are read-only or operational reporting.
- High-risk operations invoked via MCP must route through the canonical `authorize_privileged_operation` chokepoint.

---

### 4. Canonical Enforcement Chokepoint

Every privileged operation across all surfaces must call:

```python
async def authorize_privileged_operation(
    *,
    db: DatabaseEngine,
    caller_principal: PrincipalContext,
    target_org_id: str,
    action: PrivilegedAction,
    target_resource_id: str | None = None,
    step_up_proof: StepUpProof | None = None,
    four_eyes_approval: FourEyesApproval | None = None,
    jit_grant_id: str | None = None,
    break_glass_session_id: str | None = None,
) -> PrivilegedAuthorizationResult:
    ...
```

Fail-Closed Invariants:
1. Caller principal must be active and match tenant (zero cross-tenant escalation).
2. Risk Tier validation is dynamic and strict.
3. If Step-Up is required, verification failure results in immediate `HTTP 403 / StepUpRequiredError`.
4. If Four-Eyes is required, requester cannot approve their own action.
5. If Break-Glass is used, the capability must match the action, must have an active incident binding, and must be unexpired.
6. The entire decision is durably audited with tamper-evident hashing.
