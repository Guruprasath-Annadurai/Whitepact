# Cloud acceptance register

Production architecture stays Hetzner for compute and Cloudflare for
edge and offsite retention. This candidate did not apply Terraform, did
not change DNS, and did not create a paid resource. The staging
provisioning gate stays closed until the owner records
`APPROVE STAGING CLOUD PROVISIONING`.

Offline `terraform validate` for
`infra/terraform/modules/whitepact-hetzner-foundation` and
`infra/terraform/modules/cloudflare-edge` succeeded with Terraform
1.9.8. `terraform fmt -check -recursive infra/terraform` succeeded.
Validation is not deployment.

| ID | Acceptance item | This candidate | Verdict |
| --- | --- | --- | --- |
| C1 | Secure environment provisioning | Modules validate. Nothing was applied. | BLOCKED |
| C2 | Operator access separated from workload identity | SSH key lookup is in the staging module. No live IAM exists. | BLOCKED |
| C3 | Network isolation, firewall, egress | nftables negative test passed on this Linux host. Hetzner nftables was not loaded. | BLOCKED |
| C4 | Protected origin and TLS/mTLS | Local nginx rejected a missing and a wrong client certificate. Cloudflare Full (strict) was not deployed. | BLOCKED |
| C5 | Secrets management and rotation | Witness key files enforce mode 0600. No cloud secret manager was used. | BLOCKED |
| C6 | Deployment automation and rollback | Workflows exist. No live rollout or rollback ran. | BLOCKED |
| C7 | Shared PostgreSQL and Redis | CI is wired with Postgres and Redis services. One local Redis process shared a window across two clients. Production replicas were not deployed. | BLOCKED |

Additional items that stay blocked with C1–C7: independent R2 witness,
backup restoration on the real store, capacity configuration, disaster
recovery, cost and billing controls, and configuration-drift detection
on a live account.

A free-tier host would still have to pass the same isolation tests. No
free tier was substituted for Hetzner or Cloudflare.
