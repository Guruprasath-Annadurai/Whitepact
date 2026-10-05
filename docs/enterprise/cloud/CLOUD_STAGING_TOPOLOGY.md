# Cloud staging topology

## A. Minimum serious staging (qualification)

```
Internet
  → Cloudflare (orange-cloud, TLS Full Strict)
    → Hetzner LB11 (public IPv4 only on LB)
      → SaaS node (private 10.42.1.x) :8765 dashboard, :8766 MCP
        → PostgreSQL on authority (10.42.2.x:5432, no public IPv4)
        → Execution worker (10.42.3.x, egress allowlist)
```

- **Deployment unit:** `docker-compose.prod.yml` on SaaS host **or** split containers per tier (preferred for parity with production module).
- **PostgreSQL:** dedicated authority VM; port 5432 allowed only from SaaS + execution subnets (Terraform firewalls + nftables cloud-init).
- **Redis:** colocated on SaaS subnet (compose) for staging cost; document production colocation vs managed Redis for launch.

## B. Recommended production

Same three-tier network (`infra/terraform/modules/whitepact-hetzner-foundation`):

- 2× SaaS behind LB
- 1× authority (Postgres); consider replica for HA later
- 2× execution
- Optional: Cloudflare Tunnel for admin plane only (not customer traffic)

## Helm / Kubernetes

Helm chart `helm/rai-governance/` is CI-validated but **not** the default staging path — adds control-plane cost and ops burden. Use for customers who require K8s; staging qualifies the **Hetzner + compose/LB** path first.

## Artifact pinning

| Field | Value |
|-------|--------|
| Source SHA | `ee6e4a26becf7e89a933202651fba3b4e7a8176d` |
| Tree | `cbd8ba8678448a4164681ac47e31dc582c5c7947` |
| Image | Build from `Dockerfile` @ SHA; tag `whitepact:ee6e4a2@<digest>` — record digest at build |
