# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

variable "environment" {
  description = "deployment label: development | production"
  type        = string
  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "environment must be development, staging, or production"
  }
}

variable "location" {
  description = "Hetzner location (verify availability: https://docs.hetzner.com/cloud/general/locations/)"
  type        = string
  default     = "fsn1"

  validation {
    condition     = contains(["fsn1", "nbg1", "hel1", "ash", "hil", "sin"], var.location)
    error_message = "location must be a documented Hetzner Cloud region with a known network zone mapping."
  }
}

variable "network_zone_override" {
  description = "Optional override when Hetzner adds a new location before the module map is updated."
  type        = string
  default     = null
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

variable "mgmt_subnet_cidr" {
  description = "Management / NAT gateway subnet"
  type        = string
  default     = "10.42.4.0/24"
}

variable "enable_nat_gateway" {
  description = "Dedicated public NAT/management gateway for private-only nodes (required for egress)."
  type        = bool
  default     = true
}

variable "nat_gateway_server_type" {
  description = "Smallest suitable SKU with public Primary IPv4 (staging: CX23)."
  type        = string
  default     = "cx23"
}

variable "nat_gateway_private_ip" {
  description = "Private IP of NAT gateway (must not be network first IP or 172.31.1.1)."
  type        = string
  default     = ""
}

variable "lb_private_ip" {
  description = "Load balancer private IP on saas subnet (for host firewall rules)."
  type        = string
  default     = ""
}

variable "admin_cidr_allowlist" {
  description = "CIDRs permitted for SSH/bastion (no 0.0.0.0/0 on database paths)"
  type        = list(string)
  default     = []
}

variable "admin_ssh_key_ids" {
  description = "Hetzner SSH key IDs installed on administered servers. A key that exists only in the project is not installed unless listed here."
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

  validation {
    condition = (
      !var.enable_execution_egress_allowlist
      || length(var.execution_egress_cidrs) > 0
    )
    error_message = "execution_egress_cidrs must be non-empty when enable_execution_egress_allowlist is true (fail closed)."
  }
}

variable "authority_egress_cidrs" {
  description = "Permitted outbound HTTPS destinations for authority tier (updates, telemetry, R2 backup API endpoints)."
  type        = list(string)
  default     = ["10.255.0.1/32"]

  validation {
    condition = (
      length(var.authority_egress_cidrs) > 0
      && !contains(var.authority_egress_cidrs, "0.0.0.0/0")
    )
    error_message = "authority_egress_cidrs must be a non-empty explicit allowlist (no 0.0.0.0/0)."
  }
}

variable "saas_public_ipv4" {
  description = "When false, SaaS nodes are reachable only via private LB + Cloudflare (recommended for production)."
  type        = bool
  default     = false
}

variable "labels" {
  type    = map(string)
  default = {}
}

variable "lb_service_protocol" {
  description = "LB frontend protocol: http, https (TLS terminates at LB), or tcp (passthrough for origin TLS/AOP)."
  type        = string
  default     = "http"

  validation {
    condition     = contains(["http", "https", "tcp"], var.lb_service_protocol)
    error_message = "lb_service_protocol must be http, https, or tcp."
  }
}

variable "lb_listen_port" {
  type    = number
  default = 80
}

variable "lb_destination_port" {
  type    = number
  default = 8765
}

variable "lb_health_check_protocol" {
  description = "Health check protocol (can differ from frontend, e.g. tcp:443 public + http:8765 /livez)."
  type        = string
  default     = "http"
}

variable "lb_health_check_port" {
  type    = number
  default = 8765
}
