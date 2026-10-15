# WHITEPACT M13-S4 ENTERPRISE SECURITY API CONTRACT SPECIFICATION

**Milestone:** M13-S4 — Priority J Specification  
**Recipient / Integration Partner:** Codex (Product Integration Owner)  
**Security Owner:** Antigravity — Principal Security & Reliability Engineer  
**Router Prefix:** `/api/enterprise/organizations/{org_id}/authority`  
**Authentication Scheme:** Dual (Cookie-based session `wp_session` OR Verified Principal Bearer Token `wp_test_*` / `wp_staging_*` / `wp_live_*`)  
**Status:** **FREEZE / READY FOR PRODUCT FRONTEND CONSUMPTION**

---

## 1. Authentication, Step-Up & Error Envelope

All requests require an authenticated actor. High-consequence mutations (containment, quorum recovery execution, root revocation) mandate **WebAuthn Step-Up** via either Path A (direct assertion) or Path B (pre-verified authorization ticket).

### Canonical Error Response Envelope
```json
{
  "error": {
    "code": "WEBAUTHN_CHALLENGE_REPLAY",
    "message": "WebAuthn challenge has already been consumed or replayed.",
    "status_code": 409,
    "details": {
      "challenge_id": "wp_step_abc123"
    }
  },
  "request_id": "req_01j7..."
}
```

### Key Error Codes:
- `WEBAUTHN_STEPUP_REQUIRED` (401 / 403): Operation requires fresh or valid WebAuthn assertion.
- `WEBAUTHN_CHALLENGE_REPLAY` (409): Challenge/ticket already consumed by winning transaction.
- `SELF_APPROVAL_BLOCKED` (403): Requester attempted to approve own recovery request.
- `QUORUM_NOT_MET` (400): Dynamic pre-execution recheck determined insufficient active approvers.
- `RECOVERY_ALREADY_EXECUTED` (409): Recovery request was already executed.
- `CONTAINMENT_FORBIDDEN` (403): Caller lacks permission to contain organization or agent.
- `CROSS_TENANT` (403): Caller tenant does not match target resource organization.

---

## 2. API Endpoints Specification

### 2.1 WebAuthn Step-Up Challenge

#### `POST /api/enterprise/organizations/{org_id}/authority/webauthn/challenge`
Generates a cryptographically random, server-tracked challenge bound to a specific operation and parameters digest.

- **Request Body:**
  ```json
  {
    "action": "EMERGENCY_CONTAINMENT",
    "operation_digest": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "ttl_seconds": 300
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "challenge_id": "wp_step_f3b89c...",
    "challenge_str": "dGhpcy1pcy1hLWNyeXB0b2dyYXBoaWMtY2hhbGxlbmdl...",
    "expires_at": "2026-10-15T19:00:00Z"
  }
  ```

---

### 2.2 Emergency Containment

#### `POST /api/enterprise/organizations/{org_id}/authority/containment/emergency`
Triggers immediate durable lockdown and physical execution termination for an agent or entire organization.

- **Request Body:**
  ```json
  {
    "target_type": "AGENT",
    "target_id": "agent_worker_77",
    "containment_action": "TERMINATE",
    "reason": "Suspicious autonomous data exfiltration detected",
    "webauthn_assertion": {
      "challenge_id": "wp_step_f3b89c...",
      "clientDataJSON": "eyJ0eXBlIjoid2ViYXV0aG4uZ2V0Iiw...",
      "authenticatorData": "SZYN5YgOjGh0NBcPZhZgW4...",
      "signature": "MEQCIE...",
      "credentialId": "cred_apple_passkey_01"
    }
  }
  ```
- **Response (`200 OK` or `202 Accepted`):**
  ```json
  {
    "containment_id": "wp_cnt_894a2b...",
    "target_type": "AGENT",
    "target_id": "agent_worker_77",
    "containment_action": "TERMINATE",
    "status": "CONTAINED",
    "revocation_epoch": 4,
    "contained_at": "2026-10-15T18:40:00Z",
    "reconciliation_notes": "Physical process terminated and local tracking confirmed."
  }
  ```
- **Partial Failure / Remote Uncertainty (`200 OK` with truthful status):**
  ```json
  {
    "containment_id": "wp_cnt_894a2b...",
    "status": "UNRESOLVED",
    "revocation_epoch": 4,
    "reconciliation_notes": "Admission locked down, but remote execution worker confirmation is pending."
  }
  ```

---

### 2.3 M-of-N Quorum Recovery Management

#### `POST /api/enterprise/organizations/{org_id}/authority/recovery/requests`
Initiates a new M-of-N recovery request.

- **Request Body:**
  ```json
  {
    "request_type": "ROOT_RECOVERY",
    "target_root_id": "root_corp_01",
    "proposed_parameters": {
      "new_root_public_key": "MCowBQYDK2VwAyEA...",
      "scope_description": "Restore compromised root authority"
    },
    "required_quorum_m": 2,
    "eligible_quorum_n": 3,
    "ttl_seconds": 86400
  }
  ```
- **Response (`201 Created`):**
  ```json
  {
    "request_id": "wp_recov_10c8f...",
    "org_id": "org_enterprise_acme",
    "status": "PENDING",
    "action_digest": "4a7d1ed414474e4033ac29ccb8653d9b...",
    "required_quorum_m": 2,
    "approved_votes_count": 0,
    "created_at": "2026-10-15T18:40:00Z",
    "expires_at": "2026-10-16T18:40:00Z"
  }
  ```

#### `POST /api/enterprise/organizations/{org_id}/authority/recovery/requests/{request_id}/vote`
Casts an administrator vote on a pending recovery request.

- **Request Body:**
  ```json
  {
    "decision": "APPROVE",
    "action_digest": "4a7d1ed414474e4033ac29ccb8653d9b...",
    "notes": "Reviewed security incident report; approved",
    "webauthn_assertion": { ... }
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "vote_id": "wp_rvote_412e...",
    "request_id": "wp_recov_10c8f...",
    "decision": "APPROVE",
    "voted_at": "2026-10-15T18:41:00Z",
    "current_approved_count": 1,
    "quorum_met": false
  }
  ```

#### `POST /api/enterprise/organizations/{org_id}/authority/recovery/requests/{request_id}/execute`
Executes an approved recovery request after dynamic membership re-check.

- **Request Body:**
  ```json
  {
    "action_digest": "4a7d1ed414474e4033ac29ccb8653d9b...",
    "webauthn_assertion": { ... }
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "request_id": "wp_recov_10c8f...",
    "status": "EXECUTED",
    "executed_at": "2026-10-15T18:42:00Z",
    "new_root_id": "root_corp_02",
    "restored_authority_summary": "Customer root restored with approved parameters."
  }
  ```

---

### 2.4 Customer Root Ceremony & Status

- `POST /bootstrap/initiate` — Initiates the multi-factor root creation ceremony.
- `POST /bootstrap/complete` — Submits cryptographic root key and initial consent proof.
- `GET /bootstrap/reconcile` — Deterministically checks bootstrap completion state across reloads.
- `GET /status` — Returns complete organization authority status, active roots, agent delegations, and current tenant revocation epoch.
- `POST /root/{root_id}/revoke` — Revokes customer root authority and bumps tenant revocation epoch.
