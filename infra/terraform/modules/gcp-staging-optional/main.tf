# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Optional credit-funded staging — production must not depend on this project.

terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-southeast1"
}

variable "billing_budget_amount_usd" {
  description = "Owner-approved monthly ceiling for alerts (not a hard cap unless billing admin configures)"
  type        = number
  default     = 100
}

resource "google_project_service" "required" {
  for_each = toset([
    "compute.googleapis.com",
    "storage.googleapis.com",
    "billingbudgets.googleapis.com",
  ])
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "dr_backup_secondary" {
  name                        = "${var.project_id}-wp-dr-secondary"
  location                    = var.region
  force_destroy               = false
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  encryption {
    default_kms_key_name = null
  }

  labels = {
    product     = "whitepact"
    environment = "staging-dr"
    optional    = "true"
  }
}

# Budget notifications — require billing account ID at apply time (OWNER_APPROVAL_REQUIRED)
