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

  nat_private_ip    = var.nat_gateway_private_ip != "" ? var.nat_gateway_private_ip : cidrhost(var.mgmt_subnet_cidr, 10)
  lb_ip             = var.lb_private_ip != "" ? var.lb_private_ip : cidrhost(var.saas_subnet_cidr, 5)
  nat_public_iface  = "eth0"
  nat_private_iface = "enp7s0"

  # Private nodes: SSH only from NAT/management gateway (not operator /32 on private NIC).
  mgmt_ssh_nft = "${local.nat_private_ip}/32"

  dns_nft = join(", ", var.dns_resolver_cidrs)
  ntp_nft = join(", ", var.ntp_server_cidrs)

  # Name service and time sync are required for TLS. They are pinned resolvers,
  # not a substitute for the tier HTTPS allowlists.
  infra_nft_output = [
    "udp dport 53 ip daddr { ${local.dns_nft} } accept comment \"DNS\"",
    "tcp dport 53 ip daddr { ${local.dns_nft} } accept comment \"DNS TCP\"",
    "udp dport 123 ip daddr { ${local.ntp_nft} } accept comment \"NTP\"",
    "udp sport 68 udp dport 67 accept comment \"DHCP renew\"",
  ]

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
      "tcp dport { 80, 443 } ip daddr { ${join(", ", var.saas_egress_cidrs)} } accept comment \"saas egress allowlist\"",
    ],
    local.infra_nft_output,
  ))
  authority_nft_input = join("\n          ", [
    "tcp dport 5432 ip saddr { ${var.saas_subnet_cidr}, ${var.execution_subnet_cidr} } accept",
    "tcp dport 22 ip saddr { ${local.mgmt_ssh_nft} } accept comment \"SSH via bastion\"",
  ])
  # Backup and update endpoints belong in authority_egress_cidrs. A trailing
  # "tcp dport 443 accept" made that allowlist dead whenever NAT was enabled:
  # nftables is first-match, and the output chain's default is drop only for
  # destinations that no earlier rule accepted. Do not add an unrestricted
  # HTTPS accept here. Pinned DNS and NTP stay in infra_nft_output. They are
  # not a substitute for the HTTPS allowlist.
  authority_nft_output = join("\n          ", concat(
    ["tcp dport 443 ip daddr { ${join(", ", var.authority_egress_cidrs)} } accept comment \"authority egress allowlist\""],
    local.infra_nft_output,
  ))
  execution_nft_output = concat(
    [
      for cidr in var.execution_egress_cidrs :
      "tcp dport 443 ip daddr { ${cidr} } accept"
      if var.enable_execution_egress_allowlist
    ],
    ["tcp dport 5432 ip daddr { ${var.authority_subnet_cidr} } accept comment \"authority admission\""],
    local.infra_nft_output,
  )

  # Each tier may use only its own public destinations. A compromised host on one
  # private subnet must not be forwarded to another tier's allowlist. DNS and NTP
  # stay shared infrastructure, and only the three workload subnets may reach them.
  # The management subnet is not a workload source.
  nat_forward_rules = join("\n          ", concat(
    [
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.saas_subnet_cidr} } ip daddr { ${join(", ", var.saas_egress_cidrs)} } tcp dport { 80, 443 } accept comment \"saas allowlist\"",
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.authority_subnet_cidr} } ip daddr { ${join(", ", var.authority_egress_cidrs)} } tcp dport 443 accept comment \"authority allowlist\"",
    ],
    var.enable_execution_egress_allowlist ? [
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.execution_subnet_cidr} } ip daddr { ${join(", ", var.execution_egress_cidrs)} } tcp dport 443 accept comment \"execution allowlist\"",
    ] : [],
    [
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.saas_subnet_cidr}, ${var.authority_subnet_cidr}, ${var.execution_subnet_cidr} } ip daddr { ${local.dns_nft} } udp dport 53 accept comment \"DNS\"",
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.saas_subnet_cidr}, ${var.authority_subnet_cidr}, ${var.execution_subnet_cidr} } ip daddr { ${local.dns_nft} } tcp dport 53 accept comment \"DNS TCP\"",
      "iif \"${local.nat_private_iface}\" oif \"${local.nat_public_iface}\" ip saddr { ${var.saas_subnet_cidr}, ${var.authority_subnet_cidr}, ${var.execution_subnet_cidr} } ip daddr { ${local.ntp_nft} } udp dport 123 accept comment \"NTP\"",
    ],
  ))

  # The origin listener is staged on SaaS only. Cloud-init must not start it:
  # the Cloudflare client CA, origin certificate, and origin key are not in this module.
  saas_origin_write_files = <<EOT
  - path: /etc/nginx/sites-available/whitepact-origin.conf
    permissions: "0644"
    content: |
      ${replace(file("${path.module}/../../../../deploy/origin/nginx-cloudflare-aop.conf"), "\n", "\n      ")}
  - path: /var/lib/whitepact/origin-aop.contract
    permissions: "0644"
    content: |
      listener=staged
      start_without_client_ca=forbidden
      start_without_origin_certificate=forbidden
EOT
  saas_origin_runcmd      = <<EOT
  - [bash, -lc, "install -d /var/lib/whitepact /etc/whitepact/origin"]
  - [bash, -lc, "if test -s /etc/whitepact/origin/cloudflare-aop-ca.pem && test -s /etc/whitepact/origin/server.crt && test -s /etc/whitepact/origin/server.key; then echo ORIGIN_AOP_MATERIAL_PRESENT > /var/lib/whitepact/origin-aop.status; else echo ORIGIN_AOP_MATERIAL_MISSING > /var/lib/whitepact/origin-aop.status; fi"]
EOT
}
