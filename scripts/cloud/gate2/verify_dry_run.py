#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic Gate 2 checks. No Cloudflare, DNS, R2, Hetzner, or GCP calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, NoReturn, cast

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = Path(__file__).resolve().parent / "edge-contract.json"
STAGING_MAIN = ROOT / "infra" / "terraform" / "environments" / "staging" / "main.tf"

_RATE_CLASSES = (
    "login_auth",
    "signup",
    "general_api",
    "mcp",
    "webhooks",
    "exports",
    "health",
)
_SIGNALS = (
    "backup_age",
    "backup_failure",
    "restore_drill_failure",
    "origin_tls_failure",
    "disk_threshold",
    "db_connectivity",
    "application_health",
    "execution_service_health",
)


def fail(message: str) -> NoReturn:
    print(f"GATE2_DRY_RUN=FAIL {message}")
    raise SystemExit(1)


def _obj(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        fail(f"{label} must be an object")
    return cast(dict[str, Any], value)


def main() -> int:
    data = _obj(json.loads(CONTRACT.read_text(encoding="utf-8")), "contract")
    if data.get("status") != "dry-run-only":
        fail("contract is not marked dry-run-only")
    mutations = _obj(data.get("mutations"), "mutations")
    for name in ("cloudflare", "dns", "r2", "hetzner", "gcp"):
        if mutations.get(name) is not False:
            fail(f"mutation flag {name} is not false")
    edge = _obj(data.get("edge"), "edge")
    if edge.get("tls_mode") != "full_strict":
        fail("tls mode")
    if edge.get("hsts_authority") != "application_middleware":
        fail("hsts authority")
    record = _obj(edge.get("record"), "record")
    if record.get("proxied") is not True:
        fail("dns record must be proxied")
    aop = _obj(edge.get("authenticated_origin_pull"), "authenticated origin pull")
    if aop.get("origin_verifies_cloudflare_client_certificate") is not True:
        fail("authenticated origin pull")
    if aop.get("enforced_at") != "origin_reverse_proxy":
        fail("origin pull must be enforced at the origin proxy")
    hsts = _obj(edge.get("hsts"), "hsts")
    stages = hsts.get("stages")
    if not isinstance(stages, list) or not stages:
        fail("hsts stages")
    ages: list[int] = []
    for stage in stages:
        item = _obj(stage, "hsts stage")
        age = item.get("max_age")
        if not isinstance(age, int):
            fail("hsts max_age")
        ages.append(age)
        if item.get("preload") is not False:
            fail("preload is not part of the staged rollout")
    if ages != sorted(ages) or ages[0] != 0:
        fail("hsts must start at max-age 0 and increase")
    if hsts.get("preload_requires_owner") is not True:
        fail("preload owner gate")
    if hsts.get("production_default_stage") != "stage1":
        fail("production hsts default")
    waf = edge.get("waf_baseline")
    if not isinstance(waf, list) or "cloudflare_managed" not in waf:
        fail("waf baseline")
    if edge.get("waf_status") != "parameterized_not_production_tuned":
        fail("waf must not be claimed as production tuned")
    limits = _obj(edge.get("rate_limits"), "rate limits")
    if limits.get("tuned") is not False:
        fail("rate limits must not be claimed as production tuned")
    classes = _obj(limits.get("classes"), "rate limit classes")
    for name in _RATE_CLASSES:
        item = _obj(classes.get(name), name)
        requests = item.get("requests")
        if not isinstance(requests, int) or requests <= 0:
            fail(f"{name} requests")
        if not isinstance(item.get("rationale"), str) or not item["rationale"]:
            fail(f"{name} rationale")
    login = _obj(classes["login_auth"], "login")
    general = _obj(classes["general_api"], "general api")
    if login["requests"] >= general["requests"]:
        fail("login limit must be tighter than the general API")
    if general["requests"] == 600 and len(classes) == 1:
        fail("a single 600/min rule is not the policy")
    lockdown = _obj(data.get("origin_lockdown"), "origin lockdown")
    if lockdown.get("saas_public_ipv4") is not False:
        fail("saas must stay private")
    if lockdown.get("lb_source_cidr_filter") is not False:
        fail("do not claim an unsupported load balancer CIDR filter")
    if lockdown.get("lb_source_cidr_filter_supported") is not False:
        fail("load balancer CIDR filter is not supported")
    after = lockdown.get("after")
    if after == "lb_443_from_cloudflare_ranges_only":
        fail("false origin lockdown contract")
    if after != "public_hetzner_lb_tcp_passthrough_origin_aop":
        fail("origin lockdown target")
    staging = STAGING_MAIN.read_text(encoding="utf-8")
    if (
        "saas_public_ipv4" not in staging
        or "false" not in staging.split("saas_public_ipv4", 1)[1][:40]
    ):
        fail("staging terraform does not keep SaaS private")
    if "lb_service_protocol" not in staging or "tcp" not in staging:
        fail("staging load balancer must stay TCP passthrough")
    backup = _obj(data.get("backup"), "backup")
    if backup.get("object_must_be_encrypted_before_upload") is not True:
        fail("backup encryption")
    if backup.get("authenticated") is not True:
        fail("backup cipher must be authenticated")
    if backup.get("cipher") in {"aes-256-cbc-pbkdf2", "plaintext"}:
        fail("unauthenticated backup cipher")
    if backup.get("plaintext_upload") is not False:
        fail("plaintext upload")
    if backup.get("restore_drops_active_database_first") is not False:
        fail("restore must not drop the active database first")
    if backup.get("key_must_not_be_stored_beside_object") is not True:
        fail("backup key must not sit beside the object")
    if backup.get("r2_credentials_are_not_the_backup_key") is not True:
        fail("key separation")
    retention = backup.get("retention_days_staging")
    if not isinstance(retention, int) or retention < 7:
        fail("retention")
    robots = _obj(data.get("staging_robots"), "staging robots")
    if robots.get("header") != "X-Robots-Tag: noindex, nofollow":
        fail("staging noindex")
    if robots.get("production_separately_configurable") is not True:
        fail("production robots policy")
    observe = _obj(data.get("observability"), "observability")
    signals = observe.get("signals")
    if not isinstance(signals, list) or tuple(signals) != _SIGNALS:
        fail("observability signals")
    if observe.get("alerts_claimed_active") is not False:
        fail("do not claim alerts are active")
    print("GATE2_DRY_RUN=PASS")
    print("CLOUDFLARE_MUTATION=NO")
    print("DNS_MUTATION=NO")
    print("R2_MUTATION=NO")
    return 0


if __name__ == "__main__":
    sys.exit(main())
