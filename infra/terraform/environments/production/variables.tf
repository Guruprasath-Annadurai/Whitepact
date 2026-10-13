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
