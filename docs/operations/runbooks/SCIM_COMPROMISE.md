# SCIM compromise / bad provisioning

**Trigger:** malicious SCIM token, mass deprovision, or privilege escalation attempt.

1. **Contain:** disable SCIM endpoint credentials; suspend affected principals.
2. **Verify:** SCIM cannot provision ROOT/OWNER (`test_iam_adversarial_matrix.py`, `test_m4_scim_adversarial_extension.py`).
3. **Recover:** replay-safe deprovision; revoke sessions and JIT grants (cascade in `ScimService.deprovision_user`).
4. **Evidence:** privileged audit log + SCIM user table snapshot (non-prod).
5. **Escalate:** tenant-wide revocation epoch bump if stale authority suspected.
