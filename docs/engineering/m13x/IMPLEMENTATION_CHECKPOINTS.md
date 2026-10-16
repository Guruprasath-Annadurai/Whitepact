# WhitePact Operation Atlas — M13-X Implementation Checkpoints

**Milestone:** M13-X  
**Branch:** `security/whitepact-m13x-platform`  
**Base Commit:** `8cb692b97063cf2b63897d8bba07842be4b0d00a`  

---

## 1. Backend Changes

### 1.1 `src/responsibleai/dashboard/config.py`
- **Purpose:** Added configuration attributes for WebAuthn origin and Relying Party ID.
- **Attributes Added:**
  ```python
  webauthn_origin: str = "http://localhost"
  webauthn_rp_id: str = "localhost"
  ```
- **Rationale:** Allows runtime injection and default configuration of WebAuthn credentials without hardcoded strings.

### 1.2 `src/responsibleai/enterprise/security/router.py`
- **Purpose:** Implemented dynamic loopback origin binding for development and testing.
- **Method Modified:** `_svc(request: Request | None = None)`
- **Behavior:**
  - In non-production environments (`app_env != "production"`), inspects `request.headers.get("origin")` and `str(request.base_url).rstrip("/")`.
  - If the candidate origin host is a loopback address (`localhost`, `127.0.0.1`, `[::1]`), dynamically configures `rp_origin` to match the exact caller port, with `rp_id` matching the host.
  - In production, strictly enforces configured `settings.webauthn_origin` with mandatory HTTPS.
  - Injected `request: Request` into `passkey_register_begin`, `passkey_register_finish`, `passkey_auth_begin`, and `passkey_auth_finish`.

### 1.3 `src/responsibleai/trust_fabric/enums.py`
- **Purpose:** Added `APPLICATION` to `PrincipalType`.
- **Enum Entry:**
  ```python
  class PrincipalType(str, Enum):
      TENANT = "TENANT"
      AGENT = "AGENT"
      APPLICATION = "APPLICATION"
      SERVICE = "SERVICE"
      HUMAN = "HUMAN"
  ```

### 1.4 `src/responsibleai/enterprise/authority/errors.py`
- **Purpose:** Defined error constants and factory functions for application inventory failures.
- **Errors Added:**
  - `APPLICATION_NOT_FOUND`
  - `APPLICATION_REGISTRATION_INVALID`
  - `application_not_found(app_id)`
  - `application_registration_invalid(reason)`

### 1.5 `src/responsibleai/enterprise/authority/service.py`
- **Purpose:** Implemented application inventory management, agent-application association, cascading disablement, and server-authoritative executable capability synthesis.
- **Key Methods Added/Updated:**
  - `register_application(actor, org_id, name, description, environment)`:
    - Generates `app_{uuid}`.
    - Validates caller authority (`authority:manage`).
    - Creates `APPLICATION` record in `trust_fabric_principals` with `lifecycle_state="ACTIVE"`.
    - Returns application model with `has_execution_authority: False`.
  - `list_applications(actor, org_id)`:
    - Queries all `APPLICATION` records for `org_id`.
    - Computes live `agent_count` by correlating registered agents.
  - `get_application(actor, org_id, app_id)`:
    - Fetches specific application; raises `APPLICATION_NOT_FOUND` on mismatch.
    - Returns application metadata and list of bound agent IDs.
  - `disable_application(actor, org_id, app_id)`:
    - Sets application `lifecycle_state="DISABLED"`.
    - Cascades to disable all associated agents in the tenant.
    - Cascades to revoke all active delegations and consent proofs for those agents.
  - `register_agent(actor, org_id, display_name, description, application_id=None)`:
    - Validates `application_id` exists in the tenant and is `ACTIVE`.
    - Associates agent with application.
  - `list_agents(actor, org_id)`:
    - Returns `application_id` on agent records.
  - `list_capabilities(actor, org_id, agent_id=None)`:
    - Synthesizes authoritative capability reachability from active root authority and explicit delegations.
    - Unbound agents report `PENDING_DELEGATION` and 0 execution authority.
    - Agents with delegations report `AUTHORIZED` with explicit permitted action types and target boundaries.

### 1.6 `src/responsibleai/enterprise/authority/router.py`
- **Purpose:** Exposed REST endpoints for application inventory and capability queries.
- **Routes Added/Updated:**
  - `POST /api/enterprise/organizations/{org_id}/authority/applications`
  - `GET /api/enterprise/organizations/{org_id}/authority/applications`
  - `GET /api/enterprise/organizations/{org_id}/authority/applications/{app_id}`
  - `POST /api/enterprise/organizations/{org_id}/authority/applications/{app_id}/disable`
  - `GET /api/enterprise/organizations/{org_id}/authority/capabilities`
  - `GET /api/enterprise/organizations/{org_id}/authority/agents/{agent_id}/capabilities`
  - Updated `POST /agents` schema to accept optional `application_id`.

---

## 2. Frontend Changes

### 2.1 `web/src/lib/customerAuthorityReader.ts`
- **Purpose:** Preserved exact historical reader contract (`{ status, agents }`).
- **Integrity:** Matches `web/src/test/m12c-authority-reader.test.ts` expectations without regression.

### 2.2 `web/src/lib/customerApplicationReader.ts`
- **Purpose:** Typed reader for applications and capability reachability.
- **Interfaces:** `ApplicationInfo`, `CapabilityInfo`.
- **Functions:** `customerApplicationReader(session).applications()`, `customerApplicationReader(session).capabilities()`.
- **Security:** Strict tenant ID validation and organization matching.

### 2.3 `web/src/test/m13x-application-reader.test.ts`
- **Purpose:** Vitest unit test suite verifying `customerApplicationReader`.
- **Coverage:** Tenant scoping, credentials propagation, malformed payload rejection, foreign org isolation.
