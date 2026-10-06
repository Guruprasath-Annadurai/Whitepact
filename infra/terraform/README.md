# WhitePact Terraform (plan-only)

**Status:** Engineering validation only. **Do not** `terraform apply` without founder approval and Antigravity cloud re-audit pass (`CLOUD-AG-01` … `CLOUD-AG-07`).

## Validate locally

```bash
cd infra/terraform/modules/whitepact-hetzner-foundation
terraform init -backend=false
terraform validate
```

Environment roots under `environments/` require provider credentials and are not applied in Phase 1 CI by default.
