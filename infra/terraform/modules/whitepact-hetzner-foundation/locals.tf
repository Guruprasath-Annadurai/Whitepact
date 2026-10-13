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

  saas_nft_input = join("\n          ", [
    "tcp dport { 8765, 8766 } ip saddr { ${var.saas_subnet_cidr} } accept",
  ])
  saas_nft_output = join("\n          ", [
    "tcp dport 5432 ip daddr { ${var.authority_subnet_cidr} } accept",
    "tcp dport 6379 ip daddr { ${var.saas_subnet_cidr} } accept",
  ])
  authority_nft_input = join("\n          ", [
    "tcp dport 5432 ip saddr { ${var.saas_subnet_cidr}, ${var.execution_subnet_cidr} } accept",
  ])
  authority_nft_output = join("\n          ", [
    for cidr in var.authority_egress_cidrs : "tcp dport 443 ip daddr { ${cidr} } accept"
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
