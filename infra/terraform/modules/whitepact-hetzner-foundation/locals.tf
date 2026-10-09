# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Hetzner network zones are not derived from location + "-network".
# https://docs.hetzner.com/cloud/general/locations/#network-zones

locals {
  location_to_network_zone = {
    fsn1 = "eu-central"
    nbg1 = "eu-central"
    hel1 = "eu-central"
    ash  = "us-east"
    hil  = "us-west"
    sin  = "ap-southeast"
  }

  network_zone = coalesce(
    var.network_zone_override,
    lookup(local.location_to_network_zone, var.location, null)
  )

  admin_cidr_nft = length(var.admin_cidr_allowlist) > 0 ? join(", ", var.admin_cidr_allowlist) : "127.0.0.1"

  nat_private_ip = var.nat_gateway_private_ip != "" ? var.nat_gateway_private_ip : cidrhost(var.mgmt_subnet_cidr, 10)
  lb_ip          = var.lb_private_ip != "" ? var.lb_private_ip : cidrhost(var.saas_subnet_cidr, 5)

  # Private nodes: SSH only from NAT/management gateway (not operator /32 on private NIC).
  mgmt_ssh_nft = "${local.nat_private_ip}/32"

  saas_nft_input = join("\n          ", [
    "tcp dport 443 ip saddr { ${local.lb_ip}/32 } accept comment \"LB TCP passthrough\"",
    "tcp dport 8765 ip saddr { ${local.lb_ip}/32 } accept comment \"LB health to app\"",
    "tcp dport { 8765, 8766 } ip saddr { ${var.saas_subnet_cidr} } accept",
    "tcp dport 22 ip saddr { ${local.mgmt_ssh_nft} } accept comment \"SSH via bastion\"",
  ])
  saas_nft_output = join("\n          ", concat(
    [
      "tcp dport 5432 ip daddr { ${var.authority_subnet_cidr} } accept",
      "tcp dport 6379 ip daddr { ${var.saas_subnet_cidr} } accept",
    ],
    var.enable_nat_gateway ? ["tcp dport { 80, 443 } accept comment \"egress via NAT (images/updates)\""] : [],
  ))
  authority_nft_input = join("\n          ", [
    "tcp dport 5432 ip saddr { ${var.saas_subnet_cidr}, ${var.execution_subnet_cidr} } accept",
    "tcp dport 22 ip saddr { ${local.mgmt_ssh_nft} } accept comment \"SSH via bastion\"",
  ])
  # Backup and update endpoints belong in authority_egress_cidrs. A trailing
  # "tcp dport 443 accept" made that allowlist dead whenever NAT was enabled:
  # nftables is first-match, and the output chain's default is drop only for
  # destinations that no earlier rule accepted. Do not add an unrestricted
  # HTTPS accept here. Hostname backup still requires the resolved R2 (or
  # update) addresses to be in the allowlist; port 53 is not opened by this
  # chain.
  authority_nft_output = join("\n          ", [
    for cidr in var.authority_egress_cidrs : "tcp dport 443 ip daddr { ${cidr} } accept comment \"authority egress allowlist\""
  ])
  execution_nft_output = concat(
    [
      for cidr in var.execution_egress_cidrs :
      "tcp dport 443 ip daddr { ${cidr} } accept"
      if var.enable_execution_egress_allowlist
    ],
    ["tcp dport 5432 ip daddr { ${var.authority_subnet_cidr} } accept"],
  )
}
