# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# PRODUCTION topology — apply only after OWNER_APPROVAL_REQUIRED on monthly ceiling.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}

provider "hcloud" {}

module "foundation" {
  source = "../../modules/whitepact-hetzner-foundation"

  environment           = "production"
  location              = var.location
  saas_server_type      = var.saas_server_type
  authority_server_type = var.authority_server_type
  execution_server_type = var.execution_server_type
  admin_cidr_allowlist  = var.admin_cidr_allowlist
  execution_egress_cidrs = var.execution_egress_cidrs
  authority_egress_cidrs = var.authority_egress_cidrs
  labels = {
    cost_tier = "production"
  }
}
