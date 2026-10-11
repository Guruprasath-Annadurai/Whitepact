# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Static checks for the staging Terraform shape. No provider calls."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
FOUNDATION = REPO_ROOT / "infra" / "terraform" / "modules" / "whitepact-hetzner-foundation"
STAGING = REPO_ROOT / "infra" / "terraform" / "environments" / "staging"
ORIGIN_NGINX = REPO_ROOT / "deploy" / "origin" / "nginx-cloudflare-aop.conf"

_HTTPS_ACCEPT = re.compile(r"dport 443|dport \{ 80, 443 \}")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def isolation_defects() -> tuple[str, ...]:
    """Return human-readable defects. An empty tuple means the static checks passed."""
    defects: list[str] = []
    locals_text = _read(FOUNDATION / "locals.tf")
    main_text = _read(FOUNDATION / "main.tf")
    nat_text = _read(FOUNDATION / "templates" / "cloud-init-nat-gateway.yaml")
    tier_text = _read(FOUNDATION / "templates" / "cloud-init-nftables.yaml")
    staging_text = _read(STAGING / "main.tf")
    origin = _read(ORIGIN_NGINX)
    for line in locals_text.splitlines():
        if (
            _HTTPS_ACCEPT.search(line)
            and "accept" in line
            and "ip daddr" not in line
            and "ip saddr" not in line
        ):
            defects.append("Tier or NAT nftables accepts HTTPS without an IP allowlist.")
            break
    if 'tcp dport 443 accept comment "R2 backup upload via NAT"' in locals_text:
        defects.append("Authority egress still adds a world-wide HTTPS accept for NAT.")
    if "depends_on = [hcloud_server.nat_gateway]" not in main_text:
        defects.append("The default route does not wait for the NAT server attachment.")
    if "depends_on = [hcloud_load_balancer_network.saas]" not in main_text:
        defects.append("Load balancer targets do not wait for the private network attachment.")
    if 'include "/etc/nftables.d/whitepact-nat.nft"' not in nat_text:
        defects.append("NAT nftables rules are not loaded from nftables.conf.")
    if "PasswordAuthentication no" not in nat_text or "PasswordAuthentication no" not in tier_text:
        defects.append("SSH password authentication is not explicitly disabled.")
    if (
        "udp sport 68 udp dport 67" not in locals_text
        or "udp sport 67 udp dport 68" not in tier_text
    ):
        defects.append("Private nodes cannot renew DHCP under the drop policy.")
    if not re.search(r"saas_public_ipv4\s*=\s*false", staging_text):
        defects.append("Staging SaaS still requests a public IPv4.")
    if not re.search(r"monthly_cost_ceiling_cents\s*=\s*3595", staging_text):
        defects.append("Staging root is not pinned to the 35.95 EUR ceiling.")
    if "ipv4_enabled = false" not in main_text:
        defects.append("Private tiers are missing an explicit public IPv4 disable.")
    if "data.hcloud_ssh_key" not in staging_text or "admin_ssh_key_ids" not in staging_text:
        defects.append("Staging servers are not bound to the named admin SSH key.")
    if "ssl_verify_client on" not in origin:
        defects.append("Origin nginx does not require an authenticated origin pull certificate.")
    if not re.search(r'lb_service_protocol\s*=\s*"tcp"', staging_text):
        defects.append("Staging load balancer is not TCP passthrough.")
    defects.extend(nat_source_separation_violations(locals_text))
    return tuple(defects)


def _nat_forward_block(locals_text: str) -> str:
    start = locals_text.index("nat_forward_rules = join")
    end = locals_text.index("\n}", start)
    return locals_text[start:end]


def nat_forward_accept_lines(locals_text: str) -> tuple[str, ...]:
    return tuple(line for line in _nat_forward_block(locals_text).splitlines() if "accept" in line)


def nat_cross_tier_forward(locals_text: str, source_var: str, dest_var: str) -> bool:
    """True when one NAT accept line both sources a tier and destinations another."""
    return any(
        source_var in line and dest_var in line for line in nat_forward_accept_lines(locals_text)
    )


