# Production cutover plan

**Status:** OWNER_APPROVAL_REQUIRED for every step marked ⚠️

## Preconditions

- [ ] Itemized monthly spend approved (`CLOUD_COST_AND_CREDITS.md`)
- [ ] Hetzner `terraform apply` on `environments/production` ⚠️
- [ ] Helm release tested against private origin (not public DNS)
- [ ] Migrations applied via job (`helm/rai-governance` migration hook)
- [ ] Secrets in Hetzner/K8s secrets manager — not in git
- [ ] Gitleaks / CI green on integration SHA

## Sequence

1. **Provision** Hetzner private network, firewalls, LB, servers (IaC).  
2. **Install** PostgreSQL on authority node (or attach managed DB when adopted); restrict to private CIDR.  
3. **Deploy** SaaS containers / k3s / Helm per `DEPLOY_RUNBOOK.md`.  
4. **Smoke** health, auth, tenant isolation on private IP.  
5. **Configure** Cloudflare DNS **grey-cloud** test record to origin ⚠️  
6. **Validate** TLS, WAF, rate limits on test hostname.  
7. **Cutover** production DNS to proxied record ⚠️ **OWNER**  
8. **Enable** R2 backup cron with encrypt script ⚠️  
9. **Optional** GCS secondary backup if credits verified ⚠️  

## Rollback

- Revert Cloudflare DNS to previous origin (TTL documented).  
- Keep last known-good DB backup immutable.  
- Helm rollback per Cell B `kind_b9_b10_qualification.sh` pattern (on cluster).

## Explicitly not in this pass

- Live DNS changes  
- Production data migration  
- Customer traffic switch
