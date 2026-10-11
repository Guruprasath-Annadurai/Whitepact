# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# DEVELOPMENT-ONLY sizing. Not production qualification without owner-approved production tfvars.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

provider "hcloud" {
  # HCLOUD_TOKEN from environment — never commit
}

module "foundation" {
  source = "../../modules/whitepact-hetzner-foundation"

  environment         = "development"
  location            = var.location
  saas_server_type    = "cx22"
  authority_server_type = "cx22"
  execution_server_type = "cx22"
  admin_cidr_allowlist  = var.admin_cidr_allowlist
  execution_egress_cidrs  = var.execution_egress_cidrs
  authority_egress_cidrs  = var.authority_egress_cidrs
  labels = {
    cost_tier = "dev-minimum"
  }
}
