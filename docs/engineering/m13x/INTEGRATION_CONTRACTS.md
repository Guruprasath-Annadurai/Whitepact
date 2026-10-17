# WhitePact Operation Atlas — M13-X Integration Contracts for Codex

**Milestone:** M13-X  
**Audience:** Codex, Frontend Integration Engineers, SDK Authors  
**Target Branch for Product Consumers:** `codex/whitepact-m13-p4-product` / `codex/whitepact-m13-i1-integration`  

---

## 1. Application Inventory Contracts

### 1.1 Register Application
- **Method:** `POST`
- **Path:** `/api/enterprise/organizations/{org_id}/authority/applications`
- **Authorization:** Bearer token / Admin API Key with `authority:manage` permission.
- **Request Body (JSON):**
  ```json
  {
    "name": "Customer Support Automation",
    "description": "Primary conversational assistant for billing inquiries",
    "environment": "production"
  }
  ```
- **Response Status:** `201 Created`
- **Response Body (JSON):**
  ```json
  {
    "application_id": "app_550e8400-e29b-41d4-a716-446655440000",
    "organization_id": "org_enterprise_1",
    "name": "Customer Support Automation",
    "description": "Primary conversational assistant for billing inquiries",
    "environment": "production",
    "lifecycle_state": "ACTIVE",
    "has_execution_authority": false,
    "agent_count": 0,
    "created_at": "2026-10-15T21:00:00Z"
  }
  ```

### 1.2 List Applications
- **Method:** `GET`
- **Path:** `/api/enterprise/organizations/{org_id}/authority/applications`
- **Authorization:** Authenticated session / Admin API Key with `authority:read` permission.
- **Response Status:** `200 OK`
- **Response Body (JSON):**
  ```json
  {
    "organization_id": "org_enterprise_1",
    "applications": [
      {
        "application_id": "app_550e8400-e29b-41d4-a716-446655440000",
        "organization_id": "org_enterprise_1",
        "name": "Customer Support Automation",
        "description": "Primary conversational assistant for billing inquiries",
        "environment": "production",
        "lifecycle_state": "ACTIVE",
        "has_execution_authority": false,
        "agent_count": 2,
        "created_at": "2026-10-15T21:00:00Z"
      }
    ]
  }
  ```

### 1.3 Get Application Details
- **Method:** `GET`
- **Path:** `/api/enterprise/organizations/{org_id}/authority/applications/{application_id}`
- **Response Status:** `200 OK`
- **Response Body (JSON):**
  ```json
  {
    "application_id": "app_550e8400-e29b-41d4-a716-446655440000",
    "organization_id": "org_enterprise_1",
    "name": "Customer Support Automation",
    "description": "Primary conversational assistant for billing inquiries",
    "environment": "production",
    "lifecycle_state": "ACTIVE",
    "has_execution_authority": false,
    "agents": ["agent_1", "agent_2"],
    "created_at": "2026-10-15T21:00:00Z"
  }
  ```

### 1.4 Disable Application (Cascading Revocation)
- **Method:** `POST`
- **Path:** `/api/enterprise/organizations/{org_id}/authority/applications/{application_id}/disable`
- **Authorization:** Bearer token / Admin API Key with `authority:manage` permission.
- **Response Status:** `200 OK`
- **Response Body (JSON):**
  ```json
  {
    "application_id": "app_550e8400-e29b-41d4-a716-446655440000",
    "lifecycle_state": "DISABLED",
    "disabled_agents_count": 2,
    "revocation_occurred": true
  }
  ```
- **Guarantees:** Cascades immediate disablement to all associated agents in the organization and revokes active delegations and consent proofs.

---

## 2. Agent Registration with Application Association

### 2.1 Register Agent
- **Method:** `POST`
- **Path:** `/api/enterprise/organizations/{org_id}/authority/agents`
- **Request Body (JSON):**
  ```json
  {
    "display_name": "Billing Agent 01",
    "description": "Processes invoice queries",
    "application_id": "app_550e8400-e29b-41d4-a716-446655440000"
  }
  ```
- **Validation:** `application_id` is optional. If provided, the server verifies the application exists in the tenant and is in `ACTIVE` state before associating.

---

## 3. Server-Authoritative Capability Inventory Contracts

### 3.1 List Capabilities (Tenant-wide or Agent-scoped)
- **Method:** `GET`
- **Path:**
  - Tenant-wide: `/api/enterprise/organizations/{org_id}/authority/capabilities`
  - Agent-scoped: `/api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/capabilities`
- **Response Status:** `200 OK`
- **Response Body (JSON):**
  ```json
  {
    "organization_id": "org_enterprise_1",
    "capabilities": [
      {
        "capability_id": "cap_agent_1_TOOL_CALL",
        "agent_id": "agent_1",
        "application_id": "app_550e8400-e29b-41d4-a716-446655440000",
        "kind": "TOOL_CALL",
        "action_type": "TOOL_EXECUTE",
        "allowed_targets": ["db.query", "crm.read"],
        "status": "AUTHORIZED",
        "requires_approval": false,
        "requires_passkey_stepup": false,
        "authority_enforced": true
      }
    ]
  }
  ```
- **Invariant:** Capabilities represent reachability only; executing any action strictly requires short-lived, single-use `ExecutionAuthorization`.

---

## 4. TypeScript Client Interfaces

Frontend consumers should import from `@/lib/customerApplicationReader`:

```typescript
import { customerApplicationReader, ApplicationInfo, CapabilityInfo } from "@/lib/customerApplicationReader";

const reader = customerApplicationReader(session);
const applications: ApplicationInfo[] = await reader.applications();
const capabilities: CapabilityInfo[] = await reader.capabilities(undefined, agentId);
```

---

## 5. Operation TITAN Security Updates

1. **Provenance Identifiers**: When `status == "AUTHORIZED"`, capability entries return `root_id`, `delegation_id`, and `consent_id` identifying the backing root of trust and delegation chain.
2. **Organization Rename Preconditions**:
   - `expected_organization_id`: Returns `409 Conflict` (`code: "WORKSPACE_CONTEXT_CONFLICT"`) if differing from active session cookie.
   - `expected_name`: Returns `409 Conflict` (`code: "ORGANIZATION_STATE_CONFLICT"`) if the name was modified concurrently.
3. **Application Disablement Rollback & Serialization**:
   - Disabling an application atomically invalidates in-flight execution permits on PostgreSQL across workers (`StaleRevocationEpochError`) and serializes against concurrent `register_agent`.

