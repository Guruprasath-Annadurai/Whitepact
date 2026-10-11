# Host firewall policy (nftables) — private nodes

Hetzner Cloud Firewalls **do not secure private Cloud Network traffic** ([Firewall FAQ](https://docs.hetzner.com/cloud/firewalls/faq/)) and **may not attach** to servers without a public interface. Staging uses **host `nftables`** via cloud-init (`templates/cloud-init-nftables.yaml`).

## SaaS (private)

| Direction | Allow |
|-----------|--------|
| In | TCP **443** from LB private IP only |
| In | TCP **8765** from LB (health) |
| In | TCP **8765/8766** from saas subnet (internal) |
| In | TCP **22** from NAT gateway private IP only |
| Out | PostgreSQL, Redis, HTTP(S) only to `saas_egress_cidrs`, DNS and NTP to pinned resolvers, DHCP renew |

## PostgreSQL authority (private)

| Direction | Allow |
|-----------|--------|
| In | TCP **5432** from saas + execution subnets |
| In | TCP **22** from NAT gateway only |
| Out | TCP **443** only to `authority_egress_cidrs`, plus pinned DNS and NTP. NAT does not add a world-wide HTTPS accept. |

No inbound Internet exposure.

## Execution (private)

| Direction | Allow |
|-----------|--------|
| In | TCP **22** from NAT gateway only |
| Out | PostgreSQL to authority; **443** to `execution_egress_cidrs` when allowlist enabled; pinned DNS and NTP |

## NAT / management gateway (public Primary IPv4)

| Layer | Control |
|-------|---------|
| Hetzner Cloud Firewall | SSH **22** from operator `/32` only |
| Host nftables | Masquerade, SSH from the operator CIDR, and forward only to the tier allowlists plus pinned DNS and NTP. Rules are loaded from `/etc/nftables.conf`. |

Reproduced by Terraform module + `cloud-init-nat-gateway.yaml`.
