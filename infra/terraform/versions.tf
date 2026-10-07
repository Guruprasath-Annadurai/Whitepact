# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Provider pins for WhitePact Enterprise Cloud V1 (not applied without owner approval).

terraform {
  required_version = ">= 1.6.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.43"
    }
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}
