# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Gate 2 Cloudflare resources. Plan-specific features stay off unless both
# the feature flag and the plan flag are true. Terraform validate does not apply.

variable "enable_zone_tls_settings" {
  description = "Set Full (strict) TLS on the zone. This does not emit HSTS; the application is the only HSTS authority."
  type        = bool
  default     = true
}

variable "enable_authenticated_origin_pulls" {
  description = "Turn on Cloudflare authenticated origin pulls. Origin nginx/Caddy still has to require the client certificate."
  type        = bool
  default     = false
}

variable "plan_allows_authenticated_origin_pulls" {
  type    = bool
  default = false
}

variable "enable_waf_managed_rules" {
  description = "Create the Cloudflare managed WAF ruleset. Not production-tuned evidence."
  type        = bool
  default     = false
}

variable "plan_allows_waf_managed_rules" {
  type    = bool
  default = false
}

variable "enable_rate_limit_rules" {
  description = "Create route-aware rate-limit rules. Defaults are a baseline, not production tuning."
  type        = bool
  default     = false
}

variable "plan_allows_rate_limit_rules" {
  type    = bool
  default = false
}

variable "enable_staging_noindex_transform" {
  description = "Add X-Robots-Tag noindex at the edge. The application also sets this header when the environment is staging."
  type        = bool
  default     = false
}

variable "plan_allows_response_header_transform" {
  type    = bool
  default = false
}

variable "waf_managed_ruleset_id" {
  description = "Cloudflare Managed Ruleset id. Override if Cloudflare publishes a different id for the account."
  type        = string
  default     = "efb7b8c949ac4650a09736fc376e9aee"
}

variable "owasp_core_ruleset_id" {
  description = "Cloudflare OWASP Core Ruleset id."
  type        = string
  default     = "4814384a9e5d4991b9815dcfc25d2f1f"
}

resource "terraform_data" "gate2_feature_guards" {
  lifecycle {
    precondition {
      condition     = !(var.enable_waf_managed_rules && !var.plan_allows_waf_managed_rules)
      error_message = "WAF managed rules were requested but plan_allows_waf_managed_rules is false. This module will not claim they are active."
    }
    precondition {
      condition     = !(var.enable_rate_limit_rules && !var.plan_allows_rate_limit_rules)
      error_message = "Rate-limit rules were requested but plan_allows_rate_limit_rules is false. This module will not claim they are active."
    }
    precondition {
      condition     = !(var.enable_authenticated_origin_pulls && !var.plan_allows_authenticated_origin_pulls)
      error_message = "Authenticated origin pull was requested but plan_allows_authenticated_origin_pulls is false."
    }
    precondition {
      condition     = !(var.enable_staging_noindex_transform && !var.plan_allows_response_header_transform)
      error_message = "Staging noindex transform was requested but plan_allows_response_header_transform is false."
    }
    precondition {
      condition     = var.admin_hostname == "" || (var.tunnel_secret_placeholder != "REPLACE_BEFORE_APPLY" && length(var.tunnel_secret_placeholder) >= 32)
      error_message = "Refusing to plan an admin Cloudflare tunnel with the placeholder secret."
    }
  }
}

resource "cloudflare_zone_settings_override" "tls" {
  count   = var.enable_zone_tls_settings ? 1 : 0
  zone_id = var.zone_id

  settings {
    ssl              = "strict"
    always_use_https = "on"
    min_tls_version  = "1.2"
    tls_1_3          = "on"
  }
}

resource "cloudflare_authenticated_origin_pulls" "zone" {
  count   = var.enable_authenticated_origin_pulls && var.plan_allows_authenticated_origin_pulls ? 1 : 0
  zone_id = var.zone_id
  enabled = true
}

resource "cloudflare_ruleset" "waf_managed" {
  count       = var.enable_waf_managed_rules && var.plan_allows_waf_managed_rules ? 1 : 0
  zone_id     = var.zone_id
  name        = "whitepact-waf-baseline"
  description = "Managed and OWASP rulesets. Not evidence of production tuning."
  kind        = "zone"
  phase       = "http_request_firewall_managed"

  rules {
    action      = "execute"
    expression  = "true"
    description = "Cloudflare managed ruleset"
    enabled     = true
    action_parameters {
      id = var.waf_managed_ruleset_id
    }
  }

  rules {
    action      = "execute"
    expression  = "true"
    description = "OWASP core ruleset"
    enabled     = true
    action_parameters {
      id = var.owasp_core_ruleset_id
    }
  }
}

resource "cloudflare_ruleset" "rate_limits" {
  count       = var.enable_rate_limit_rules && var.plan_allows_rate_limit_rules ? 1 : 0
  zone_id     = var.zone_id
  name        = "whitepact-route-rate-limits"
  description = "Route baseline. Not production tuning."
  kind        = "zone"
  phase       = "http_ratelimit"

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/(auth|login)\")"
    description = "login and auth"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 20
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/(signup|register)\")"
    description = "signup"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 10
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/\" and not http.request.uri.path matches \"^/api/(auth|login|signup|register|webhooks|exports|health)\")"
    description = "general API"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 300
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/(mcp|sse)\")"
    description = "MCP"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 120
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/webhooks/\")"
    description = "webhooks"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 60
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "block"
    expression  = "(http.request.uri.path matches \"^/api/exports/\")"
    description = "exports"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 10
      mitigation_timeout  = 60
    }
  }

  rules {
    action      = "log"
    expression  = "(http.request.uri.path matches \"^/(api/health|livez|readyz)\")"
    description = "health endpoints are counted, not blocked, by this baseline"
    enabled     = true
    ratelimit {
      characteristics     = ["ip.src", "cf.colo.id"]
      period              = 60
      requests_per_period = 600
      mitigation_timeout  = 0
    }
  }
}

# R2 object lifecycle is intentionally absent. Age-based Cloudflare lifecycle
# can delete the newest remaining backup. Retention is scripts/cloud/gate2/enforce_r2_retention.sh,
# which refuses to delete the newest viable recovery points and defaults to dry-run.

resource "cloudflare_ruleset" "staging_noindex" {
  count       = var.enable_staging_noindex_transform && var.plan_allows_response_header_transform ? 1 : 0
  zone_id     = var.zone_id
  name        = "whitepact-staging-noindex"
  description = "Staging X-Robots-Tag. Production stays separately configurable."
  kind        = "zone"
  phase       = "http_response_headers_transform"

  rules {
    action      = "rewrite"
    expression  = "true"
    description = "noindex staging"
    enabled     = true
    action_parameters {
      headers {
        name      = "X-Robots-Tag"
        operation = "set"
        value     = "noindex, nofollow"
      }
    }
  }
}

output "waf_managed_rules_configured" {
  value = var.enable_waf_managed_rules && var.plan_allows_waf_managed_rules
}

output "rate_limit_rules_configured" {
  value = var.enable_rate_limit_rules && var.plan_allows_rate_limit_rules
}

output "authenticated_origin_pulls_configured" {
  value = var.enable_authenticated_origin_pulls && var.plan_allows_authenticated_origin_pulls
}

output "staging_noindex_transform_configured" {
  value = var.enable_staging_noindex_transform && var.plan_allows_response_header_transform
}
