# Cost and expiry risk register

Budget: **$0 out of pocket**.

Alerts and free-tier badges do not guarantee that number. Every row below
can still produce a charge if the listed trigger happens. The mitigation is
avoidance and deletion, not a promise from the provider.

Status of every row on 2026-10-09: **not created** by this package.

| ID | Service | How it charges | Mitigation in this package | Residual risk | Expiry |
|---|---|---|---|---|---|
| C-01 | OCI Ampere overage | More than 2 OCPUs or 12 GB, or a second A1 that pushes the total over the cap | Variable validation locks 2 / 12. Quota statements prepared for the same cap. Paid shapes are not in the module | Console creates outside Terraform. Quota name can be wrong and then there is no cap | Always Free has no end date in Oracle's doc. The separate trial is 30 days / $300. Instances over the Always Free total are disabled and deleted 30 days after trial end unless the account is upgraded |
| C-02 | OCI block storage | Boot + data over 200 GB, volumes outside the home region, or a paid volume that was not converted back | 50 + 50 GB, home region only, `preserve_boot_volume=false` | Orphan boot volumes and backups. Cap is 5 backups | Always Free. Orphan volumes bill or consume the cap indefinitely |
| C-03 | OCI image and license | An image that is not Always Free Eligible | Checklist item. Module cannot verify an OCID offline | Operator pastes a paid image OCID | Immediate |
| C-04 | OCI NAT gateway or load balancer | Hourly and capacity charges, including a flexible LB left above 10 Mbps | Resources are not in the module. Preflight fails if the NAT resource type appears | Someone adds one in the console "for SSH" | While the resource exists |
| C-05 | OCI outbound | Data transfer above 10 TB/month | Dev pulls are megabytes to low gigabytes | A public dashboard left open could serve traffic. Loopback bind is the mitigation | Monthly |
| C-06 | OCI idle reclaim | Not a charge. Oracle may delete an idle A1 after 7 days under 20% CPU, network, and memory | Documented. No fake load | Rebuild cost is time, not money, unless someone rebuilds on a paid shape | 7 idle days |
| C-07 | OCI card on file | Signup can require a card (`DEPLOY_RUNBOOK.md`) | Do not upgrade to paid. Read the cost analyzer the day of any future create | A card plus an upgrade bills overage even when alerts exist | While the card and paid status exist |
| C-08 | GCP Free Trial | $300, 90 days. Usage past Always Free consumes the credit. Upgrade starts real billing | Not the persistent host. `e2-micro` rejected as too small (1 GB) | Founder Gemini billing link may already be a Paid account. A Paid account bills an `e2-standard-2` immediately | 90 days or credit exhaustion, whichever first. Unused credit expires |
| C-09 | GCP Always Free egress | 1 GB North America egress, then billed on a Paid account | No GCP VM in this design | A trial VM that is upgraded crosses this quickly | Monthly |
| C-10 | GCP budget alert | The alert itself is not a charge. The usage it reports may already be a charge | Do not describe an alert as a cap | Budgets notify. A programmatic billing disable is delayed and incomplete | n/a |
| C-11 | AWS credits | Balance is unknown in this repo. Paid plan bills after credits. New Free plan ends at 6 months or credit exhaustion | No AWS resources. Checklist requires the console balance before any use | Assuming "$200" when the account has less, or is legacy, or is already Paid | Credits: 12 months from account creation on the new program, or sooner if the Free plan ends. Legacy 12-month offers follow the account's original clock |
| C-12 | AWS NAT, LB, public IPv4, EBS, RDS storage | Hourly and per-GB prices with no meaningful free tier for NAT | Forbidden in the temporary path | Stopping an instance leaves EBS and IPv4 charges | While the resource exists |
| C-13 | Neon Launch upgrade | $0.106/CU-hour and storage charges, no monthly minimum, so "no minimum" still bills | Free plan only. No payment method | An upgrade click in the console | While upgraded. Free CU-hours reset monthly; storage does not |
| C-14 | Neon Free limits | Not a charge if the plan stays Free. Compute suspends or writes fail | One synthetic project. CI does not point at it | A payment method turns the next overage into C-13 | Monthly compute; storage is continuous |
| C-15 | Cloudflare Workers / R2 | Free caps error or throttle without a payment method. With a payment method, overage bills (Workers $0.30/million requests after the free allotment; R2 storage and operation prices on the paid schedule) | No payment method. No production DNS. No Worker in the decision path | Someone adds a card to "lift" the 100k/day cap | Monthly. R2 storage is continuous |
| C-16 | GitHub Actions | Standard runners on a public repo are $0. Larger runners, private-repo minutes, and some artifacts bill | This repo is public. Workflow uses `ubuntu-latest` only | Changing visibility to private, or registering a larger runner | While the setting exists |
| C-17 | Domain and DNS | Registration and some DNS providers bill. A Tunnel hostname is a DNS write | No DNS changes in this package | A later "quick test" record on the production zone | Annual for a domain; immediate for a mistake |
| C-18 | Human workaround | Out of capacity or a failed free signup, followed by a paid VM "for the weekend" | Stop condition in the deployment doc | The weekend becomes a month | Until deleted |

## Alert rule

If a future authorization allows an account that can bill, create the
provider's budget or credit notification **before** the VM. Set thresholds
at 50%, 80%, and 100% of the **remaining credit**, not of a guessed monthly
budget. Notifications go to the owner.

Then write this sentence next to the alert, in the same change:

> This alert does not stop resources and does not guarantee a $0 bill.

The actual stop is deletion of the resource, using the rollback section,
the same day a non-zero charge appears.

## Expiry calendar to fill in before any create

| Clock | Value on 2026-10-09 | Owner fills in |
|---|---|---|
| OCI trial end | Unknown. Not required for Always Free shapes that stay inside the cap | Date, if the tenancy is still in trial |
| GCP trial start + 90 days | Unknown | Date and remaining credit, and whether the billing account is Paid |
| AWS credit expiry | Unknown | Balance, expiry, plan type |
| Neon billing period reset | Unknown until a project exists | n/a while unused |
| Planned VM shutdown | No VM | At least 7 days before the earliest credit expiry |

Leave the table blank rather than inventing a date. An invented expiry is
worse than an unknown one.
