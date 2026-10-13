# Network Security — Live Staging Test Plan

SHA: `caf539b`

## Baseline (code)

| Control | Location | Status |
|---------|----------|--------|
| Tier subnets | `whitepact-hetzner-foundation` | **VERIFIED_SIMULATION** |
| Hetzner cloud firewalls | `main.tf` saas/authority/execution | **VERIFIED_SIMULATION** |
| Execution egress allowlist | `execution_egress_cidrs` | **VERIFIED_AUTOMATED_TESTS** (`test_terraform_policy.py`) |
| Authority egress fail-closed default | module locals | **VERIFIED_AUTOMATED_TESTS** |
| Host nftables | `cloud-init-nftables.yaml` | **VERIFIED_AUTOMATED_TESTS** |
| `saas_public_ipv4` default false | module variable | **VERIFIED_AUTOMATED_TESTS** |

Subnet placement alone is **not** claimed as isolation — tests must show deny/allow behavior.

## Live test matrix (Phase 4)

| ID | Flow | Expected | Tool | Status |
|----|------|----------|------|--------|
| N-01 | Internet → CF → LB → SaaS:443/8765 | Allow TLS to app | curl via staging URL | **AWAITING_LIVE_STAGING** |
| N-02 | Direct server public IP (if any) | No dashboard | nmap/curl | **AWAITING_LIVE_STAGING** |
| N-03 | SaaS → authority:5432 | Allow | psql from SaaS host | **AWAITING_LIVE_STAGING** |
| N-04 | SaaS → execution tier | Deny by default | nc / traceroute | **AWAITING_LIVE_STAGING** |
| N-05 | Execution → approved API CIDR | Allow | curl from exec host | **AWAITING_LIVE_STAGING** |
| N-06 | Execution → random Internet | Deny (nft + fw) | curl 1.1.1.1:443 | **AWAITING_LIVE_STAGING** |
| N-07 | SaaS → Hetzner metadata/admin | Deny | — | **AWAITING_LIVE_STAGING** |
| N-08 | East-west SaaS ↔ execution | Deny | — | **AWAITING_LIVE_STAGING** |
| N-09 | nftables loads on first boot | `nft list ruleset` | SSH after create | **AWAITING_LIVE_STAGING** |
| N-10 | Survives reboot | rules persist | reboot + retest N-06 | **AWAITING_LIVE_STAGING** |
| N-11 | Emergency SSH from allowlist | Allow | SSH from founder IP | **AWAITING_LIVE_STAGING** |
| N-12 | SSH from non-allowlist | Deny | — | **AWAITING_LIVE_STAGING** |
| N-13 | Origin TLS (LB ↔ origin) | Valid cert chain; no plain HTTP | openssl s_client | **AWAITING_LIVE_STAGING** |

## TLS / origin note

Cloudflare orange-cloud alone is insufficient — validate **full stack TLS** and that origin is not reachable except via LB/CF path.

## Evidence

For each test: command, timestamp, source IP, pass/fail, packet capture or firewall log snippet.
