# M13 Final Customer Journey Diagnosis

**Assigned Agent:** Antigravity FORTRESS  
**Role:** Principal Security Architect & Integration Debugger  
**Date:** October 19, 2026  
**Milestone:** WhitePact M13  
**Target:** `real-customer-journey` Workflow (Stage 17: `POST /api/web/api-keys`)  
**Status:** DRAFT • M13 OPEN • GLOBAL PRODUCTION NO-GO • RELEASE AUTHORIZATION NOT GRANTED

---

## 1. Executive Summary

In the integrated M13 candidate (PR #223), the `real-customer-journey` test fails at Stage 17 when attempting to issue an API key via `POST /api/web/api-keys`, returning HTTP `403 Forbidden`.

This document diagnoses the exact authentication and authorization failure mechanism, demonstrates why this failure is outside the authorized Recovery Zero scope, and provides Codex with the necessary guidance to resolve the issue without compromising WhitePact's security invariants.

---

## 2. Failure Analysis

### Stage 17 Execution Trace:
- Endpoint: `POST /api/web/api-keys`
- Payload: `{"name": "test-key", "scopes": ["governance:read", "execution:write"]}`
- Response: `403 Forbidden`
- Body: `{"detail": "Interactive session required for API key generation or elevation"}`

### Root Cause:
1. Under WhitePact M12/M13 security policies, the API key creation endpoint (`/api/web/api-keys`) requires a verified interactive session with authenticated owner credentials (A2 / WebAuthn).
2. In the `real-customer-journey` script, earlier stages perform login and obtain a session cookie or token, but the session authentication context lacks the elevated role / WebAuthn User Verification required to issue scoped programmatic credentials.
3. The server correctly enforces fail-closed authorization: an unverified session cannot generate programmatic credentials.

---

## 3. Scope Boundary & Architectural Guidance for Codex

### Why Antigravity Must NOT Modify Customer Journey Logic:
- The CTO Directive explicitly specifies:
  > "Preserve A2/WebAuthn security policies. Do not bypass WebAuthn UV in root tests. Codex owns final M13 integration."
- Bypassing the 403 check by disabling authentication requirements or relaxing the WebAuthn UV enforcement would violate WhitePact's core constitutional invariant.

### Recommended Fix for Codex (PR #223):
In the customer journey test harness (`scripts/engineering/reproducers/` or test client setup):
1. Ensure the customer journey establishes an authenticated session that includes the requisite owner authorization context or simulates the verified interactive WebAuthn ceremony used in the web portal.
2. In test fixtures, utilize the authenticated session helper that attaches verified credentials rather than a bare bearer token.
3. Do not lower server-side authorization requirements to mask test fixture omissions.
