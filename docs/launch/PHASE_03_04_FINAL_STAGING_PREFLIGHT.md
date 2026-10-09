# Phase 3/4 — final staging preflight

**Live staging: NO-GO.** This package does not run `terraform apply`, change DNS, provision paid resources, activate billing, or deploy production.

Pinned candidates stay where they are:

| PR | Commit | Treatment |
|----|--------|-----------|
| #171 | `6801d4ad0047d15a196ab9caeffacf54f9ce557e` | Not modified |
| #172 | `6fefece7b7620ae2f1fa7c307f6720e4bbde709f` | Not modified. This branch starts there and adds the preflight. |

Offline checks in this commit are not Phase 4 staging acceptance.

## Defects closed in the staging modules

1. Authority and SaaS host nftables no longer add an unrestricted `tcp/443` or `tcp/80` accept when the NAT gateway is enabled. Egress is the explicit CIDR list. The NAT forward chain uses the same lists.
2. Private nodes can renew DHCP and reach pinned DNS (`185.12.64.1`, `185.12.64.2`) and NTP (`162.159.200.1`, `162.159.200.123`). Output policy remains drop.
3. NAT rules are written into `/etc/nftables.conf` with `flush ruleset`, so `nftables.service` does not restore the image default accept policy.
4. SSH password authentication is disabled on the NAT gateway and the private tiers. Root key login is unchanged.
5. The default route waits for the NAT server. Servers wait for their subnet and the route. Load balancer targets wait for the private load-balancer attachment.
6. `0.0.0.0/0` and `::/0` are rejected on admin, SaaS, authority, and execution egress. Staging and production require an admin SSH key id. An admin Cloudflare tunnel cannot be planned with `REPLACE_BEFORE_APPLY`.
7. The staging root refuses a plan whose FSN1 estimate exceeds 3595 euro cents.

Execution to authority PostgreSQL on port 5432 remains the documented admission path. It was not removed.

## Exact Hetzner staging cost

Location scope: Falkenstein / Nuremberg / Helsinki. Prices exclude VAT. Reviewed 2026-10-09.

| Line | SKU | EUR / month ex VAT | Source |
|------|-----|--------------------|--------|
| SaaS | CX33 | 8.49 | Hetzner price adjustment, 15 June 2026, Germany/Finland, excl. IPv4 |
| Authority | CX33 | 8.49 | Same |
| Execution | CX23 | 5.49 | Same |
| NAT | CX23 | 5.49 | Same |
| NAT primary IPv4 | IPv4 | 0.50 | Hetzner primary IP overview |
| Load balancer | LB11 | 7.49 | April 2026 adjustment. Load balancers were excluded from the June 2026 round. The LB11 IPv4 is included in this price and is not added again. |
| Private network and firewall | — | 0.00 | Included |
| **Approved ceiling** | | **35.95** | 3595 euro cents |

The approved shape is `at_ceiling`. Any added resource is a new approval. The alert action is: do not enable backups, volumes, a second server, or unmetered traffic.

Optional, not in the staging root and not in the ceiling:

| Item | EUR / month ex VAT | Note |
|------|--------------------|------|
| Hetzner server backups | 5.592 | 20% of the four server SKUs (27.96), not 20% of 35.95 |
| VAT if the invoice is German 19% | 6.8305 on the 35.95 subtotal | Gross would be 42.7805. Billing country is unconfirmed. |

CX22 and CX32, used by the development and production examples, are not in this price book. Those roots do not set a ceiling. A production plan still requires SSH key ids and explicit egress CIDRs.

## What offline tests proved

`python3 scripts/cloud/staging/preflight_offline.py` checks the static isolation rules, the 35.95 EUR total, and the at-ceiling alert. It prints secret **names** that are absent. It does not print values and does not call Hetzner, Cloudflare, or R2.

The pytest module `tests/test_phase34_staging_preflight.py` also rehearses, on this workstation only:

- governed MCP deny, one-time allow, replay, and expiry
- tenant mismatch between org A and org B
- execution environment stripping of `POSTGRES_PASSWORD`
- container argv containing `--network=none` and no `docker.sock`
- an encrypted restore into a `wp_restore_` scratch name, with no active-database drop and no deletion of the newest recovery point
- a 50-iteration in-process authorization timing sample

`tests/test_phase34_billing_sandbox.py` rejects unsigned, mismatched, and expired Paddle webhook signatures, keeps a sandbox client off the live API, and blocks an SSO-required admin login and an MFA downgrade. No price, plan, or contract was chosen.

## Owner dependencies

| ID | Need |
|----|------|
| OWNER-GATE-1 | Reply with the exact phrase APPROVE STAGING CLOUD PROVISIONING. That phrase is not granted by this package. |
| HCLOUD_TOKEN | Place a Hetzner project token in the operator secret store. Do not commit it. |
| SSH-KEY | Create the Hetzner SSH key named whitepact-staging-admin before plan. |
| ADMIN-CIDR | Replace YOUR.PUBLIC.IP.ADDRESS/32 with the operator /32. 0.0.0.0/0 is rejected. |
| AUTHORITY-EGRESS | Replace 10.255.0.1/32 with the R2 API ranges the owner accepts. The placeholder does not open the Internet. |
| SAAS-EGRESS | Replace 10.255.0.3/32 with the package mirror or registry ranges the owner accepts. |
| EXECUTION-EGRESS | Replace 203.0.113.10/32 with the governed MCP upstream ranges. TEST-NET-3 is not a customer destination. |
| CLOUDFLARE | Decide whether the first apply includes Cloudflare. The staging root does not. DNS stays unchanged. |
| R2-SECRETS | Provide R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT, and WHITEPACT_BACKUP_ENCRYPTION_KEY outside git. |
| APP-SECRETS | Provide POSTGRES_PASSWORD and REDIS_PASSWORD on the hosts, not in Terraform state comments. |
| BACKUP-DELETE | Retention deletion stays dry-run until the owner passes --delete on a reviewed plan. |
| VAT | 35.95 EUR is exclusive of VAT. A German 19 percent VAT invoice would be 42.7805 EUR. Confirm the billing country. |
| LIVE-ACCEPTANCE | Offline tests are not staging acceptance. Do not mark Phase 4 live checks passed from this package. |
| ANTIGRAVITY | Independent review of this successor is still required. PR #171 at 6801d4ad and PR #172 at 6fefece7 stay unmodified. |

## Owner approval request

Please approve or reject this inventory. Approval is the single line:

`APPROVE STAGING CLOUD PROVISIONING`

That line would authorize a later staging apply of the 35.95 EUR / month (ex VAT) shape above. It does not authorize production, a DNS change, Cloudflare cutover, R2 deletion, billing activation, or treating this offline package as Phase 4 acceptance. Until that line is recorded by the owner, the gate remains NO-GO.
