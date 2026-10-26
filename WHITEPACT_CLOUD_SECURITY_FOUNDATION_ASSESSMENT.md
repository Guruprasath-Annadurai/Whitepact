# WHITEPACT — CLOUD SECURITY FOUNDATION ASSESSMENT

**Document ID:** WP-M12S-CLOUD-011  
**Classification:** CLOUD ARCHITECTURE & ENTERPRISE SECURITY ASSESSMENT  
**Audience:** Cloud Architects, SRE Leads, Compliance Officers  
**Expenditure Cap:** ₹0 / $0 (strictly zero unapproved expenditure)  
**Status:** QUALIFIED FOR PRIVATE VPC / STAGING INTEGRATION

---

## 1. ZERO-EXPENDITURE MANDATE & CLOUD QUALIFICATION

In accordance with Executive Directive M12-S, all security qualification and development activities were conducted with **strictly zero cloud expenditure** ($0 / ₹0). No unapproved cloud clusters, RDS instances, S3 buckets, or external compute instances were provisioned.

All testing and verification were executed within isolated local containerized worktrees leveraging local PostgreSQL 16 and Redis instances.

---

## 2. CLOUD FOUNDATION ARCHITECTURE & CONTROLS

When deployed to production cloud environments (AWS, GCP, Azure, or Private Sovereign VPC), WhitePact enforces the following baseline architecture:

```
[Internet Traffic]
       |
       v (TLS 1.3 / mTLS / WAF)
+-------------------------------------------------------------+
|               Cloud Load Balancer / API Gateway             |
+-------------------------------------------------------------+
       |
       v (Private VPC Subnet)
+-------------------------------------------------------------+
|              WhitePact Runtime API Nodes (FastAPI)           |
|  - Stateless compute                                        |
|  - Runs as non-root unprivileged container user             |
|  - Environment secrets mounted via Vault / AWS Secrets Mgr  |
+-------------------------------------------------------------+
       |                           |
       v (Encrypted TLS)           v (Encrypted TLS)
+-----------------------+   +---------------------------------+
| Managed PostgreSQL 16 |   | Redis Cluster (Rate Limit/Cache)|
| - KMS AES-256 Storage |   | - In-transit TLS                |
| - Row-Level Security  |   | - Auth password protected       |
| - Point-in-Time Backup|   +---------------------------------+
+-----------------------+
```

---

## 3. SECURITY CONTROL INVARIANTS

### 3.1 Data-at-Rest Encryption
- Sensitive database columns (including `governance_approvals.arguments`, API keys, and private delegation constraints) use SQLAlchemy `EncryptedString`.
- Encryption is performed application-side using AES-256-GCM with authenticated keys derived from the master encryption key (`WHITEPACT_ENCRYPTION_KEY`).
- Database administrators or compromised database dumps cannot read raw arguments, personal identifiable information (PII), or payload secrets.

### 3.2 Zero-Trust Egress Architecture
- Containers executing agent tools operate under `--network none` by default.
- If an agent tool requires external API access (e.g., webhook or upstream REST API):
  - Egress is routed through an explicit forward proxy with DNS allowlisting (`DNS_EGRESS_SECURITY_CLOSURE.md`).
  - Access to cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`) is strictly dropped at the routing firewall.

### 3.3 Immutability of Audit Trails
- `enterprise_audit_log` is structurally append-only.
- PostgreSQL database roles for the application runtime are granted `INSERT` and `SELECT` privileges only; `UPDATE`, `DELETE`, and `TRUNCATE` are revoked on all audit and governance ledger tables.
- Audit logs are streamed continuously to WORM (Write-Once-Read-Many) cloud storage (e.g., AWS S3 with Object Lock in Compliance Mode).

---

## 4. PRE-DEPLOYMENT GATES FOR CLOUD STAGING

Before opening cloud staging in Milestone M13, the following gates must be completed:
1. Automated deployment via vetted Terraform / OpenTofu modules with zero public database exposure.
2. KMS key rotation policy established and verified.
3. Multi-AZ database failover simulation with active traffic.
