# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.49"
    }
  }
}
