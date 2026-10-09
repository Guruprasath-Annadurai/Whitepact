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
  estimated_monthly_cents = (
    local.price_book_complete
    ? (local.saas_unit_cents * local.saas_count)
    + local.authority_unit_cents
    + (local.execution_unit_cents * local.execution_count)
    + (local.nat_unit_cents * local.nat_count)
    + (local.ipv4_unit_cents * local.public_ipv4_count)
    + local.lb_unit_cents
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
      error_message = "Refusing to plan: the Hetzner shape is missing from the FSN1 price book or its estimate exceeds monthly_cost_ceiling_cents. Do not apply a larger SKU, backup, or volume without a new owner ceiling."
    }
  }
}
