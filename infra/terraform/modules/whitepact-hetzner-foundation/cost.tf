# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Euro cents so the ceiling comparison does not depend on binary floats.
# Approved staging shape: 849+849+549+549+50+749 = 3595.

locals {
  price_book           = jsondecode(file("${path.module}/pricing/hetzner-fsn1.json"))
  saas_count           = var.environment == "production" ? 2 : 1
  execution_count      = var.environment == "production" ? 2 : 1
  nat_count            = var.enable_nat_gateway ? 1 : 0
  public_ipv4_count    = local.nat_count + (var.saas_public_ipv4 ? local.saas_count : 0)
  server_prices        = local.price_book.server_monthly_cents
  saas_unit_cents      = lookup(local.server_prices, var.saas_server_type, null)
  authority_unit_cents = lookup(local.server_prices, var.authority_server_type, null)
  execution_unit_cents = lookup(local.server_prices, var.execution_server_type, null)
  nat_unit_cents = (
    local.nat_count == 0 ? 0 : lookup(local.server_prices, var.nat_gateway_server_type, null)
  )
  lb_unit_cents   = lookup(local.price_book.load_balancer_monthly_cents, "lb11", null)
  ipv4_unit_cents = local.price_book.primary_ipv4_monthly_cents
  price_book_complete = (
    local.saas_unit_cents != null
    && local.authority_unit_cents != null
    && local.execution_unit_cents != null
    && local.nat_unit_cents != null
    && local.lb_unit_cents != null
  )
  server_shape_cents = (
    local.price_book_complete
    ? (local.saas_unit_cents * local.saas_count)
    + local.authority_unit_cents
    + (local.execution_unit_cents * local.execution_count)
    + (local.nat_unit_cents * local.nat_count)
    : -1
  )
  # 20 percent of server SKUs only, rounded up to the next euro cent.
  # VAT is not added. A Hetzner console spending alert is not created.
  backup_monthly_cents = (
    var.enable_server_backups && local.server_shape_cents >= 0
    ? ((local.server_shape_cents * 20) + 99) / 100
    : 0
  )
  estimated_monthly_cents = (
    local.price_book_complete
    ? local.server_shape_cents
    + (local.ipv4_unit_cents * local.public_ipv4_count)
    + local.lb_unit_cents
    + local.backup_monthly_cents
    : -1
  )
}

resource "terraform_data" "monthly_cost_ceiling" {
  input = {
    estimated_monthly_cents = local.estimated_monthly_cents
    ceiling_cents           = var.monthly_cost_ceiling_cents
  }

  lifecycle {
    precondition {
      condition = (
        var.monthly_cost_ceiling_cents == 0
        || (
          local.price_book_complete
          && local.estimated_monthly_cents <= var.monthly_cost_ceiling_cents
        )
      )
      error_message = "Refusing to plan: the Terraform price-book estimate is missing a SKU or exceeds monthly_cost_ceiling_cents. This check is not a Hetzner billing alert. It excludes VAT. Server backups are added only when enable_server_backups is true, and that larger estimate still has to fit under an owner ceiling."
    }
  }
}
