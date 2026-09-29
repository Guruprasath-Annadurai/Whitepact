# WhitePact Cloud

Internal zero-trust privileged-access and multicloud security control plane. **Not** exposed to public customers.

| Doc | Topic |
|-----|--------|
| [01_ARCHITECTURE.md](01_ARCHITECTURE.md) | Control plane vs production app |
| [02_IDENTITY_AND_EMPLOYEE_KEYS.md](02_IDENTITY_AND_EMPLOYEE_KEYS.md) | Passkeys, enrollment, revocation |
| [03_MULTICLOUD_ACCESS_GOVERNANCE.md](03_MULTICLOUD_ACCESS_GOVERNANCE.md) | Hetzner, Cloudflare, GCP IAM |
| [04_PRIVILEGED_ACCESS.md](04_PRIVILEGED_ACCESS.md) | JIT grants, roles, approvals |
| [05_NETWORK_ISOLATION.md](05_NETWORK_ISOLATION.md) | Tiers, nftables, egress |
| [06_SECRETS_AND_CRYPTOGRAPHY.md](06_SECRETS_AND_CRYPTOGRAPHY.md) | Keys, rotation, separation |
| [07_THREAT_MODEL.md](07_THREAT_MODEL.md) | Adversary assumptions |
| [08_SECURITY_MONITORING.md](08_SECURITY_MONITORING.md) | Logging and alerts |
| [09_INCIDENT_RESPONSE.md](09_INCIDENT_RESPONSE.md) | Playbooks |
| [10_DISASTER_RECOVERY.md](10_DISASTER_RECOVERY.md) | R2 primary, optional GCS |
| [11_SECURITY_TEST_RESULTS.md](11_SECURITY_TEST_RESULTS.md) | 25-scenario matrix |
| [12_COST_AND_OPERATIONS.md](12_COST_AND_OPERATIONS.md) | Monthly estimate |
| [13_PRODUCTION_READINESS.md](13_PRODUCTION_READINESS.md) | Gate checklist |

Implementation code: `src/responsibleai/whitepact_cloud/`. Infrastructure: `infra/terraform/`.
