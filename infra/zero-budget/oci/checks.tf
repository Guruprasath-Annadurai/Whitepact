resource "terraform_data" "authorization_gate" {
  input = var.authorization_gate

  lifecycle {
    precondition {
      condition     = var.authorization_gate == "AUTHORIZED_BY_OWNER"
      error_message = "Deployment authorization gate is closed (HOLD). This module refuses to plan or apply. apply.sh also refuses mutation. Opening this string is not owner approval."
    }
  }
}

check "always_free_exact_allocation" {
  assert {
    condition = (
      var.shape == "VM.Standard.A1.Flex" &&
      var.ocpus == 2 &&
      var.memory_in_gbs == 12 &&
      var.boot_volume_gb == 50 &&
      var.data_volume_gb == 50 &&
      var.vcn_cidr == "10.8.0.0/16" &&
      var.subnet_cidr == "10.8.1.0/24" &&
      var.operator_cidr != "0.0.0.0/0"
    )
    error_message = "Allocation drifted from the documented Always Free candidate (2 OCPU, 12 GB, 50 GB boot, 50 GB data)."
  }
}
