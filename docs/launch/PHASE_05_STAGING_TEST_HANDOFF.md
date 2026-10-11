# Phase 5 — Staging test handoff

Execute on the successor SHA after its CI is green and the owner has approved staging. Do not execute against production.

## Identity and tenancy

1. Register two users in two organizations.
2. Confirm each session cookie is rejected by the other organization.
3. Invite a member, accept, then revoke. The revoked member's next call is denied.
4. Reset a password. The reset token fails on second use and existing sessions are revoked.

## Authority

5. Register an agent under org A with `memory_scope` `org:a`.
6. Attempt to delegate `memory_scope` `org`. Expect deny `DELEGATION_AUTHORITY_ESCALATION`.
7. Delegate `org:a:agent:1`. Expect the attenuation check to pass, then the action-time scope check to apply.
8. Issue a short-lived grant, execute once, replay the grant, and confirm the replay is denied.
9. Wait until expiry or use a fixture clock if the product supports it. Expired grant is denied.
10. Ask a human approver to reject a high-risk action. The action does not run.

## Failure

11. Stop PostgreSQL. Readiness becomes not ready. No tool execution is reported as success.
12. Restore PostgreSQL. A new grant works. The replayed old grant still fails.

Record the SHA, the organization ids (not secrets), and the deny reason codes.

## Gate

NOT EXECUTED. This is a handoff.
