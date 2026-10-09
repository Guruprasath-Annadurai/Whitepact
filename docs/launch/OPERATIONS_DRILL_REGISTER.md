# Operations drill register

Proposed objectives, not measured and not approved:

| Service | Proposed RTO | Proposed RPO | Measured |
| --- | --- | --- | --- |
| API and authorization | 15 minutes | 5 minutes | No |
| PostgreSQL | 30 minutes | 5 minutes | No |
| Evidence publication | 60 minutes | last fsynced object | No |
| Redis rate-limit state | 5 minutes | window may reset | No |

A process restart is not a restore. A fail-closed response during an
outage is required and is not service recovery.

| Drill | Result on this candidate |
| --- | --- |
| Health and readiness routes exist in the application | Code present. Not exercised on a deployed replica. |
| Redis shared limiter | Passed locally, one host, two clients. |
| Audit export and tenant scope | Passed against in-memory SQLite over HTTP. |
| Evidence publication reopen | Passed. A new log object read the same directory. |
| nftables egress negative test | Passed in a local network namespace. |
| nginx client-certificate rejection | Passed on local nginx. |
| Database backup and restore | Not run. |
| Evidence object restore | Not run. No object store. |
| Secret rotation on a deployed host | Key rotation passed in a temp directory only. |
| Node failure and multi-replica failover | Not run. |
| Alert delivery | Not run. |
| Incident escalation | Runbooks exist from earlier phases. No drill evidence was produced here. |

Live operational qualification remains blocked until those drills run on
the approved infrastructure and an independent reviewer sees the
evidence.
