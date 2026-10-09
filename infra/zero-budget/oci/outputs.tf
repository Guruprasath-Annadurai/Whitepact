output "authorization_gate" {
  description = "HOLD means this candidate has not been authorized for provisioning."
  value       = var.authorization_gate
}

output "exact_allocation" {
  description = "Always Free candidate this module is willing to represent."
  value = {
    shape          = var.shape
    ocpus          = var.ocpus
    memory_in_gbs  = var.memory_in_gbs
    boot_volume_gb = var.boot_volume_gb
    data_volume_gb = var.data_volume_gb
    public_ingress = "none; SSH only from the VCN via OCI Bastion"
    nat_gateway    = false
    load_balancer  = false
  }
}

output "instance_id" {
  description = "Populated only after a future authorized apply. Empty while the gate is closed."
  value       = try(oci_core_instance.dev.id, null)
}

output "private_ip" {
  description = "Instance private address for Bastion sessions."
  value       = try(oci_core_instance.dev.private_ip, null)
}
