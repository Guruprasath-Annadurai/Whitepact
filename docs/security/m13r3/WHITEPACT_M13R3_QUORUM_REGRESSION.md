# WHITEPACT M13-R3 QUORUM REGRESSION

**Milestone:** M13-R3  
**Vulnerability Class:** Stale Role Authorization / Quorum Integrity Bypass  
**CWE:** CWE-285 (Improper Authorization), CWE-287 (Improper Authentication)  
**Status:** FULLY REMEDIATED & PROVEN

---

## 1. Problem Definition

In earlier M13 implementations, an administrator's vote on an M-of-N root recovery request was recorded with their current role at voting time. However, if an administrator voted to approve a root rotation or sovereign recovery request and was subsequently:
- Demoted from `ADMIN`/`OWNER` to `MEMBER`,
- Deactivated / Suspended, or
- Removed entirely from the organization membership table,

the subsequent recovery execution routine counted the vote based solely on historical validity, allowing unauthorized or demoted individuals to influence sovereign recovery decisions.

---

## 2. Dynamic Pre-Execution Quorum Validation

In `CustomerAuthorityService.execute_recovery_request`, the quorum enforcement logic performs a fresh, dynamic membership and role query inside the serialized recovery transaction:

```python
# 1. Fetch all APPROVE votes
votes = (
    await conn.execute(
        select(authority_recovery_votes).where(
            and_(
                authority_recovery_votes.c.request_id == request_id,
                authority_recovery_votes.c.decision == "APPROVE",
            )
        )
    )
).fetchall()

# 2. Dynamic recheck: Ensure all approving voters are still active admins/owners of org_id!
valid_approver_ids: list[str] = []
seen_voters: set[str] = set()
for v in votes:
    voter_id = v.voter_user_id
    if voter_id in seen_voters:
        continue
    seen_voters.add(voter_id)

    # Anti-self-approval recheck
    if voter_id == req["requester_user_id"]:
        continue

    mem = (
        await conn.execute(
            select(web_memberships).where(
                and_(
                    web_memberships.c.user_id == voter_id,
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.status == "ACTIVE",
                    web_memberships.c.role.in_(["OWNER", "ADMIN", "owner", "admin"]),
                )
            )
        )
    ).first()
    if mem:
        valid_approver_ids.append(voter_id)

if len(valid_approver_ids) < req["required_quorum_m"]:
    raise quorum_not_met(
        f"Quorum threshold {req['required_quorum_m']} not satisfied (active verified approvals: {len(valid_approver_ids)})."
    )
```

### Invariants Enforced:
1. **Dynamic Eligibility:** Historical votes cast by users whose current role is not `OWNER` or `ADMIN` are strictly excluded from the quorum tally.
2. **Anti-Self-Approval:** The requester of the recovery cannot vote for or count toward their own recovery threshold.
3. **Voter Deduplication:** Multiple votes by the same user ID are deduplicated and count as at most 1 vote.
4. **Action Digest Binding:** The action digest computed over the requested parameters must match the approved digest.
5. **Cross-Tenant Isolation:** Queries strictly filter by `org_id`.

---

## 3. Empirical Test Evidence

Dedicated tests in `tests/test_m13r3_security_regression.py` and `tests/test_m12fs_root_hardening.py` were run against PostgreSQL and SQLite:

1. `test_quorum_role_demotion_invalidates_recovery`:
   - Setup: 2-of-3 quorum requirement (Owner Alice, Admin Bob, Admin Charlie).
   - Action: Bob and Charlie vote APPROVE. Quorum threshold 2 is met.
   - Mutation: Charlie is demoted to `MEMBER`.
   - Execution Attempt: Alice attempts `execute_recovery_request`.
   - Outcome: **QUORUM_NOT_MET raised (`Quorum threshold 2 not satisfied (active verified approvals: 1)`).**
2. `test_quorum_anti_self_approval_and_duplicate_voting`:
   - Alice attempts to approve her own request: **SELF_APPROVAL_BLOCKED**.
   - Bob votes twice: Second vote rejected with **ALREADY_VOTED**.
   - Quorum count with 1 valid voter fails threshold requirement: **QUORUM_NOT_MET**.
3. `test_quorum_pre_execution_deactivation_check`:
   - Approver account disabled before execution: Approval invalidated, execution rejected.
