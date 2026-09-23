# ADR 0008: Always-On Hosted MCP Deployment & Cold-Start Elimination

**Status**: Accepted  
**Date**: 2026-09-17  
**Deciders**: WhitePact Core Engineering & Security  

---

## 1. Context & Problem Statement

WhitePact exposes a public Model Context Protocol (MCP) server interface (`whitepact-mcp-http`) over Streamable HTTP (`/mcp`) and SSE (`/sse`), currently deployed at `https://whitepact-mcp-http.onrender.com`.

In initial staging and demo configurations running on Render's free tier, instances automatically spin down (sleep) after 15 minutes of inactivity. When a remote MCP client (such as Google Antigravity, Claude Desktop, Cursor, Mistral Le Chat, or custom agent runners) initiates an MCP handshake or executes a tool call:
- The instance cold-start takes between 45 and 90 seconds.
- Standard client HTTP/SSE connection timeouts (typically 10–30 seconds) expire before TLS termination and Python process initialization complete.
- This manifests to users and client orchestrators as intermittent connection drops, HTTP 502/504 errors, and protocol initialization timeouts (`transport error: timeout`).

Furthermore, WhitePact's MCP server maintains per-process sliding-window rate limiters, OAuth authorization state, and in-flight SSE streams. Ephemeral spin-downs clear in-memory state and sever persistent SSE streaming channels.

---

## 2. Decision: Always-On Render Starter (Immediate Target)

For the immediate production deployment, upgrade the `whitepact-mcp-http` service on Render to the **Starter Instance Tier** (or higher) with always-on capabilities:
- **Zero Spin-Down**: Instance remains active 24/7; cold-start latency is 0 ms.
- **Dedicated Resources**: 0.5 vCPU, 512 MB RAM guaranteed allocation.
- **Native Health Probes**: Configured with decoupled HTTP liveness (`/health`) and database readiness (`/ready`) probes.
- **Zero Infrastructure Drift**: Reuses the existing Render Docker build pipeline (`Dockerfile`, `entrypoint.sh`), unified environment configuration, and Render-managed TLS certificates.

---

## 3. Viable Alternative Cloud Architectures

We evaluated three alternative architectures for hosting the always-on MCP service:

### A. Google Cloud Run (Fully Managed Container)
- **Configuration**: Cloud Run service running container `responsibleai-mcp-http`, with `min-instances=1`, concurrency=80, CPU allocation always on (`--no-cpu-throttling`).
- **Pros**: Native Google Cloud IAM integration, enterprise DDoS protection via Google Cloud Armor, seamless zero-downtime blue/green traffic splitting.
- **Cons**: Requires GCP project setup, VPC connector configuration to connect to private databases, higher configuration overhead.

### B. AWS ECS Fargate
- **Configuration**: ECS Service with Fargate launch type, Application Load Balancer (ALB), target group health checks pointing to `/ready`.
- **Pros**: Deep AWS ecosystem integration, IAM role per task, robust autoscaling.
- **Cons**: Substantial Terraform/CloudFormation surface area, ALB monthly baseline cost ($16–$22/mo), VPC/NAT Gateway requirements.

### C. Self-Hosted Kubernetes (Helm Chart)
- **Configuration**: Deploying via WhitePact's existing Helm chart (`helm/rai-governance`) with `mcp.enabled=true`, `mcp.autoscaling.minReplicas=2`, `readinessProbe.path=/ready`, and `livenessProbe.path=/health`.
- **Pros**: Completely cloud-agnostic, full control over network policies and private database connectivity, already codified in repository.
- **Cons**: Requires managing a Kubernetes cluster (GKE, EKS, or k3s), ingress controller, cert-manager, and cluster monitoring.

---

## 4. Cost vs. Operational Complexity Trade-off Matrix

| Option | Estimated Baseline Cost | Operational Overhead | Cold Start | High Availability (Multi-AZ) | Recommendation |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Render Free Tier** | \$0/month | Low | Severe (45–90s) | None (single container, spins down) | **Rejected** (Unusable for agent workflows) |
| **Render Starter Tier** | \$7/month | Minimal (managed UI / CLI) | **None (0s)** | Single instance with automatic restart | **Accepted (Target for V1 Cutover)** |
| **Google Cloud Run (min=1)**| ~\$18–\$25/month | Moderate (GCP console / gcloud) | **None (0s)** | Multi-zone managed by Google | **Fast-Follow / Enterprise Tier** |
| **AWS ECS Fargate (2 tasks)**| ~\$40–\$60/month | High (VPC, ALB, IAM) | **None (0s)** | Multi-AZ redundant | **Future Enterprise Option** |
| **Kubernetes Helm** | Cluster-dependent | High (Cluster ops) | **None (0s)** | Multi-node, PodDisruptionBudget | **On-Premises / Enterprise Self-Hosted** |

---

## 5. V1 Production Cutover Runbook

### Prerequisites
1. Render account with admin or operator access to the `whitepact-mcp-http` service.
2. Render PostgreSQL database connection string (`DATABASE_URL`).
3. Valid WhitePact master API keys and OIDC configuration (if enabled).

### Procedure
1. **Tier Elevation**:
   - In the Render Dashboard, navigate to `whitepact-mcp-http` -> **Settings** -> **Instance Type**.
   - Change instance type from `Free` to `Starter` (or run `render services update srv-xxxx --instance-type starter`).
   - Save changes to trigger container re-provisioning.
2. **Environment Variable Verification**:
   - Ensure the following variables are present in the Render environment:
     ```bash
     WHITEPACT_ENV=production
     RAI_ENV=production
     DATABASE_URL=postgresql://...
     WHITEPACT_MCP_HTTP_HOST=0.0.0.0
     WHITEPACT_MCP_HTTP_PORT=8766
     WHITEPACT_MCP_LOG_LEVEL=INFO
     WHITEPACT_MCP_TRUST_FORWARDED_HEADERS=true
     ```
   - Verify that `auto_create_tables` is bypassed in production (`WHITEPACT_ENV=production`), allowing Alembic migrations to govern schema.
3. **Health & Readiness Verification**:
   - Test Liveness:
     ```bash
     curl -fsS https://whitepact-mcp-http.onrender.com/health
     ```
     Expected: `{"status": "ok", "transport": "http+sse", "transports": ["streamable-http", "http+sse"], "tools": 23}`
   - Test Database Readiness:
     ```bash
     curl -fsS https://whitepact-mcp-http.onrender.com/ready
     ```
     Expected HTTP 200: `{"status": "ready", "database": "connected"}`
4. **End-to-End MCP Smoke Test**:
   - Execute the integration smoke test script against the deployed endpoint:
     ```bash
     python scripts/integration_smoke.py --mcp-url https://whitepact-mcp-http.onrender.com
     ```
   - Verify MCP tool listing (`tools/list`), schema validity, and authenticated tool ping.

---

## 6. Rollback Plan

If the upgraded instance fails health checks or produces unrecoverable errors during cutover:
1. **Immediate Service Rollback**:
   - In Render Dashboard -> **Deploys**, select the previous known stable commit/build and click **Rollback to this deploy**.
2. **Temporary Fallback to Secondary Transport**:
   - If Streamable HTTP (`/mcp`) experiences proxy buffering or TLS termination issues on Render, direct clients to the legacy SSE endpoint:
     `https://whitepact-mcp-http.onrender.com/sse`
3. **Database Safeguard**:
   - Because production server startup runs `SELECT 1` without calling `metadata.create_all`, rolling back the application tier has zero destructive impact on database schema or active migrations.
