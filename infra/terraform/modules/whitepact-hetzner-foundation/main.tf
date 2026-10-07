# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Trust boundaries: SaaS/API, authority engine, execution — separate subnets and firewalls.
# Databases are not exposed on public interfaces; attach via private network only.

locals {
  name_prefix = "wp-${var.environment}"
  common_labels = merge(var.labels, {
    product     = "whitepact"
    environment = var.environment
    managed_by  = "terraform"
  })
}

resource "hcloud_network" "private" {
  name     = "${local.name_prefix}-net"
  ip_range = var.network_cidr
  labels   = local.common_labels
}

resource "hcloud_network_subnet" "saas" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = local.network_zone
  ip_range     = var.saas_subnet_cidr
}

resource "hcloud_network_subnet" "authority" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = local.network_zone
  ip_range     = var.authority_subnet_cidr
}

resource "hcloud_network_subnet" "execution" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = local.network_zone
  ip_range     = var.execution_subnet_cidr
}

resource "hcloud_network_subnet" "mgmt" {
  count        = var.enable_nat_gateway ? 1 : 0
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = local.network_zone
  ip_range     = var.mgmt_subnet_cidr
}

resource "hcloud_network_route" "default_via_nat" {
  count       = var.enable_nat_gateway ? 1 : 0
  network_id  = hcloud_network.private.id
  destination = "0.0.0.0/0"
  gateway     = local.nat_private_ip
}

# Hetzner Cloud Firewalls cannot be applied to servers without a public network interface
# (see Firewall FAQ: "no public IP" may prevent application). Private tiers use host nftables.

resource "hcloud_firewall" "nat_gateway" {
  count  = var.enable_nat_gateway ? 1 : 0
  name   = "${local.name_prefix}-fw-nat"
  labels = merge(local.common_labels, { tier = "nat-mgmt" })

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = length(var.admin_cidr_allowlist) > 0 ? var.admin_cidr_allowlist : ["127.0.0.1/32"]
    description = "Operator SSH to management gateway only"
  }
}

resource "hcloud_firewall" "saas_public" {
  count  = var.saas_public_ipv4 ? 1 : 0
  name   = "${local.name_prefix}-fw-saas-public"
  labels = merge(local.common_labels, { tier = "saas" })

  rule {
    direction   = "in"
    protocol    = "tcp"
    port        = "22"
    source_ips  = length(var.admin_cidr_allowlist) > 0 ? var.admin_cidr_allowlist : ["127.0.0.1/32"]
    description = "SSH when SaaS retains public IPv4 (non-staging)"
  }
}

resource "hcloud_server" "nat_gateway" {
  count       = var.enable_nat_gateway ? 1 : 0
  name        = "${local.name_prefix}-nat-1"
  server_type = var.nat_gateway_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = var.admin_ssh_key_ids
  labels      = merge(local.common_labels, { tier = "nat", role = "mgmt-egress" })

  user_data = templatefile("${path.module}/templates/cloud-init-nat-gateway.yaml", {
    admin_cidrs   = local.admin_cidr_nft
    public_iface  = "eth0"
    private_iface = "enp7s0"
  })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = local.nat_private_ip
  }

  firewall_ids = [hcloud_firewall.nat_gateway[0].id]

  depends_on = [hcloud_network_subnet.mgmt]
}

resource "hcloud_server" "saas" {
  count       = var.environment == "production" ? 2 : 1
  name        = "${local.name_prefix}-saas-${count.index + 1}"
  server_type = var.saas_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = var.admin_ssh_key_ids
  labels      = merge(local.common_labels, { tier = "saas", role = "dashboard-mcp" })

  user_data = templatefile("${path.module}/templates/cloud-init-nftables.yaml", {
    admin_cidrs       = local.admin_cidr_nft
    tier_input_rules  = local.saas_nft_input
    tier_output_rules = local.saas_nft_output
  })

  public_net {
    ipv4_enabled = var.saas_public_ipv4
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.saas_subnet_cidr, 10 + count.index)
  }

  firewall_ids = var.saas_public_ipv4 ? [hcloud_firewall.saas_public[0].id] : []
}

resource "hcloud_server" "authority" {
  name        = "${local.name_prefix}-authority-1"
  server_type = var.authority_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = var.admin_ssh_key_ids
  labels      = merge(local.common_labels, { tier = "authority", role = "postgres-governance" })

  user_data = templatefile("${path.module}/templates/cloud-init-nftables.yaml", {
    admin_cidrs       = local.admin_cidr_nft
    tier_input_rules  = local.authority_nft_input
    tier_output_rules = local.authority_nft_output
  })

  public_net {
    ipv4_enabled = false
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.authority_subnet_cidr, 10)
  }

}

resource "hcloud_server" "execution" {
  count       = var.environment == "production" ? 2 : 1
  name        = "${local.name_prefix}-exec-${count.index + 1}"
  server_type = var.execution_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  ssh_keys    = var.admin_ssh_key_ids
  labels      = merge(local.common_labels, { tier = "execution", role = "isolated-executor" })

  user_data = templatefile("${path.module}/templates/cloud-init-nftables.yaml", {
    admin_cidrs       = local.admin_cidr_nft
    tier_input_rules  = "tcp dport 22 ip saddr { ${local.mgmt_ssh_nft} } accept comment \"SSH via bastion\""
    tier_output_rules = join("\n          ", local.execution_nft_output)
  })

  public_net {
    ipv4_enabled = false
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.execution_subnet_cidr, 10 + count.index)
  }

}

resource "hcloud_load_balancer" "saas" {
  name               = "${local.name_prefix}-lb-saas"
  load_balancer_type = "lb11"
  location           = var.location
  labels             = local.common_labels
}

resource "hcloud_load_balancer_network" "saas" {
  load_balancer_id = hcloud_load_balancer.saas.id
  network_id       = hcloud_network.private.id
  ip               = cidrhost(var.saas_subnet_cidr, 5)
}

resource "hcloud_load_balancer_target" "saas" {
  count            = length(hcloud_server.saas)
  type             = "server"
  load_balancer_id = hcloud_load_balancer.saas.id
  server_id        = hcloud_server.saas[count.index].id
  use_private_ip   = true
}

resource "hcloud_load_balancer_service" "public" {
  load_balancer_id = hcloud_load_balancer.saas.id
  protocol         = var.lb_service_protocol
  listen_port      = var.lb_listen_port
  destination_port = var.lb_destination_port

  health_check {
    protocol = var.lb_health_check_protocol
    port     = var.lb_health_check_port
    interval = 15
    timeout  = 10
    retries  = 3

    dynamic "http" {
      for_each = contains(["http", "https"], var.lb_health_check_protocol) ? [1] : []
      content {
        path         = "/livez"
        status_codes = ["2??", "3??"]
      }
    }
  }
}
