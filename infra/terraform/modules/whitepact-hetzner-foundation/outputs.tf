# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

output "network_id" {
  value = hcloud_network.private.id
}

output "load_balancer_ipv4" {
  description = "Origin for Cloudflare A/AAAA record (orange-cloud proxied)"
  value       = hcloud_load_balancer.saas.ipv4
}

output "nat_gateway_public_ipv4" {
  description = "Operator SSH / WireGuard entry (not in app request path)"
  value       = var.enable_nat_gateway ? hcloud_server.nat_gateway[0].ipv4_address : null
}

output "nat_gateway_private_ip" {
  value = var.enable_nat_gateway ? local.nat_private_ip : null
}

output "saas_private_ips" {
  value = [for s in hcloud_server.saas : one([for n in s.network : n.ip])]
}

output "authority_private_ip" {
  value = one([for n in hcloud_server.authority.network : n.ip])
}

output "execution_private_ips" {
  value = [for s in hcloud_server.execution : one([for n in s.network : n.ip])]
}
