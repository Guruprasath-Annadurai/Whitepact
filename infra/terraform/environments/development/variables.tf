variable "location" {
  type    = string
  default = "fsn1"
}

variable "admin_cidr_allowlist" {
  type    = list(string)
  default = []
}

variable "execution_egress_cidrs" {
  type    = list(string)
  default = []
}
