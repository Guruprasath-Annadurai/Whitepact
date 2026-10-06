# Identity and Employee Keys

## Requirement

Every authorized employee has an **individual** internal identity and **individually revocable** credentials. Prefer **WebAuthn/FIDO2** passkeys; hardware security keys for highly privileged roles.

## Enrollment record (logical model)

- `employee_id` (unique)
- Registered passkey credential IDs (public key only on server)
- `CloudRole` assignment (`src/responsibleai/whitepact_cloud/roles.py`)
- Explicit resource permissions via JIT grants
- Account status: `active` | `suspended` | `terminated`
- Audit correlation on enrollment changes

**Never** store private passkey material on WhitePact servers.

## Session security

- Short-lived admin sessions (target: ≤8h, sensitive actions require step-up)
- Centralized session revocation on offboarding (`offboarding.py`)
- Reauthentication for sensitive operations

## Offboarding

`run_offboarding()` orchestrates: disable identity → revoke sessions → revoke grants → remove provider permissions → revoke API credentials. **Must not** rely on TTL alone.

## Implemented vs documented

| Capability | Status |
|------------|--------|
| Cloudflare Access JWT validation (exact issuer + JWKS) | **VERIFIED** (`access_gateway.py`, unit tests) |
| Employee passkey / WebAuthn enrollment UI | **NOT IMPLEMENTED** — requires IdP (Access) + future enrollment API |
| Hardware security key enforcement | **OWNER_APPROVAL_REQUIRED** (Access device posture + live IdP) |
| Per-employee DB identity row (`cloud_employees`) | **VERIFIED** (migration `0062`, PostgreSQL tests) |

## Status

| Control | Status |
|---------|--------|
| Role/permission model | VERIFIED (code) |
| WebAuthn enrollment service | BLOCKED (no live IdP connection in repo) |
| Device trust policies | OWNER_APPROVAL_REQUIRED |
