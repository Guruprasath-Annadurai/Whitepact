# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# STAGING — apply only after OWNER APPROVAL (see docs/enterprise/cloud/CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md).

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

  environment             = "staging"
  location                = var.location
  saas_server_type        = var.saas_server_type
  authority_server_type   = var.authority_server_type
  execution_server_type   = var.execution_server_type
  admin_cidr_allowlist    = var.admin_cidr_allowlist
  execution_egress_cidrs  = var.execution_egress_cidrs
  authority_egress_cidrs  = var.authority_egress_cidrs
  saas_public_ipv4        = false

  labels = {
    cost_tier   = "staging"
    m6_sha      = "ee6e4a26becf7e89a933202651fba3b4e7a8176d"
    qualification = "antigravity-pending"
  }
}
