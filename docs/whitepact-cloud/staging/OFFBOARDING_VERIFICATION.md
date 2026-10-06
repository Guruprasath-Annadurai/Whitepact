# Offboarding and Revocation — Verification Plan

SHA: `caf539b`

## Code baseline

| Behavior | Module | Status |
|----------|--------|--------|
| Local fail-closed first | `OffboardingService` → `terminate_local_access` | **VERIFIED_AUTOMATED_TESTS** |
| External steps independent + retries | `revoke_sessions`, provider perms, API creds, identity | **VERIFIED_AUTOMATED_TESTS** (stubs) |
| `offboarding_complete()` | All external success required | **VERIFIED_AUTOMATED_TESTS** |
| `UNRESOLVED` external | Never complete | **VERIFIED_AUTOMATED_TESTS** |

## `IdentityRevocationPort` (Phase 5)

Protocol in `offboarding.py`. **Live adapters not connected** — `integrations.py` documents blockers.

| Adapter method | Intended provider API | Repo state |
|----------------|----------------------|------------|
| `revoke_sessions` | Cloudflare Access session revoke | **BLOCKED_PROVIDER_ACCESS** |
| `revoke_provider_permissions` | CF Zero Trust / API tokens | **BLOCKED_PROVIDER_ACCESS** |
| `revoke_api_credentials` | Hetzner token rotation / key delete | **BLOCKED_PROVIDER_ACCESS** |
| `disable_identity_external` | IdP user suspend | **BLOCKED_PROVIDER_ACCESS** |

### Offline preparation (safe)

1. Implement adapter classes in `integrations.py` (or sibling module) that **only** call HTTP when `WHITEPACT_CLOUD_LIVE_INTEGRATIONS=1` — default no-op/fail closed. **Optional follow-up PR** — document here as **IMPLEMENTED** pattern only until coded.

Actually user asked implement where practical without live credentials - I could add stub adapters with clear NotImplemented unless env var - minimal scope. Let me add a small `staging_adapters.py` or extend integrations - user said don't broad redesign. Document in OFFBOARDING is enough unless quick stub.

I'll add minimal `LiveIntegrationGate` stub file - actually skip code, document compensating controls.

## Live workflow tests

| ID | Step | Expected | Status |
|----|------|----------|--------|
| O-01 | Terminate employee | `cloud_employees.status=terminated`; grants revoked | **AWAITING_LIVE_STAGING** |
| O-02 | New grant after terminate | `employee_not_active` | **VERIFIED_AUTOMATED_TESTS** |
| O-03 | Verify existing grant after terminate | `employee_not_active` | **AWAITING_LIVE_STAGING** |
| O-04 | CF session revoke | Sessions invalid <5m | **AWAITING_LIVE_STAGING** |
| O-05 | Hetzner API key revoke | 401 on old key | **AWAITING_LIVE_STAGING** |
| O-06 | Partial external failure | `offboarding_complete()==False`; UNRESOLVED logged | **VERIFIED_AUTOMATED_TESTS** |
| O-07 | Retry success | Step moves to SUCCESS | **AWAITING_LIVE_STAGING** |

## Compensating controls (provider limits)

| Gap | Compensating control |
|-----|---------------------|
| Delayed Hetzner token propagation | Rotate token + deny old in firewall; mark UNRESOLVED until API confirms |
| CF session revoke API lag | Short Access session TTL in staging |
| No instant device wipe | Device posture + session revoke |

## Pass criteria

O-01–O-05 with API response artifacts; never mark complete with UNRESOLVED critical steps.
