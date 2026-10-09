# API key / session compromise

**Trigger:** leaked key, stolen laptop, or suspicious session activity.

1. **Contain:** revoke the named API key or terminate web sessions for the user/org.
2. **Verify:** check approvals and execution authorizations issued during exposure window; deny pending risky actions.
3. **Recover:** issue replacement keys; require MFA re-enrollment if TOTP implicated.
4. **Evidence:** export audit trail for the interval; attach evidence IDs to incident ticket.
5. **Escalate:** if cross-tenant access suspected, follow `INCIDENT_RESPONSE.md` and freeze org integrations.
