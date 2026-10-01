# Privileged Access

## Roles

`OWNER`, `SECURITY_ADMIN`, `PLATFORM_ENGINEER`, `DEVELOPER`, `SECURITY_AUDITOR`, `BACKUP_OPERATOR` — enforced in `role_allows()`, not UI labels alone.

## JIT administrative grants

`issue_admin_grant()` binds:

- Employee identity, operation, provider, target resource
- Permission set, policy id, approval decision
- Expiry, execution id, audit correlation id
- HMAC signature over canonical grant bytes

`verify_admin_grant()` at automation boundary: signature, expiry, revocation, replay (`consumed`).

## Founder-only stage

Sensitive operations require `approved_by` or explicit `founder_only_exception=True` with independent audit evidence. Dual control when additional personnel join.

## Gateway vs application auth

Cloudflare Access JWT validated in `access_gateway.py` (issuer, audience, exp). **Forwarded identity headers are not trusted.**

## Status

| Control | Status |
|---------|--------|
| Grant issue/verify | VERIFIED (unit tests) |
| Provider credential binding | IMPLEMENTED_NOT_DEPLOYED |
| Dual control | OWNER_APPROVAL_REQUIRED (headcount) |
