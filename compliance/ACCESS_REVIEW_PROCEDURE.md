# WhitePact Privileged Access Review Procedure

**Status:** Adopted first-party operating procedure  
**Effective date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner  
**Cadence:** Quarterly and on privileged-personnel/role changes

## Purpose

Ensure privileged access to WhitePact source, release, hosted-service, database, infrastructure and administrative systems remains necessary, least-privileged and attributable.

## Scope

Review, where applicable:

- GitHub repository administration/write permissions;
- CI/CD and release publishing authority;
- production hosting/admin access;
- database administration/service credentials;
- Redis/cache administration where privileged;
- DNS/domain administration;
- organization Owner/Admin roles in WhitePact;
- production API keys/service identities with privileged scopes;
- security/monitoring/vendor administration accounts;
- cryptographic signing/key custodianship metadata (never expose private key material in review evidence).

## Review steps

1. Export or inspect the current privileged-identity list from each in-scope system.
2. Confirm each identity still belongs to an authorized person/service.
3. Confirm role/scope is the minimum necessary for current duties.
4. Identify stale, duplicate, shared or unused privileged credentials.
5. Revoke/downgrade access that is no longer justified.
6. Confirm MFA/SSO requirements where supported and applicable.
7. Review service/machine identities separately from human identities.
8. Record exceptions and residual risk; Critical/High exceptions require explicit owner treatment.
9. Preserve dated review evidence without committing secrets or sensitive credential values.

## Required evidence record

```text
Review date:
Reviewer:
Systems reviewed:
Privileged identities reviewed (names/IDs only; no secrets):
Access removed/downgraded:
Exceptions:
Risk acceptance / corrective actions:
Next scheduled review:
Secure evidence location:
```

## Solo-maintainer limitation

At the current team size, the maintainer may be reviewing access they themselves hold. This procedure creates traceable discipline but is not independent oversight or segregation of duties. That limitation remains recorded in the risk register until another authorized reviewer exists.

## Triggered review

Run an out-of-cycle review after:

- maintainer/employee/contractor onboarding or offboarding;
- suspected credential compromise;
- material role change;
- new production vendor/infrastructure;
- major security incident;
- certification/audit scoping request;
- discovery of an unmanaged privileged account.

## Claim boundary

The existence of this procedure means WhitePact has an adopted privileged-access review process. Evidence that it operates over time must come from real dated reviews captured under `compliance/OPERATING_EVIDENCE_REGISTER.md`.
