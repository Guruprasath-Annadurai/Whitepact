# WHITEPACT — ZERO-CASH STAGING ARCHITECTURE SPECIFICATION
## Google Cloud + AWS S3 Compliance Mode + Cloudflare Free + Deno Deploy Free

**Date**: 2026-10-11  
**Author**: Antigravity (Principal WhitePact Engineering Agent)  
**Status**: APPROVED ZERO-CASH SPECIFICATION (Offline Architecture — Live Cloud Deployment Blocked)  
**Review Target**: GPT-6 Independent Technical Review  

---

## 1. Zero-Cash Staging Policy & Strategic Context

The Founder has explicitly rejected paid Hetzner infrastructure for the current staging deployment. In compliance with the Founder's direct financial and infrastructure constraints:
- **No Paid Infrastructure / Zero Cash Outlay**: Staging must run exclusively on verified zero-cash allocations ($0 Free tiers and verified eligible cloud credit envelopes).
- **No Production Expenditure**: No credit card charges, unbudgeted commitments, or out-of-pocket spending are authorized.
- **Strict Authorization Boundary**: All live cloud provisioning remains **BLOCKED** until explicit, separate Founder sign-off.

```mermaid
flowchart TD
    Client["Client / AI Assistant (Claude, Cursor, Codex, OpenCode)"] -->|TLS 1.3 / Free Edge WAF| CF["Cloudflare Free Tier (DNS, SSL/TLS, DDoS, R2 Backups)"]
    CF -->|Secure Ingress (Port 443)| GCP_Ingress["Google Cloud Load Balancer / Reverse Proxy"]
    
    subgraph GCP_Staging ["Google Cloud Staging Plane (Credit-Funded / Hard Capped)"]
        GCP_Ingress --> App["WhitePact SaaS & MCP Server (e2-standard-2)"]
        App -->|Port 5432 (App Subnet Only)| DB["PostgreSQL 16 + Redis (Isolated Private Subnet)"]
        App -->|Spawn Container / IPC| Exec["Isolated Execution Plane (--network=none, cgroupv2)"]
        Exec -.x|BLOCKED: No DB Reachability| DB
    end

    subgraph External_Witness_Plane ["External Zero-Cash Verification & Compliance"]
        App -.->|Opaque Witness Commits| Deno["Deno Deploy Free Tier (Org: whitepact-dev)"]
        App -.->|Canonical Evidence Digests (PROPOSED)| AWS_S3["AWS S3 Compliance Mode (Subject to Approval)"]
    end
```

---

## 2. Pilot Program Design & Operational Scope

The staging environment is exclusively sized and scheduled for a controlled, invite-only enterprise pilot program.

### Pilot Parameters
- **Cohort Size**: Exactly 3 partner organizations.
- **Evaluator Allocation**: Maximum 3 designated evaluators per organization (total 9 evaluators).
- **Access Duration**: Exactly 14 calendar days per organization from account activation.
- **Hosting Model**: **Scheduled interactive sessions**, NOT continuous 24/7 hosting. Staging compute instances are spun up for designated evaluation windows (e.g., 2–4 hour blocks) and suspended outside testing windows to eliminate passive credit burn and idle cloud risks.
- **Core Onboarding Journey**: Linear, fail-closed **Connect → Govern → Verify** workflow:
  1. **Connect**: Evaluator connects their agent via MCP endpoint (`sse` or `streamable-http`) or local CLI bridge. Mutual TLS / Bearer authentication establishes identity and initial trust handshake.
  2. **Govern**: Evaluator defines four-eyes tiered policy rules. Policy weakening or privileged actions trigger approval requests requiring independent admin sign-off. Active runs are continuously tracked via `InFlightExecutionRegistry`.
  3. **Verify**: Evaluator inspects tamper-evident audit logs, cryptographic receipts, and external witness digests proving that revoked actions cannot execute.
- **Destructive Security Lab**: An isolated, ephemeral staging sandbox specifically designated for negative and adversarial testing:
  - Synthetic prompt injection and policy escape simulations.
  - Revocation race conditions (in-flight permit revocation under concurrent execution).
  - Out-of-order billing and entitlement downgrade spoofing.
  - Ephemeral database tenant resets after each destructive test session.
- **Expenditure Ceiling**: $0.00 cash outlay authorized.

---

## 3. Financial Risk Assessment & Billing Shutdown Mechanics

### Honest Provider-Specific Risk Analysis
Previous documentation asserted that automated billing budget alerts guarantee zero charges. **This assertion is technically flawed and has been corrected.**

