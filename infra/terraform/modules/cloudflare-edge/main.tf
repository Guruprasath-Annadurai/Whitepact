# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# DNS/TLS/CDN — do not apply until owner approves cutover (PRODUCTION_CUTOVER.md).

terraform {
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.43"
    }
  }
}

variable "zone_id" {
  type = string
}

variable "hostname" {
  type = string
}

variable "origin_ipv4" {
  description = "Hetzner load balancer IPv4 (not database)"
  type        = string
}

variable "proxied" {
  type    = bool
  default = true
}

resource "cloudflare_record" "app" {
  zone_id = var.zone_id
  name    = var.hostname
  content = var.origin_ipv4
  type    = "A"
  proxied = var.proxied
  ttl     = 1
}

# Rate limiting / WAF rules depend on plan — configure in dashboard or Rulesets API after plan verification.

output "record_id" {
  value = cloudflare_record.app.id
}
