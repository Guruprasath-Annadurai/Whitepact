# WHITEPACT — AGENT IDENTITY & APPLICATION SECURITY CONTRACT

**Document ID:** WP-M12S-AGENT-004  
**Classification:** DOMAIN MODEL & SECURITY CONTRACT SPECIFICATION  
**Audience:** Codex Application Leads, Frontend Developers, Security Engineers  
**Module:** `responsibleai.enterprise.authority`  
**Status:** IMPLEMENTED & VERIFIED

---

## 1. DOMAIN ENTITY TAXONOMY & SEPARATION OF POWERS

To eliminate security-critical ambiguity between identity, configuration, credentials, and authority, WhitePact enforces strict distinctions across the following domain entities:

| Entity | Domain | Stored In | Authority Bearing? | Description |
| :--- | :--- | :--- | :---: | :--- |
| **Organization** | Tenant | `organizations` | No | Tenant boundary and security container. Owns all roots, agents, and policies. |
| **Human User** | Principal | `web_users` | No (by default) | Human employee/admin. Only OWNER role has authority to bootstrap or revoke roots. |
| **AI Agent** | Principal | `trust_fabric_principals` | **NO** | Registered agent entity with framework metadata. Holds **zero execution authority** by itself. |
| **Service Account** | Principal | `trust_fabric_principals` | **NO** | Automated machine principal for CI/CD or ingestion. |
| **Credential** | Secret | `api_keys`, `webauthn_credentials` | **NO** | Authentication secret. Authenticates identity only; never conveys authority. |
| **Policy** | Rule Set | `governance_policy_rules` | Guardrail | Defines constraints, required approvals, and deny rules. Can restrict, but cannot grant authority. |
| **Consent Proof** | Governance | `governance_consent_proofs` | **Prerequisite** | Signed customer record defining permitted action types, targets, and purpose. |
| **Delegation** | Governance | `governance_delegations` | **YES** | Cryptographically bound grant delegating attenuated rights from root to agent. |
| **Capability** | Authority | `AuthorityContext` | Computed | Mathematical set of permitted actions after applying delegation and consent constraints. |
| **Execution Grant** | Runtime | `ExecutionAuthorization` | **Single-Use** | Short-lived, nonce-backed permit for a single execution within the active epoch. |

---

## 2. THE CORE INVARIANT: REGISTRATION != AUTHORITY

In many legacy systems, creating an API token or registering an "assistant" automatically bestows write permissions. In WhitePact, this shortcut is strictly forbidden.

### Invariant Rule:
> **An agent registration confers identity, metadata, and lifecycle tracking. It grants ZERO execution authority.**

### Verification Proof:
When an agent is registered via `POST /api/enterprise/organizations/{org_id}/authority/agents`:
1. The agent is stored in `trust_fabric_principals` with `lifecycle_state = 'ACTIVE'`.
2. The response explicitly returns `"has_delegated_authority": false`.
3. If the agent attempts to execute an action immediately, `AuthorityResolver.resolve()` queries `delegations.get_latest_delegation(org_id, agent_id)` and raises `AuthorityDenied("DELEGATION_INVALID")` because no delegation chain exists.

Execution is only unlocked when an organization owner or administrator explicitly issues an attenuated delegation via `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/delegations`.

---

## 3. AGENT LIFECYCLE & MUTATION SEMANTICS

### 3.1 Registration
- Agents are provisioned within an authenticated tenant context.
- Name, description, framework (e.g., `crewai`, `langchain`, `llamaindex`), and stated purpose are captured.
- Agent IDs are globally unique, deterministic or cryptographically random (`agent_<12_hex_chars>`).

### 3.2 Attenuated Delegation
- A delegation grant requires:
  - `granted_action_types`: Must be a strict subset of the delegator's permitted actions.
  - `allowed_targets`: Must be a strict subset or exact match of consented targets.
  - `purpose`: Must match the consented purpose.
- Automatically creates a corresponding `ConsentProof` for the agent grantee.
- Mutates the delegation tree under a row lock (`lock_epoch()`) without advancing `revocation_epoch`.

### 3.3 Disabling & Deletion
- When an agent is disabled via `POST /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/disable`:
  1. `lifecycle_state` transitions to `DISABLED`.
  2. All active delegations targeting this agent (and any subordinate agents to which it delegated) are recursively marked `revoked_at = now`.
  3. All consent proofs with `grantee_id == agent_id` are marked `revoked_at = now`.
  4. The organization's `revocation_epoch` is atomically incremented.
  5. Any in-flight execution authorization issued to this agent fails closed on epoch verification.

---

## 4. CROSS-TENANT DEFENSE & AUDIT INTEGRITY

1. **Strict Context Binding:**
   The `AgentContext.identity.org_id` must match `GovernanceContext.organization_id`. Any mismatch raises `ValueError("CONTEXT_MISMATCH")` before resolution starts.
2. **Repository Scoping:**
   All delegation queries require `org_id` as the primary filter key. PostgreSQL indexes enforce `(org_id, to_identity_id, revoked_at)`.
3. **Immutable Audit Trail:**
   Every registration, delegation, and disabling event is committed to `enterprise_audit_log` with actor identity, target agent, before/after metadata, and UTC timestamp. Audit rows cannot be updated or deleted.
