# Cursor Cloud Agent bootstrap

Scripts in this directory prepare the **engineering environment** for Cloud Agents (dependency install, tool checks).

`cloud-agent-install.sh` installs **Terraform 1.9.8** from the official HashiCorp release (HTTPS + SHA256 verification) when it is not already present. If another Terraform version is already on `PATH`, install **fails closed** rather than replacing it.

They do **not**:

- run `terraform apply` or call Hetzner
- start the WhitePact dashboard or API
- disable authentication (`RAI_AUTH_ENABLED=false` is **not** used here)
- read or print Cursor Runtime Secrets

The development-only dashboard launcher on `cursor/whitepact-dev-environment-f7a9` must not be copied into this bootstrap without review.

**Build checkout:** Cursor environment builds currently clone `main`. Merge the bootstrap PR (or point the environment build ref at the bootstrap branch) so `cloud-agent-install.sh` exists at install time.