def nat_source_separation_violations(locals_text: str) -> tuple[str, ...]:
    """Hostile NAT shapes. Empty means each public allowlist is bound to its source tier."""
    violations: list[str] = []
    lines = nat_forward_accept_lines(locals_text)
    if not lines:
        return ("NAT forward rules are missing.",)
    for line in lines:
        if "ip saddr" not in line:
            violations.append("A NAT forward accept has no source restriction.")
            break
    pairs = (
        (
            "var.saas_subnet_cidr",
            "var.authority_egress_cidrs",
            "SaaS source can reach authority destinations.",
        ),
        (
            "var.saas_subnet_cidr",
            "var.execution_egress_cidrs",
            "SaaS source can reach execution destinations.",
        ),
        (
            "var.authority_subnet_cidr",
            "var.saas_egress_cidrs",
            "Authority source can reach SaaS destinations.",
        ),
        (
            "var.authority_subnet_cidr",
            "var.execution_egress_cidrs",
            "Authority source can reach execution destinations.",
        ),
        (
            "var.execution_subnet_cidr",
            "var.saas_egress_cidrs",
            "Execution source can reach SaaS destinations.",
        ),
        (
            "var.execution_subnet_cidr",
            "var.authority_egress_cidrs",
            "Execution source can reach authority destinations.",
        ),
        (
            "var.mgmt_subnet_cidr",
            "var.saas_egress_cidrs",
            "Management source can reach SaaS destinations.",
        ),
    )
    for source_var, dest_var, message in pairs:
        if nat_cross_tier_forward(locals_text, source_var, dest_var):
            violations.append(message)
    block = _nat_forward_block(locals_text)
    if "var.mgmt_subnet_cidr" in block or "0.0.0.0/0" in block or "::/0" in block:
        violations.append("NAT forward rules include the management subnet or a world route.")
    for source_var, dest_var, label in (
        ("var.saas_subnet_cidr", "var.saas_egress_cidrs", "SaaS"),
        ("var.authority_subnet_cidr", "var.authority_egress_cidrs", "authority"),
        ("var.execution_subnet_cidr", "var.execution_egress_cidrs", "execution"),
    ):
        if not nat_cross_tier_forward(locals_text, source_var, dest_var):
            violations.append(f"{label} tier has no source-restricted NAT allowlist.")
    dns_lines = [line for line in lines if "DNS" in line]
    ntp_lines = [line for line in lines if "NTP" in line]
    if not dns_lines:
        violations.append("NAT forwarding has no source-restricted DNS rule.")
    if not ntp_lines:
        violations.append("NAT forwarding has no source-restricted NTP rule.")
    for line in dns_lines + ntp_lines:
        for source_var in (
            "var.saas_subnet_cidr",
            "var.authority_subnet_cidr",
            "var.execution_subnet_cidr",
        ):
            if source_var not in line:
                violations.append(
                    "DNS or NTP forwarding is not limited to the three workload subnets."
                )
                return tuple(dict.fromkeys(violations))
    return tuple(dict.fromkeys(violations))


OWNER_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    (
        "OWNER-GATE-1",
        "Reply with the exact phrase APPROVE STAGING CLOUD PROVISIONING. That phrase is not granted by this package.",
    ),
    (
        "HCLOUD_TOKEN",
        "Place a Hetzner project token in the operator secret store. Do not commit it.",
    ),
    ("SSH-KEY", "Create the Hetzner SSH key named whitepact-staging-admin before plan."),
    (
        "ADMIN-CIDR",
        "Replace YOUR.PUBLIC.IP.ADDRESS/32 with the operator /32. 0.0.0.0/0 is rejected.",
    ),
    (
        "AUTHORITY-EGRESS",
        "Replace 10.255.0.1/32 with the R2 API ranges the owner accepts. The placeholder does not open the Internet.",
    ),
    (
        "SAAS-EGRESS",
        "Replace 10.255.0.3/32 with the package mirror or registry ranges the owner accepts.",
    ),
    (
        "EXECUTION-EGRESS",
        "Replace 203.0.113.10/32 with the governed MCP upstream ranges. TEST-NET-3 is not a customer destination.",
    ),
    (
        "CLOUDFLARE",
        "Decide whether the first apply includes Cloudflare. The staging root does not. DNS stays unchanged.",
    ),
    (
        "R2-SECRETS",
        "Provide R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET, R2_ENDPOINT, and WHITEPACT_BACKUP_ENCRYPTION_KEY outside git.",
    ),
    (
        "APP-SECRETS",
        "Provide POSTGRES_PASSWORD on the authority host and REDIS_PASSWORD on the SaaS host. Do not copy the authority owner password to the execution tier.",
    ),
    (
        "EXECUTION-DB-ROLE",
        "Set WHITEPACT_EXECUTION_DB_PASSWORD for role whitepact_execution. It must differ from POSTGRES_PASSWORD. Apply infra/postgres/whitepact_execution_role.sql as the migrator after migrations.",
    ),
    (
        "ORIGIN-AOP-MATERIAL",
        "The staging root does not instantiate Cloudflare, authenticated origin pulls, the client CA, or the origin certificate and key. The nginx file is not a live control until those artifacts exist.",
    ),
    (
        "BILLING-ALERT",
        "The 3595 cent figure is a Terraform price-book ceiling. It is not a Hetzner billing alert. VAT and server backups are outside it.",
    ),
    (
        "PR172-ANCESTRY",
        "This branch is based on 6fefece7b7620ae2f1fa7c307f6720e4bbde709f. Current PR #172 head 7a0852899afd997264c384a9ff5ca5f99a65c7ca is not an ancestor.",
    ),
    (
        "BACKUP-DELETE",
        "Retention deletion stays dry-run until the owner passes --delete on a reviewed plan.",
    ),
    (
        "VAT",
        "35.95 EUR is exclusive of VAT. A German 19 percent VAT invoice would be 42.7805 EUR. Confirm the billing country.",
    ),
    (
        "LIVE-ACCEPTANCE",
        "Offline tests are not staging acceptance. Do not mark Phase 4 live checks passed from this package.",
    ),
    (
        "ANTIGRAVITY",
        "Independent review of this successor is still required. PR #171 at 6801d4ad is not modified. PR #172's current head is 7a0852899afd997264c384a9ff5ca5f99a65c7ca and is not this branch's base.",
    ),
)

PREFLIGHT_BASE_SHA = "6fefece7b7620ae2f1fa7c307f6720e4bbde709f"
PREFLIGHT_BASE_TREE = "043b5f14f63b32ea60d3c168d4fcf3bf27800d14"
PR_172_HEAD_SHA = "7a0852899afd997264c384a9ff5ca5f99a65c7ca"
PR_172_HEAD_IS_ANCESTOR = False
PR_171_SHA = "6801d4ad0047d15a196ab9caeffacf54f9ce557e"
