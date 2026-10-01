# Network Isolation

## Tiers

SaaS, authority, execution — separate subnets (`10.42.1.0/24`, `.2.0/24`, `.3.0/24` defaults).

## Hetzner limitations

- Cloud Firewalls **do not** filter east-west traffic on the private network.
- **Host nftables** via cloud-init (`templates/cloud-init-nftables.yaml`) enforce tier rules.

## Egress

- **Execution:** allowlist only; empty allowlist = no outbound 443 (fail closed).
- **Authority:** explicit `authority_egress_cidrs` only (no `0.0.0.0/0`).
- **SaaS:** `saas_public_ipv4` default **false**; traffic via LB + Cloudflare.

## Origin protection

Cloudflare orange-cloud + optional Tunnel; direct origin bypass tested in `11_SECURITY_TEST_RESULTS.md` scenario 8.

## Status

| Control | Status |
|---------|--------|
| Subnet separation | IMPLEMENTED_NOT_DEPLOYED |
| nftables cloud-init | IMPLEMENTED_NOT_DEPLOYED |
| Live tier connectivity tests | BLOCKED (no environment) |
