# WHITEPACT — FINAL THREE-PROVIDER STAGING ARCHITECTURE SPECIFICATION
## Hetzner Cloud + Cloudflare Enterprise Edge + AWS S3 Compliance Mode

**Date**: 2026-10-11  
**Author**: Antigravity (Principal WhitePact Engineering Agent)  
**Status**: Architecture Design Finalized (Offline Validation Complete — Provisioning Blocked)  

---

## 1. Executive Summary & Design Principles

WhitePact enforces the doctrine:
> **"The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority."**

The finalized hosting architecture distributes trust and infrastructure boundaries across three specialized providers:
1. **Hetzner Cloud (EU)**: Primary private application compute, independent authority tier, PostgreSQL database, Redis state cache, and Linux isolated container executors.
2. **Cloudflare**: Global edge security, DNS, strict mutual/origin TLS, authenticated origin pull (AOP), DDoS mitigation, and encrypted R2 disaster recovery snapshots.
3. **Amazon Web Services (AWS)**: Privately stored, cryptographic evidence checkpoint anchoring utilizing S3 Object Lock in strict **Compliance Mode**. No application compute, API endpoints, or database workloads reside on AWS.

```mermaid
flowchart TD
    Client["Client / AI Assistant (Claude / ChatGPT)"] -->|HTTPS (TLS 1.3)| CF["Cloudflare Edge (WAF, Rate Limiting, DDoS)"]
    CF -->|Authenticated Origin Pull (mTLS / Strict TLS)| HLB["Hetzner Load Balancer (TCP Passthrough :443)"]
    HLB -->|Private Network 10.42.1.0/24| SaaS["SaaS Application / MCP Gateway (Ubuntu 24.04 CX33)"]
    
    subgraph Hetzner Private Network ["Hetzner VPC (10.42.0.0/16)"]
        SaaS -->|TCP :5432 Private| DB["Authority Tier / PostgreSQL 16 (10.42.2.0/24)"]
        SaaS -->|TCP :6379 Private| Redis["Redis Rate Limiter (10.42.1.0/24)"]
        SaaS -->|Dispatched Execution| Exec["Execution Tier / Linux Isolation (10.42.3.0/24)"]
        Exec -.->|Admit Nonce via plpgsql function ONLY| DB
    end

    subgraph External Immutability Plane
        DB -.->|Batched Canonical Evidence Digests| S3Lock["AWS S3 Object Lock (Compliance Mode / WORM)"]
        DB -.->|Encrypted Daily DB Snapshots| R2["Cloudflare R2 Backup Bucket"]
    end
```

---

## 2. Hetzner Cloud Infrastructure Architecture

- **Network Segmentation (`10.42.0.0/16`)**:
  - `10.42.1.0/24` — SaaS Application & MCP Server Subnet.
  - `10.42.2.0/24` — Authority & PostgreSQL Database Subnet.
  - `10.42.3.0/24` — Container Execution Plane Subnet.
  - `10.42.4.0/24` — NAT & Management Subnet (Bastion host for operator SSH).
- **Network Policy & Egress Restrictions**:
  - The Execution Tier has **no direct Internet egress** (`--network=none` inside Docker containers, `nftables` blocking on the host).
  - Ingress to PostgreSQL is strictly limited to SaaS and Execution hosts on `tcp:5432`.
  - The `whitepact_execution` database role has **zero** `SELECT`, `INSERT`, `UPDATE`, or `DELETE` permissions on all canonical authority tables (`governance_policies`, `governance_approvals`, `governance_revocation_epochs`, etc.). It can only invoke the `SECURITY DEFINER` function `whitepact_admit_execution()`.
- **Compute Sizing (Staging)**:
  - SaaS / MCP Gateway: 1x `cx33` (4 vCPU, 8 GB RAM) — €8.49/mo.
  - Authority / PostgreSQL: 1x `cx33` (4 vCPU, 8 GB RAM) — €8.49/mo.
  - Execution Plane: 1x `cx23` (2 vCPU, 4 GB RAM) — €5.49/mo.
  - NAT / Bastion Gateway: 1x `cx23` (2 vCPU, 4 GB RAM) — €5.49/mo.
  - Load Balancer: 1x `lb11` (TCP passthrough) — €7.49/mo.
  - Primary IPv4: €0.50/mo.
  - **Hetzner Subtotal**: **€35.95 / month** (excl. VAT).

---

## 3. Cloudflare Edge Architecture

- **DNS & TLS**:
  - Proxied DNS ("orange-cloud") for public apex and subdomains.
  - Edge TLS: Minimum TLS 1.2, TLS 1.3 enabled, Strict SSL encryption mode.
- **Origin Protection**:
  - Load balancer listens on TCP 443 and routes directly to the SaaS reverse proxy.
  - Nginx/Caddy on SaaS validates Cloudflare Authenticated Origin Pull (AOP) client certificates.
- **Edge Security Rulesets**:
  - Managed WAF and OWASP core rulesets enabled.
  - Route-aware rate limiting: 20 req/min on `/api/auth`, 10 req/min on `/api/signup`, 120 req/min on `/mcp`.
  - Staging `X-Robots-Tag: noindex, nofollow` header injection.
- **Disaster Recovery (Cloudflare R2)**:
  - Encrypted, versioned backups pushed via S3 API with retention protection scripts preventing premature deletion.

---

## 4. AWS S3 Compliance Mode Evidence Anchoring

- **Architecture Purpose**:
  - Cryptographic witness and audit integrity verification.
  - Stores canonical SHA-256 evidence digests and witness batch receipts.
- **Bucket Configuration**:
  - Object Lock enabled at creation with **COMPLIANCE** retention mode (cannot be disabled or shortened even by AWS root account).
  - Minimum retention period: 365 days (or 7 years for enterprise regulatory compliance).
  - Versioning enabled; MFA Delete enforced on bucket configuration changes.
  - Public access completely blocked (`BlockPublicAcls = true`, `IgnorePublicAcls = true`, `BlockPublicPolicy = true`, `RestrictPublicBuckets = true`).
- **Least-Privilege IAM Access**:
  - WhitePact publisher role is granted `s3:PutObject` and `s3:PutObjectRetention` ONLY.
  - Auditor role is granted `s3:GetObject` and `s3:GetObjectRetention` ONLY.
  - No entity possesses `s3:DeleteObject` or `s3:DeleteObjectVersion`.
- **Auditor Verification**:
  - Supported via `responsibleai.governance.evidence_publication.read_back_object_lock()`.

---

## 5. Offline IaC Validation Status

All Terraform configuration modules have been tested offline:
- `infra/terraform/modules/whitepact-hetzner-foundation`: `terraform validate` **PASSED**.
- `infra/terraform/modules/cloudflare-edge`: `terraform validate` **PASSED**.
- `infra/terraform/environments/{development,staging,production}`: Syntactically valid.

> [!WARNING]
> Live cloud provisioning remains **STRICTLY BLOCKED**. No cloud credentials were used, no API tokens were generated, and no real expenditures occurred.