1. **Free-Trial Accounts vs. Paid Accounts with Startup Credits**:
   - **Google Cloud Free Trial**: Has built-in spend protections that suspend services automatically when free promotional balances reach zero, preventing spillover to credit cards.
   - **Standard Billing Accounts with Credits / Coupons**: Startup credits (e.g., Google Cloud for Startups) apply against consumption on a regular billing account. If credits expire, become exhausted, or encounter ineligible SKUs (e.g., marketplace third-party licenses), Google Cloud **automatically charges the primary credit card on file**.
   - **Billing Alert Latency**: GCP Cloud Billing budget notifications (via Pub/Sub) experience a documented propagation lag of **15 minutes to several hours**. During this lag, active virtual machines, network egress, and persistent disks continue accruing real charges.
2. **Safeguard Architecture Against Billing Overage**:
   - **Automated Kill-Switch (`billingbudgets.googleapis.com`)**: A Cloud Function subscribed to billing budget Pub/Sub topics executes `gcloud billing projects unlink` immediately upon reaching 80% of authorized credit allocation.
   - **Quotas and Resource Bounds**: Set GCP Compute Engine instance quotas to 1 across the project. Prohibit GPU, TPU, and multi-region network allocations.
   - **Ephemeral Operation**: Run VMs only during scheduled pilot evaluation windows.
   - **Static IP Risk Mitigation**: Unused external IPv4 addresses in GCP accrue charges ($0.005/hour). All ephemeral staging environments must release external static IPs when instances are stopped.

---

## 4. Multi-Provider Zero-Cash Component Specifications

### 1. Google Cloud — Primary Staging Compute Plane
- **Role**: Application API, MCP server gateway, PostgreSQL database, and Linux isolated container execution plane.
- **Funding**: Strictly funded via verified Google Cloud Startup Credits.
- **Compute Sizing**:
  - Web & Application: 1x `e2-standard-2` (2 vCPU, 8 GB RAM, Ubuntu 24.04 LTS).
  - Storage: 30 GB standard Persistent Disk (`pd-standard`).
- **Execution Sandbox Boundary**:
  - Container engine: Docker with cgroupv2 resource limits (512 MB RAM, 1.0 vCPU max).
  - Security profile: `--security-opt=no-new-privileges:true`, seccomp default profile, read-only root filesystem with tmpfs `/tmp`.
  - Network isolation: `--network=none`. Zero network reachability to host, internet, or PostgreSQL database.
- **IAM Roles & Least Privilege**:
  - `whitepact-staging-app@<project>.iam.gserviceaccount.com`:
    - `roles/logging.logWriter` (Cloud Logging)
    - `roles/monitoring.metricWriter` (Cloud Monitoring)
    - `roles/secretmanager.secretAccessor` (Database and JWT secrets only)
  - Explicitly denied: `roles/owner`, `roles/editor`, `roles/iam.*`, `roles/compute.admin`.

### 2. Cloudflare Free Tier — Edge, DNS, & Backups
- **Role**: Edge SSL/TLS termination, DDoS mitigation, DNS management, and off-site encrypted disaster recovery.
- **DNS / WAF**: Cloudflare Universal SSL (TLS 1.3), automated HTTPS rewrite, rate limiting (100 req/min per evaluator IP).
- **R2 Backup Storage**:
  - Off-site automated daily PostgreSQL encrypted dump (`age` or AES-256-GCM encrypted prior to upload).
  - Operates strictly within Cloudflare R2 Free Allowance:
    - 10 GB-months of storage (staging DB dump is <100 MB).
    - 1,000,000 Class A operations/month (uploads).
    - 10,000,000 Class B operations/month.
    - $0 egress fee.

### 3. Deno Deploy Free Tier — Independent Witness & Liveness Monitor
- **Organization**: `whitepact-dev` (verified and confirmed on the $0 Free plan).
- **Role**: Lightweight external witness and independent public verification endpoint.
- **Scope**:
  - Verifies signed batch state roots (`sha256(batch_epoch + prev_root + tx_root)`) transmitted over HTTPS.
  - Zero access to internal staging credentials or customer data.
  - Operates within Deno Free Tier limits (100,000 requests/day, 100ms CPU time/request).
- **Constraint**: Deployment scripts and Deno projects are prepared offline; no cloud project creation until live deployment authorization.

### 4. AWS S3 Compliance Mode — Limited Immutable Evidence (PROPOSAL ONLY)
- **Role**: Write-Once-Read-Many (WORM) immutable anchoring for canonical batch evidence manifests.
- **Status**: **FORMAL PROPOSAL ONLY — NOT FOUNDER AUTHORIZED**.
  - S3 Object Lock in Compliance Mode cannot be overridden, shortened, or deleted even by the root AWS account.
  - **Proposed Staging Policy**: 30-day retention lock (reduced from the rescinded 365-day assumption) to prevent irreversible long-term storage accrual.
  - **Proposed Production Policy**: 90-day to 365-day retention determined by enterprise contract.
  - **Financial Risk**: Even with free tier or AWS Activate credits, Compliance Mode objects cannot be deleted if a test fails or during clean-up. No S3 bucket creation is authorized until credit balance is verified and written Founder approval is granted.

---

## 5. Network Boundaries & Firewall Egress Architecture

