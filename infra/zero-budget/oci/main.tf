resource "oci_limits_quota" "always_free_a1" {
  compartment_id = var.tenancy_ocid
  name           = "whitepact-zero-budget-a1"
  description    = "Cap Ampere A1 at the Always Free total so a second instance cannot be billed as overage."
  statements = [
    "set compute-core quota standard-a1-core-count to ${var.ocpus} in compartment ${var.compartment_quota_name}",
    "set compute-memory quota standard-a1-memory-count to ${var.memory_in_gbs} in compartment ${var.compartment_quota_name}",
  ]

  depends_on = [terraform_data.authorization_gate]
}

resource "oci_core_vcn" "dev" {
  compartment_id = var.compartment_ocid
  display_name   = "whitepact-dev"
  cidr_blocks    = [var.vcn_cidr]
  dns_label      = "wpdev"
  is_ipv6enabled = false
  freeform_tags = {
    project     = "whitepact"
    cost-class  = "always-free"
    environment = "dev-candidate"
  }

  depends_on = [terraform_data.authorization_gate]
}

resource "oci_core_internet_gateway" "dev" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dev.id
  display_name   = "whitepact-dev"
  enabled        = true
  freeform_tags  = oci_core_vcn.dev.freeform_tags
}

resource "oci_core_route_table" "dev" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dev.id
  display_name   = "whitepact-dev"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.dev.id
    description       = "Outbound internet for package and image pulls. No NAT gateway."
  }
}

resource "oci_core_security_list" "dev" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dev.id
  display_name   = "whitepact-dev"

  ingress_security_rules {
    protocol    = "6"
    source      = var.vcn_cidr
    source_type = "CIDR_BLOCK"
    stateless   = false
    description = "SSH from inside the VCN only, for OCI Bastion. No internet ingress."

    tcp_options {
      min = 22
      max = 22
    }
  }

  egress_security_rules {
    protocol         = "6"
    destination      = "0.0.0.0/0"
    destination_type = "CIDR_BLOCK"
    stateless        = false
    description      = "HTTPS for Ubuntu packages, container images, and git. Application egress stays in SafeNetworkBackend."

    tcp_options {
      min = 443
      max = 443
    }
  }

  egress_security_rules {
    protocol         = "17"
    destination      = "169.254.169.254/32"
    destination_type = "CIDR_BLOCK"
    stateless        = false
    description      = "DNS to the OCI resolver. This is not permission for metadata HTTP."

    udp_options {
      min = 53
      max = 53
    }
  }

  egress_security_rules {
    protocol         = "6"
    destination      = "169.254.169.254/32"
    destination_type = "CIDR_BLOCK"
    stateless        = false
    description      = "DNS over TCP to the OCI resolver."

    tcp_options {
      min = 53
      max = 53
    }
  }
}

resource "oci_core_subnet" "dev" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.dev.id
  display_name   = "whitepact-dev"
  cidr_block     = var.subnet_cidr
  dns_label      = "dev"
  # Public subnet so outbound package pulls can use the free internet
  # gateway. A private subnet would need a paid NAT gateway. Unsolicited
  # internet ingress stays closed in the security list.
  prohibit_public_ip_on_vnic = false
  route_table_id             = oci_core_route_table.dev.id
  security_list_ids          = [oci_core_security_list.dev.id]
  freeform_tags              = oci_core_vcn.dev.freeform_tags
}

resource "oci_core_instance" "dev" {
  compartment_id      = var.compartment_ocid
  availability_domain = var.availability_domain
  display_name        = "whitepact-dev-a1"
  shape               = var.shape

  shape_config {
    ocpus         = var.ocpus
    memory_in_gbs = var.memory_in_gbs
  }

  source_details {
    source_type             = "image"
    source_id               = var.image_ocid
    boot_volume_size_in_gbs = var.boot_volume_gb
  }

  preserve_boot_volume = false

  create_vnic_details {
    subnet_id                 = oci_core_subnet.dev.id
    display_name              = "whitepact-dev"
    assign_public_ip          = true
    assign_private_dns_record = true
    hostname_label            = "wpdev"
    nsg_ids                   = []
  }

  metadata = {
    ssh_authorized_keys = var.ssh_public_key
    user_data           = base64encode(file("${path.module}/cloud-init.yaml"))
  }

  agent_config {
    is_management_disabled = true
    is_monitoring_disabled = false

    plugins_config {
      name          = "Bastion"
      desired_state = "ENABLED"
    }
  }

  freeform_tags = oci_core_vcn.dev.freeform_tags

  depends_on = [
    terraform_data.authorization_gate,
    oci_limits_quota.always_free_a1,
  ]
}

resource "oci_core_volume" "data" {
  compartment_id      = var.compartment_ocid
  availability_domain = var.availability_domain
  display_name        = "whitepact-dev-data"
  size_in_gbs         = var.data_volume_gb
  freeform_tags       = oci_core_vcn.dev.freeform_tags

  depends_on = [terraform_data.authorization_gate]
}

resource "oci_core_volume_attachment" "data" {
  attachment_type                     = "paravirtualized"
  instance_id                         = oci_core_instance.dev.id
  volume_id                           = oci_core_volume.data.id
  display_name                        = "whitepact-dev-data"
  is_pv_encryption_in_transit_enabled = true
  is_read_only                        = false
}

resource "oci_bastion_bastion" "operator" {
  compartment_id               = var.compartment_ocid
  target_subnet_id             = oci_core_subnet.dev.id
  bastion_type                 = "STANDARD"
  client_cidr_block_allow_list = [var.operator_cidr]
  name                         = "wpdevbastion"
  max_session_ttl_in_seconds   = 10800
  freeform_tags                = oci_core_vcn.dev.freeform_tags

  depends_on = [terraform_data.authorization_gate]
}
