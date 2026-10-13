# Zero-budget infrastructure (plan only)

This directory prepares a development-and-test candidate. It does not provision
anything.

- `terraform apply` and `terraform destroy` are refused by
  `oci/apply.sh`, which exits 2.
- The Terraform authorization gate defaults to `HOLD`. A plan against a live
  tenancy is not part of CI.
- This is not the enterprise cloud design reviewed as **BLOCKED — UNSAFE TO
  PROVISION** in `docs/phase0/ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md`.
  It does not close findings CLOUD-AG-01 through CLOUD-AG-07.
- It is not staging GO and it is not production readiness.

Read `docs/zero-budget/README.md` before changing these files.
