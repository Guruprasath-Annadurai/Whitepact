variable "location" {
  type    = string
  default = "fsn1"
}

variable "saas_server_type" {
  type    = string
  default = "cx32"
}

variable "authority_server_type" {
  type    = string
  default = "cx32"
}

variable "execution_server_type" {
  type    = string
  default = "cx22"
}

variable "admin_cidr_allowlist" {
  type = list(string)
}

variable "execution_egress_cidrs" {
  type = list(string)
}

variable "authority_egress_cidrs" {
  type = list(string)
}

variable "saas_egress_cidrs" {
  description = "Explicit SaaS HTTP(S) destinations. Required before any production plan."
  type        = list(string)
}

variable "admin_ssh_key_ids" {
  description = "Hetzner SSH key IDs. Production servers are not created without one."
  type        = list(string)
}
