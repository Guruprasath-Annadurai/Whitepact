# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

variable "environment" {
  description = "deployment label: development | production"
  type        = string
  validation {
    condition     = contains(["development", "production"], var.environment)
    error_message = "environment must be development or production"
  }
}

variable "location" {
  description = "Hetzner location (verify availability: https://docs.hetzner.com/cloud/general/locations/)"
  type        = string
  default     = "fsn1"
}

variable "network_cidr" {
  type    = string
  default = "10.42.0.0/16"
}

variable "saas_subnet_cidr" {
  type    = string
  default = "10.42.1.0/24"
}

variable "authority_subnet_cidr" {
  type    = string
  default = "10.42.2.0/24"
}

variable "execution_subnet_cidr" {
  type    = string
  default = "10.42.3.0/24"
}

variable "admin_cidr_allowlist" {
  description = "CIDRs permitted for SSH/bastion (no 0.0.0.0/0 on database paths)"
  type        = list(string)
  default     = []
}

variable "saas_server_type" {
  type    = string
  default = "cx22"
}

variable "authority_server_type" {
  type    = string
  default = "cx22"
}

variable "execution_server_type" {
  type    = string
  default = "cx22"
}

variable "enable_execution_egress_allowlist" {
  description = "When true, execution nodes only egress to documented destinations"
  type        = bool
  default     = true
}

variable "execution_egress_cidrs" {
  description = "Permitted outbound CIDRs for agent execution workloads (e.g. MCP upstreams)"
  type        = list(string)
  default     = []
}

variable "labels" {
  type    = map(string)
  default = {}
}
