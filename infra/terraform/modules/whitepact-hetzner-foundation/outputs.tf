# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

output "network_id" {
  value = hcloud_network.private.id
}

output "load_balancer_ipv4" {
  description = "Origin for Cloudflare A/AAAA record (orange-cloud proxied)"
  value       = hcloud_load_balancer.saas.ipv4
}

output "saas_private_ips" {
  value = [for s in hcloud_server.saas : s.network[0].ip]
}

output "authority_private_ip" {
  value = hcloud_server.authority.network[0].ip
}

output "execution_private_ips" {
  value = [for s in hcloud_server.execution : s.network[0].ip]
}
