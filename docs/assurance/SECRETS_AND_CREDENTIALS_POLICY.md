# Secrets and credentials policy (DRAFT for founder adoption)

Status: **draft**; applies to credentials the *project* uses to build, test, release and run the hosted service.

1. **Storage:** secrets live only in GitHub Actions encrypted secrets / environments or the hosting provider's secret
   store. Never in the repository, issues, logs, test fixtures, `.env` files committed to git or build artifacts.
   `gitleaks` runs on every change and on history.
2. **Prefer no secret:** package publishing uses OIDC trusted publishing and GitHub attestations; there is no
   long-lived PyPI token in the release path. New automation must use short-lived OIDC credentials where the target
   supports them.
3. **Least privilege:** workflow `GITHUB_TOKEN` permissions are declared per workflow/job and default to read-only.
4. **Access:** only the maintainer holds production and release credentials. MFA is required on the GitHub, PyPI and
   hosting accounts. **Founder responsibility:** the repository cannot verify this; any recurring check (for example
   quarterly) is a calendar commitment the founder must choose to make. None is claimed here.
5. **Rotation:** rotate on suspected exposure immediately. A fixed 12-month cadence is a **proposal pending founder
   commitment**. No single documented rotation procedure for the field-encryption key and webhook secrets exists yet;
   `docs/operations/runbooks/` covers incident-driven cases only.
6. **Exposure response:** revoke first, then assess use in logs, rotate dependents, record the incident
   (`docs/security/AUTH_INCIDENT_RESPONSE.md`), and add a regression check.
7. **Tests:** test credentials are generated per run or documented placeholders and are never valid elsewhere.
