# Secrets and Cryptography

- No secrets in Git, CI artifacts, or images.
- Terraform state: remote backend with encryption (configure at apply; not committed).
- Separate keys: production authorization signing vs infrastructure admin vs backup encryption.
- Admin grant HMAC keys rotated on compromise (procedure in `09_INCIDENT_RESPONSE.md`).
- Use provider and library crypto only — no custom algorithms.

**Status:** IMPLEMENTED_NOT_DEPLOYED (patterns documented; vault backend OWNER_APPROVAL_REQUIRED).
