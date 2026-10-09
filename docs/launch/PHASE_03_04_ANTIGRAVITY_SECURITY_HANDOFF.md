# Phase 3/4 — Antigravity security handoff

**This document is a handoff. It is not an Antigravity PASS.** Live staging remains NO-GO.

Review the tip of `cursor/whitepact-phase34-staging-preflight-00f5` (PR #173). After fetch, record:

```bash
git rev-parse HEAD
git rev-parse 'HEAD^{tree}'
```

Reject the packet if those values differ from the pull-request head. This file cannot contain its own commit SHA. The PR body records the exact HEAD and TREE after the tip commit.

## Ancestry

| Field | Value |
|-------|--------|
| Preflight base | `6fefece7b7620ae2f1fa7c307f6720e4bbde709f` |
| Preflight base tree | `043b5f14f63b32ea60d3c168d4fcf3bf27800d14` |
| PR #171 | `6801d4ad0047d15a196ab9caeffacf54f9ce557e` — ancestor of the base, not modified |
| PR #172 current head | `7a0852899afd997264c384a9ff5ca5f99a65c7ca` — **not** an ancestor of this branch |
| PR #174 Foundation Hardening | Not merged |

`6fefece7` is the parent of current PR #172. The only commit on PR #172 absent here is `7a08528`, which edits `docs/launch/ANTIGRAVITY_DELTA_6801d4.md`. Do not treat that documentation commit as contained in this tree.

## What changed after the base

- NAT forward rules require the source subnet that owns each destination allowlist. Cross-tier and management-subnet sources are rejected, including a synthetic hostile ruleset.
- `whitepact_execution` has no table privileges and cannot execute `whitepact_admit_execution`. The authority role is the only grantee. A live PostgreSQL test covers insert, update, delete, select, self-issued authorization, nonce replay, epoch rewind, `SET ROLE`, `SUPERUSER`, and `CREATE TABLE`.
- The origin nginx file requires a client certificate. An independent nginx 1.24 probe sends an HTTP request to a sentinel upstream. A missing certificate returns HTTP 400 `No required SSL certificate was sent` and does not reach the sentinel. A wrong CA returns HTTP 400 `The SSL certificate error` and does not reach the sentinel. A certificate signed by the test CA is proxied and the sentinel answers. Staging still does not enforce this: the Cloudflare module, zone and per-hostname authenticated origin pulls, CA bundle, origin certificate, origin key, proxied DNS record, Full (strict) zone setting, nginx package, and real hostname are absent.
- The 3595 euro-cent figure is a Terraform price-book ceiling. It is not a Hetzner billing alert, it excludes VAT, and it excludes backups unless `enable_server_backups` is set. That flag rounds backup cost up and then exceeds 3595 cents. No billing-alert resource is created.

## Commands

Do not run `terraform apply`. Do not change DNS. Do not activate billing.

```bash
ruff check src/ tests/
pytest tests/test_phase34_staging_preflight.py tests/test_phase34_billing_sandbox.py tests/test_phase34_execution_db_boundary.py tests/test_phase34_origin_aop.py -q --tb=line --override-ini='addopts='
terraform -chdir=infra/terraform/modules/whitepact-hetzner-foundation init -backend=false -input=false
terraform -chdir=infra/terraform/modules/whitepact-hetzner-foundation validate
terraform fmt -check -recursive infra/terraform
```

The execution-role test needs PostgreSQL on `127.0.0.1:55432` as user `wp`. The origin probe needs nginx and openssl. Neither test calls Hetzner or Cloudflare.

## Owner approval

Still required, and still the only approving line:

`APPROVE STAGING CLOUD PROVISIONING`

That line is not granted here.
