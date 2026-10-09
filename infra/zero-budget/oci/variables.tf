variable "authorization_gate" {
  type        = string
  default     = "HOLD"
  description = "HOLD refuses plan/apply. AUTHORIZED_BY_OWNER is not a sufficient approval by itself; oci/apply.sh still refuses mutation."

  validation {
    condition     = contains(["HOLD", "AUTHORIZED_BY_OWNER"], var.authorization_gate)
    error_message = "authorization_gate must be HOLD or AUTHORIZED_BY_OWNER."
  }
}

variable "region" {
  type        = string
  description = "Tenancy home region. Always Free compute is home-region only."

  validation {
    condition     = length(var.region) > 0 && !strcontains(var.region, " ")
    error_message = "region must be the tenancy home region identifier."
  }
}

variable "availability_domain" {
  type        = string
  description = "Availability domain name inside the home region. Do not switch regions to chase capacity."

  validation {
    condition     = length(var.availability_domain) > 0
    error_message = "availability_domain is required."
  }
}

variable "tenancy_ocid" {
  type        = string
  description = "Tenancy OCID. Supplied at plan time from the operator environment, never committed."

  validation {
    condition     = startswith(var.tenancy_ocid, "ocid1.tenancy.oc1.")
    error_message = "tenancy_ocid must be an ocid1.tenancy.oc1 identifier."
  }
}

variable "user_ocid" {
  type        = string
  description = "OCI API user OCID. Not a WhitePact governance identity."

  validation {
    condition     = startswith(var.user_ocid, "ocid1.user.oc1.")
    error_message = "user_ocid must be an ocid1.user.oc1 identifier."
  }
}

variable "compartment_ocid" {
  type        = string
  description = "Dedicated compartment for this candidate. Do not reuse a production compartment."

  validation {
    condition     = startswith(var.compartment_ocid, "ocid1.compartment.oc1.")
    error_message = "compartment_ocid must be an ocid1.compartment.oc1 identifier."
  }
}

variable "compartment_quota_name" {
  type        = string
  description = "Compartment name or parent:child path used in the quota statement."

  validation {
    condition     = length(var.compartment_quota_name) > 0 && !strcontains(var.compartment_quota_name, "\"")
    error_message = "compartment_quota_name must be a non-empty quota-statement compartment path."
  }
}

variable "api_key_fingerprint" {
  type        = string
  description = "Fingerprint of the API key that lives outside the repository."

  validation {
    condition     = length(var.api_key_fingerprint) > 0
    error_message = "api_key_fingerprint is required and must not be committed."
  }
}

variable "api_private_key_path" {
  type        = string
  description = "Local path to the API private key. The key file must stay outside git."

  validation {
    condition     = length(var.api_private_key_path) > 0 && !strcontains(var.api_private_key_path, "..")
    error_message = "api_private_key_path must be an explicit local path."
  }
}

variable "ssh_public_key" {
  type        = string
  description = "Operator SSH public key only."

  validation {
    condition     = startswith(var.ssh_public_key, "ssh-ed25519 ") || startswith(var.ssh_public_key, "ssh-rsa ")
    error_message = "ssh_public_key must be an ssh-ed25519 or ssh-rsa public key."
  }
}

variable "image_ocid" {
  type        = string
  description = "Always Free Eligible Ubuntu aarch64 image OCID in the home region. Platform images that are not Always Free Eligible can bill."

  validation {
    condition     = startswith(var.image_ocid, "ocid1.image.oc1.")
    error_message = "image_ocid must be an ocid1.image.oc1 identifier for an Always Free Eligible ARM image."
  }
}

variable "operator_cidr" {
  type        = string
  description = "Operator CIDR allowed to open OCI Bastion sessions. Not an instance ingress rule."

  validation {
    condition     = can(cidrnetmask(var.operator_cidr)) && var.operator_cidr != "0.0.0.0/0" && var.operator_cidr != "::/0"
    error_message = "operator_cidr must be a specific CIDR, never 0.0.0.0/0 or ::/0."
  }
}

variable "shape" {
  type        = string
  default     = "VM.Standard.A1.Flex"
  description = "Exact Always Free ARM shape. Paid shapes are rejected."

  validation {
    condition     = var.shape == "VM.Standard.A1.Flex"
    error_message = "shape must be VM.Standard.A1.Flex."
  }
}

variable "ocpus" {
  type        = number
  default     = 2
  description = "Exact OCPU count. This consumes the entire Always Free Ampere quota."

  validation {
    condition     = var.ocpus == 2
    error_message = "ocpus must be exactly 2, the full Always Free Ampere quota."
  }
}

variable "memory_in_gbs" {
  type        = number
  default     = 12
  description = "Exact memory. This consumes the entire Always Free Ampere memory quota."

  validation {
    condition     = var.memory_in_gbs == 12
    error_message = "memory_in_gbs must be exactly 12, the full Always Free Ampere memory quota."
  }
}

variable "boot_volume_gb" {
  type        = number
  default     = 50
  description = "Boot volume size. 50 GB is the default Always Free boot volume and counts against the 200 GB block cap."

  validation {
    condition     = var.boot_volume_gb == 50
    error_message = "boot_volume_gb must be exactly 50."
  }
}

variable "data_volume_gb" {
  type        = number
  default     = 50
  description = "Data volume for Postgres, Redis, and the Docker data root. Boot plus data is 100 GB of the 200 GB cap."

  validation {
    condition     = var.data_volume_gb == 50
    error_message = "data_volume_gb must be exactly 50."
  }
}

variable "vcn_cidr" {
  type        = string
  default     = "10.8.0.0/16"
  description = "Private address plan for the single dev VCN."

  validation {
    condition     = var.vcn_cidr == "10.8.0.0/16"
    error_message = "vcn_cidr is fixed at 10.8.0.0/16 for this candidate."
  }
}

variable "subnet_cidr" {
  type        = string
  default     = "10.8.1.0/24"
  description = "Subnet for the single dev instance."

  validation {
    condition     = var.subnet_cidr == "10.8.1.0/24"
    error_message = "subnet_cidr is fixed at 10.8.1.0/24 for this candidate."
  }
}