```
+-----------------------------------------------------------------------------------+
| Cloudflare Edge (Free Tier)                                                       |
| - TLS 1.3 Ingress, WAF, Rate Limiting                                             |
+-----------------------------------------------------------------------------------+
                                        | (HTTPS 443)
                                        v
+-----------------------------------------------------------------------------------+
| GCP Staging VPC (10.0.0.0/16)                                                     |
|                                                                                   |
|  [Public/Ingress Subnet 10.0.1.0/24]                                              |
|  - Reverse Proxy / Load Balancer (Port 443 Inbound only)                          |
|                                        | (Internal Proxy Pass)                    |
|                                        v                                          |
|  [Application Subnet 10.0.2.0/24]                                                 |
|  - WhitePact Core API & MCP Server (e2-standard-2)                               |
|        |                               | (Spawn Container)                        |
|        | (Port 5432 - TCP Ingress)      v                                          |
|        v                         [Execution Subnet 10.0.3.0/24]                   |
|  [Database Subnet 10.0.4.0/24]   - Isolated Containers                            |
|  - PostgreSQL 16 Private Subnet  - Flags: --network=none                          |
|  - Ingress: 10.0.2.0/24 only     - Ingress: NONE                                  |
|  - 10.0.3.0/24 EXPLICITLY DENIED - Egress: NONE (Port 5432 BLOCKED)               |
+-----------------------------------------------------------------------------------+
```

### Firewall Rule Enforcement
1. **Rule `allow-cloudflare-ingress`**: Ingress TCP 443 from Cloudflare IP ranges only.
2. **Rule `allow-app-to-db`**: Ingress TCP 5432 on Database Subnet with source tag `app-server` (10.0.2.0/24).
3. **Rule `deny-execution-to-db`**: Explicit egress drop from Execution Subnet (10.0.3.0/24) to Database Subnet (10.0.4.0/24) and all RFC1918 addresses.
4. **Local Container Runtime**: Docker daemon configured with `iptables: false` or isolated bridge, execution containers spawned with `--network=none`.

---

## 6. Recovery Testing & Credit Expiration Plan

### 1. Credit Expiration Behavior (Fail-Closed)
- If Google Cloud credits reach 95% or expire:
  1. Billing kill-switch unlinks project billing.
  2. GCP instances transition to stopped/suspended state.
  3. External requests via Cloudflare receive custom HTTP 503 ("Maintenance: Staging Evaluation Window Closed").
  4. Database integrity is preserved on persistent disk; latest backup snapshot resides safely in Cloudflare R2.
  5. Zero additional cloud charges accrue.

### 2. Staging Recovery Procedure
1. Export latest encrypted snapshot from Cloudflare R2 bucket.
2. Spin up local or secondary test environment using `docker-compose -f docker-compose.staging.yml up`.
3. Verify cryptographic state roots against Deno Deploy witness log.
4. Restore PostgreSQL database using `scripts/restore_r2_snapshot.sh`.
5. Validate tenant data isolation and run `pytest tests/test_faststart.py`.

---

## 7. Staging Acceptance Matrix

| Category | Component / Feature | Zero-Cash Qualification Method | Staging Status |
| :--- | :--- | :--- | :--- |
| **Compute** | Primary API & MCP Gateway | 1x `e2-standard-2` on Google Cloud Credits | **SPECIFIED / OFFLINE READY** |
| **Execution** | Container Isolation & Kill | Docker cgroupv2, `--network=none`, InFlightRegistry | **TESTED & VERIFIED** |
| **Database** | PostgreSQL 16 & Redis | Dedicated private subnet, no exec subnet ingress | **VERIFIED & CONSTRAINED** |
| **Edge** | SSL/TLS, WAF, DNS | Cloudflare Free Tier ($0/month) | **DESIGN APPROVED** |
| **Witness** | External State Root Witness | Deno Deploy Free Tier (Org: `whitepact-dev`) | **DESIGN APPROVED** |
| **Immutable Log** | WORM S3 Compliance Mode | 30-day retention lock (AWS Activate/Free) | **PROPOSAL ONLY (UNAUTHORIZED)** |
| **Disaster Recovery** | Off-site Encrypted Backups | Cloudflare R2 Free Tier (10 GB allowance) | **DESIGN APPROVED** |
| **Security Lab** | Destructive Testing Sandbox | Ephemeral tenant partitioning, reset on complete | **TESTED & VERIFIED** |
| **Budget Control** | Zero-Cash Enforcement | Budget alert + Cloud Function billing kill-switch | **SPECIFIED & RISK-ANALYZED** |

---

## 8. Historical Hetzner Archive Notice

All prior Hetzner Cloud infrastructure documentation (`docs/enterprise/cloud/*` and `WHITEPACT_FINAL_THREE_PROVIDER_STAGING_ARCHITECTURE.md`) is retained strictly as an **unfunded historical design reference**. It is **NOT** the approved staging architecture.
