# Owner Approval Gate — Private Staging

**STOP — read before any provisioning.**

| Field | Value |
|-------|--------|
| Repository SHA | `caf539bcaa9893d346ce01f6fbc032cf9d1eabc4` |
| PR | [#128](https://github.com/Guruprasath-Annadurai/Whitepact/pull/128) (do **not** merge yet) |
| Engineering CI | [`36632878907`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36632878907) — **success** on exact HEAD |
| Code qualification SHA | `7743dd5` (CI workflow split); docs at `caf539b` |

**CI success ≠ live security qualification.** Staging apply remains **closed**.

---

## Founder approval request (template)

By approving, I authorize the **minimum private staging** described in `STAGING_ARCHITECTURE.md` and `RESOURCE_AND_COST_APPROVAL.md`.

### Resources to be created (if approved)

| Resource | Provider | Purpose |
|----------|----------|---------|
| 2–4× CX22 servers | Hetzner | SaaS, authority/DB, execution (per BOM) |
| 1× LB11 | Hetzner | TLS ingress to origin |
| 1× private network | Hetzner | Tier isolation |
| Staging Access application | Cloudflare | Employee authentication |
| Staging DNS records | Cloudflare | **Non-apex** subdomain only |
| R2 bucket/prefix | Cloudflare | Encrypted backups (optional phase) |

### Accounts affected

- Hetzner Cloud project (staging/disposable)
- Cloudflare account (zone DNS + Access + optional R2)
- GitHub repository **staging** environment secrets (not committed)

### Credentials to configure (never in chat or git)

- `HCLOUD_TOKEN` (scoped project token)
- Cloudflare API token (DNS + Access + R2 scoped separately)
- Staging admin grant signing key (32+ bytes, random)
- PostgreSQL password (staging only)
- Backup operator R2 credentials (no delete permission on app role)

### DNS changes

- **Allowed:** `staging.<domain>` or `cloud-staging.<domain>` → LB
- **Forbidden without separate approval:** apex production records, MX changes, customer-facing cutover

### Expenditure ceiling (founder fills in)

| | |
|---|---|
| Maximum approved monthly recurring | € ______ / $ ______ |
| Maximum 14-day qualification burn | € ______ / $ ______ |
| Cloudflare plan/seats approved | Yes / No |

### Deployment duration

- Intended live staging window: **≤ 14 days** (default)
- Extension requires written re-approval

### Teardown commitment

- Execute `ROLLBACK_AND_RESOURCE_CLEANUP.md` within **48 hours** of qualification end or on any critical finding
- Verify zero billable Hetzner compute afterward

### Required test results before advancing past staging

- [ ] `IDENTITY_AND_ACCESS_TEST_PLAN.md` — live I-01–I-08
- [ ] `NETWORK_SECURITY_TEST_PLAN.md` — live N-01–N-13
- [ ] `ADMIN_EXECUTION_TEST_PLAN.md` — live A-01, A-05–A-07
- [ ] `OFFBOARDING_VERIFICATION.md` — live O-01–O-05
- [ ] `BACKUP_AND_RECOVERY_TEST_PLAN.md` — B-04 restore drill
- [ ] `ADVERSARIAL_QUALIFICATION_MATRIX.md` — no open **AWAITING** for infra/auth tiers
- [ ] **Antigravity independent review** — pass with evidence

### Explicit prohibitions (remain in force until separate launch approval)

- No `terraform apply` without signing this gate
- No production customer data
- No merge of PR #128 to `main` as part of staging
- No `PRIVILEGED_EXECUTOR_ENABLED=True` without admin execution live tests
- No production DNS cutover
- No public production launch

---

## Signature block

| | |
|---|---|
| Founder name | |
| Date | |
| Approved max spend | |
| Approved BOM variant | Dev-minimum / Prod-shaped staging |
| Notes | |

Store signed PDF or issue comment in private tracker — **not** in public repo.
