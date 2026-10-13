# Deployment and rollback

**Do not execute this document.** The authorization gate is closed.
`infra/zero-budget/oci/apply.sh` exits 2 and does not call Terraform.
The steps are here so a later review can see the intended order and the
rollback before anyone is asked to approve it.

No production system is a dependency of these steps. Rollback does not touch
Render, Supabase, Upstash, Paddle, or DNS.

## Current state

| Item | State |
|---|---|
| OCI / GCP / AWS / Neon / Cloudflare resources from this package | None |
| Terraform state | None committed. Backend is local. `*.tfstate` is gitignored |
| Supported checks | `python3 infra/zero-budget/oci/preflight.py --self-test`, `terraform init -backend=false`, `terraform validate` |
| `terraform plan` with `authorization_gate=HOLD` | Fails the precondition in `checks.tf`. Observed locally on 2026-10-09. Not a CI step, because a plan with a real key would talk to OCI |

## Future order, after a new authorization

Run these as separate reviewed steps. Stop at the first failure. Do not
"fix" a failure by choosing a paid shape, a second region, or a NAT gateway.

1. **Eligibility.** Complete `01-provider-eligibility-checklist.md` against
   the real account. Record home region, remaining Ampere capacity, block
   storage already used, billing-account type, and trial end date if any.
2. **Quota first.** Apply only `oci_limits_quota.always_free_a1`. Confirm
   in the console that A1 cores are capped at 2 and A1 memory at 12 GB in
   the target compartment. If the statement is rejected, stop. Do not create
   the instance without the cap.
3. **Network and host.** Apply the VCN, security list, instance, data
   volume, and bastion. If the API returns out of host capacity, stop.
   Trying another availability domain in the **same home region** is
   allowed. Trying another region or `VM.Standard.E2.1.Micro` is not.
4. **Image check.** Confirm the image is Always Free Eligible Ubuntu
   aarch64 before accepting the plan. A plan that shows any other shape,
   more than 2 OCPUs, more than 12 GB, a boot volume other than 50 GB, a
   data volume other than 50 GB, a NAT gateway, or a load balancer is a
   failed plan. Discard it.
5. **Host bootstrap.** Connect with OCI Bastion. Confirm cloud-init enabled
   `whitepact-drop-metadata.service`. Move Docker's data root onto the 50 GB
   volume before the first build. Bind dashboard and MCP to `127.0.0.1`
   only. Set `WHITEPACT_WORKERS=1`.
6. **Secrets.** Generate Postgres, Redis, and field-encryption secrets on
   the host. Keep them in a root-only env file. Do not copy them into
   Terraform, chat, or git.
7. **Smoke, synthetic data only.** `curl` health on the host loopback.
   Run the isolation tests that need Docker. Do not point the VM at a
   production database URL.
8. **Spend check.** The same day, open the OCI cost analyzer. Confirm the
   new resources show as Always Free and that no paid SKU appeared. A
   non-zero projected charge means delete the stack (section below), not
   "watch it".

GCP or AWS temporary staging, if OCI capacity is unavailable and the owner
opens that alternative separately:

- Create the one VM described in the allocation doc and a budget alert in
  the same session.
- Write the shutdown date into the risk register before the VM boots.
- Delete the VM, disks, and addresses at least seven days before credit
  expiry, or immediately if the credit balance falls below the cost of
  the next 48 hours. Stopping the VM is not deletion.

## Rollback

Rollback of this candidate is destruction of resources that this candidate
created. There is no previous dev VM to roll forward to, and there is no
production deploy to undo.

1. Export nothing that contains customer data. There should be none. If a
   dump contains anything other than synthetic rows, stop and treat it as
   an incident instead of copying it off the host.
2. From the module directory, a future authorized destroy deletes the
   instance, the data volume, the bastion, and the VCN. `preserve_boot_volume`
   is false so the boot volume goes with the instance.
3. In the console, delete any volume, backup, reserved public IP, or
   instance that was created by hand and is therefore absent from state.
   A leftover 50 GB boot volume still counts against 200 GB and can push
   the next volume into paid storage.
4. Confirm the cost analyzer returns to the pre-change baseline.
5. If Oracle reclaims the instance for idleness, treat that as an
   involuntary rollback. Do not re-create it on a paid shape. Rebuild only
   with the same module, after capacity exists, or abandon the VM and stay
   on GitHub Actions.

Application rollback on the VM, before the VM itself is destroyed:

- `git checkout` the previous reviewed SHA and rebuild the local image.
- Postgres schema rollback uses Alembic downgrade only when that downgrade
  has been read. Prefer restoring the synthetic data volume from a snapshot
  that was taken immediately before the migration. The Always Free backup
  cap is five; delete the snapshot after the restore.
- Dashboard and MCP listen on loopback, so a bad build does not change a
  public name. There is no DNS TTL to wait out.

## Clean shutdown without destroying the account

For a pause shorter than seven days, `docker compose stop` is enough.
Past seven days the idle-reclamation rule may delete the instance anyway.
Do not run a CPU burner to stay under that rule. If the VM will sit idle,
destroy it on purpose so the block volumes are released under operator
control instead of by reclamation.

## What this procedure refuses

- `terraform apply` or `terraform destroy` while `apply.sh` is the hard
  failure shipped with this package.
- Any change to production DNS, including a Cloudflare hostname for a tunnel.
- Copying `.env.prod` from the live reference deployment onto this VM.
- Opening 8765 or 8766 on the security list "just to test from a laptop".
  Use an SSH tunnel through Bastion.
