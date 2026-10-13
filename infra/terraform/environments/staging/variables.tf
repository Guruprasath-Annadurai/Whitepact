# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

variable "location" {
  type    = string
  default = "fsn1"
}

variable "saas_server_type" {
  description = "SaaS/dashboard/MCP tier (see Hetzner Cloud pricing)"
  type        = string
  default     = "cx33"
}

variable "authority_server_type" {
  type    = string
  default = "cx33"
}

variable "execution_server_type" {
  type    = string
  default = "cx23"
}

variable "admin_cidr_allowlist" {
  description = "Operator SSH source CIDRs (never 0.0.0.0/0 on DB paths)"
  type        = list(string)
}

variable "execution_egress_cidrs" {
  type = list(string)
}

variable "authority_egress_cidrs" {
  type = list(string)
}
