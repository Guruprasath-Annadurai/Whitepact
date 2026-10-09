# Incident response (operator)

**Trigger:** suspected compromise, data leak, abusive execution, or unexplained governance bypass attempt.

1. **Contain:** disable affected org API keys and sessions via dashboard admin; bump revocation epoch if org-scoped (`governance_revocation_epochs`).
2. **Verify:** inspect audit export + evidence IDs for the window; confirm no `EXECUTED` without matching grant.
3. **Recover:** rotate credentials per `CREDENTIAL_COMPROMISE.md`; re-run security smoke (`tests/test_m3_adversarial_security_campaign.py` in staging).
4. **Evidence:** preserve SIEM batches and DB snapshots (non-production restore drill only).
5. **Escalate:** founder + security lead; do not merge emergency code without review.
