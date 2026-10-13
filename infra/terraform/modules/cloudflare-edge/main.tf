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

# Route-aware WAF, rate limits, TLS, and authenticated origin pulls are in gate2.tf.
# Plan-specific resources stay at count 0 unless both the enable flag and the plan flag are true.

variable "enable_origin_protection" {
  description = "When true, documents orange-cloud + authenticated origin pull (requires paid plan features)."
  type        = bool
  default     = false
}

variable "admin_hostname" {
  description = "Hostname for WhitePact Cloud admin ingress (Cloudflare Access + Tunnel)."
  type        = string
  default     = ""
}

# Stub: Cloudflare Tunnel for admin plane — apply only with owner approval and account credentials.
# Same arguments as the deprecated cloudflare_tunnel resource. count stays 0 unless
# admin_hostname is set, so this replacement does not describe a live tunnel.
resource "cloudflare_zero_trust_tunnel_cloudflared" "admin" {
  count      = var.admin_hostname != "" ? 1 : 0
  account_id = var.cloudflare_account_id
  name       = "whitepact-cloud-admin"
  secret     = var.tunnel_secret_placeholder
}

moved {
  from = cloudflare_tunnel.admin
  to   = cloudflare_zero_trust_tunnel_cloudflared.admin
}

variable "cloudflare_account_id" {
  type    = string
  default = ""
}

variable "tunnel_secret_placeholder" {
  description = "Replace at apply time via TF_VAR or secrets manager — never commit a real secret."
  type        = string
  default     = "REPLACE_BEFORE_APPLY"
  sensitive   = true
}

output "record_id" {
  value = cloudflare_record.app.id
}
