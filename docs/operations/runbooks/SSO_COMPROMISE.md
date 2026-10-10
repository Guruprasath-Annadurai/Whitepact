# SSO / IdP compromise

**Trigger:** forged assertion, tenant mismatch, or IdP key compromise suspected.

1. **Contain:** disable affected IdP binding; require step-up for privileged actions.
2. **Verify:** audit SSO logins; compare `ENTRA_TENANT_MISMATCH` / issuer failures in tests (`test_enterprise_layer2_identity_security.py`).
3. **Recover:** rotate IdP client secrets; re-bind verified domains only.
4. **Evidence:** export identity security notifications and audit rows for incident window.
5. **Escalate:** if cross-tenant mapping suspected, invoke `INCIDENT_RESPONSE.md`.
