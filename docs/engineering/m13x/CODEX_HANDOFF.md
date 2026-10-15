# WhitePact Operation Atlas — M13-X Codex Handoff & Coordination

**Issued To:** Codex (Product Integration Owner)  
**Issued By:** Antigravity (Security & Platform Execution Owner)  
**Milestone:** M13-X  
**Platform Branch:** `security/whitepact-m13x-platform`  
**Base Commit:** `8cb692b97063cf2b63897d8bba07842be4b0d00a`  

---

## 1. Division of Ownership & Boundaries

In accordance with CTO directives for Operation Atlas:
- **Codex Owns:** Dashboard UI components, frontend inventory page presentations, user experience flows, and integration verification in `web/` and `scripts/engineering/m13p4_*`.
- **Antigravity Owns:** Security foundation, authority service contracts, database models and migration integrity, runtime enforcement, WebAuthn origin and cryptographic bindings, and backend REST endpoints.
- **Strict Boundary:** Antigravity has **not** modified Codex's active branches (`codex/whitepact-m13-p4-product`, `codex/whitepact-m13-i1-integration`) or working trees. All work is staged on `security/whitepact-m13x-platform`.

---

## 2. Platform Capabilities Delivered for Codex

Codex's M13-P4 checkpoint identified missing backend contracts and ungrounded frontend inventory representations. Antigravity has completed these contracts:

### 2.1 Tenant-Scoped Application Inventory
- **Endpoints Available:**
  - `POST /api/enterprise/organizations/{org_id}/authority/applications`
  - `GET /api/enterprise/organizations/{org_id}/authority/applications`
  - `GET /api/enterprise/organizations/{org_id}/authority/applications/{app_id}`
  - `POST /api/enterprise/organizations/{org_id}/authority/applications/{app_id}/disable`
- **Agent Binding:**
  - `POST /api/enterprise/organizations/{org_id}/authority/agents` now accepts an optional `application_id`.
  - Registered agents reliably report their associated `application_id`.
- **Frontend Client:**
  - Codex can import `customerApplicationReader(session)` from `@/lib/customerApplicationReader`.
  - Note: `customerAuthorityReader` was intentionally kept unmodified to preserve `m12c-authority-reader.test.ts` exact keys test.

### 2.2 Server-Authoritative Capabilities
- **Endpoints Available:**
  - `GET /api/enterprise/organizations/{org_id}/authority/capabilities`
  - `GET /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/capabilities`
- **Semantics:** Capabilities represent reachability only; they do not imply blanket authority to act. Consequential tool or MCP invocations strictly require short-lived, single-use `ExecutionAuthorization`.
- **Frontend Client:** Available via `reader.capabilities(signal, agentId)`.

### 2.3 WebAuthn Dynamic Origin Resolution
- Dynamic origin resolution in development mode allows ephemeral dev servers to register and authenticate passkeys across dynamic ports without origin mismatches.

---

## 3. Recommended Integration Strategy for Codex

1. **Rebase or Merge Base:**
   - Merge `security/whitepact-m13x-platform` into Codex's integration candidate.
2. **Wire Application Inventory in Dashboard:**
   - In `web/src/pages/inventory` or related dashboard views, call `customerApplicationReader(session).applications()` to display registered tenant applications.
   - When registering an agent in the UI, offer an optional dropdown of active applications.
3. **Display Server-Authoritative Capabilities:**
   - Replace any simulated or hardcoded capability displays with live reads from `customerApplicationReader(session).capabilities(undefined, selectedAgentId)`.
4. **Preserve Migration Revision:**
   - Do NOT introduce an Alembic migration 0065 unless coordinated with repository owners, as historical regression suites assert revision 0064. Application models use the pre-existing `trust_fabric_principals` table.
