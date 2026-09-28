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
  network_zone = "${var.location}-network"
  ip_range     = var.saas_subnet_cidr
}

resource "hcloud_network_subnet" "authority" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = "${var.location}-network"
  ip_range     = var.authority_subnet_cidr
}

resource "hcloud_network_subnet" "execution" {
  network_id   = hcloud_network.private.id
  type         = "cloud"
  network_zone = "${var.location}-network"
  ip_range     = var.execution_subnet_cidr
}

# --- SaaS / dashboard / MCP ingress (private NIC; public via LB + Cloudflare only) ---
resource "hcloud_firewall" "saas" {
  name = "${local.name_prefix}-fw-saas"
  labels = merge(local.common_labels, { tier = "saas" })

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = length(var.admin_cidr_allowlist) > 0 ? var.admin_cidr_allowlist : ["127.0.0.1/32"]
    description = "SSH admin allowlist only"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "8765"
    source_ips = ["10.42.0.0/16"]
    description = "Dashboard/API from private network (LB origin)"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "8766"
    source_ips = ["10.42.0.0/16"]
    description = "MCP HTTP from private network"
  }

  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "5432"
    destination_ips = [var.authority_subnet_cidr]
    description     = "PostgreSQL to authority/data tier"
  }

  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "6379"
    destination_ips = [var.saas_subnet_cidr]
    description     = "Redis on saas subnet if colocated"
  }
}

resource "hcloud_firewall" "authority" {
  name   = "${local.name_prefix}-fw-authority"
  labels = merge(local.common_labels, { tier = "authority" })

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "5432"
    source_ips = [var.saas_subnet_cidr, var.execution_subnet_cidr]
    description = "PostgreSQL only from app/execution tiers"
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = length(var.admin_cidr_allowlist) > 0 ? var.admin_cidr_allowlist : ["127.0.0.1/32"]
  }

  # Authority tier: no broad outbound — signing/policy material must not egress to execution
  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "443"
    destination_ips = ["0.0.0.0/0"]
    description     = "Package updates and backup upload endpoints only (tighten with allowlist)"
  }
}

resource "hcloud_firewall" "execution" {
  name   = "${local.name_prefix}-fw-execution"
  labels = merge(local.common_labels, { tier = "execution" })

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = length(var.admin_cidr_allowlist) > 0 ? var.admin_cidr_allowlist : ["127.0.0.1/32"]
  }

  dynamic "rule" {
    for_each = var.enable_execution_egress_allowlist ? [1] : []
    content {
      direction       = "out"
      protocol        = "tcp"
      port            = "443"
      destination_ips = length(var.execution_egress_cidrs) > 0 ? var.execution_egress_cidrs : ["0.0.0.0/0"]
      description     = "Documented MCP/upstream egress"
    }
  }

  rule {
    direction       = "out"
    protocol        = "tcp"
    port            = "5432"
    destination_ips = [var.authority_subnet_cidr]
    description     = "Nonce/audit admission only — not policy signing"
  }
}

resource "hcloud_server" "saas" {
  count       = var.environment == "production" ? 2 : 1
  name        = "${local.name_prefix}-saas-${count.index + 1}"
  server_type = var.saas_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  labels      = merge(local.common_labels, { tier = "saas", role = "dashboard-mcp" })

  public_net {
    ipv4_enabled = true
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.saas_subnet_cidr, 10 + count.index)
  }

  firewall_ids = [hcloud_firewall.saas.id]
}

resource "hcloud_server" "authority" {
  name        = "${local.name_prefix}-authority-1"
  server_type = var.authority_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  labels      = merge(local.common_labels, { tier = "authority", role = "postgres-governance" })

  public_net {
    ipv4_enabled = false
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.authority_subnet_cidr, 10)
  }

  firewall_ids = [hcloud_firewall.authority.id]
}

resource "hcloud_server" "execution" {
  count       = var.environment == "production" ? 2 : 1
  name        = "${local.name_prefix}-exec-${count.index + 1}"
  server_type = var.execution_server_type
  location    = var.location
  image       = "ubuntu-24.04"
  labels      = merge(local.common_labels, { tier = "execution", role = "isolated-executor" })

  public_net {
    ipv4_enabled = false
    ipv6_enabled = false
  }

  network {
    network_id = hcloud_network.private.id
    ip         = cidrhost(var.execution_subnet_cidr, 10 + count.index)
  }

  firewall_ids = [hcloud_firewall.execution.id]
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

resource "hcloud_load_balancer_service" "http" {
  load_balancer_id = hcloud_load_balancer.saas.id
  protocol         = "http"
  listen_port      = 80
  destination_port = 8765

  health_check {
    protocol = "http"
    port     = 8765
    interval = 15
    timeout  = 10
    retries  = 3
    http {
      path         = "/livez"
      status_codes = ["2??", "3??"]
    }
  }
}
