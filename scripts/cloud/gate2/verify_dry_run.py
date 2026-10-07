#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic Gate 2 checks. No Cloudflare, DNS, R2, Hetzner, or GCP calls."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = Path(__file__).resolve().parent / "edge-contract.json"
STAGING_MAIN = ROOT / "infra" / "terraform" / "environments" / "staging" / "main.tf"


def fail(message: str) -> None:
    print(f"GATE2_DRY_RUN=FAIL {message}")
    raise SystemExit(1)


def main() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    if data.get("status") != "dry-run-only":
        fail("contract is not marked dry-run-only")
    mutations = data.get("mutations") or {}
    for name in ("cloudflare", "dns", "r2", "hetzner", "gcp"):
        if mutations.get(name) is not False:
            fail(f"mutation flag {name} is not false")
    edge = data["edge"]
    if edge.get("tls_mode") != "full_strict":
        fail("tls mode")
    if edge["record"].get("proxied") is not True:
        fail("dns record must be proxied")
    if (
        edge["authenticated_origin_pull"].get("origin_verifies_cloudflare_client_certificate")
        is not True
    ):
        fail("authenticated origin pull")
    stages = edge["hsts"]["stages"]
    ages = [stage["max_age"] for stage in stages]
    if ages != sorted(ages) or ages[0] != 0:
        fail("hsts must start at max-age 0 and increase")
    if any(stage.get("preload") for stage in stages):
        fail("preload is not part of the staged rollout")
    if edge["hsts"].get("preload_requires_owner") is not True:
        fail("preload owner gate")
    if "cloudflare_managed" not in edge["waf_baseline"]:
        fail("waf baseline")
    limit = edge["rate_limit_baseline"]
    if limit["path"] != "/api/" or limit["requests"] <= 0 or limit["action"] != "block":
        fail("rate limit baseline")
    lockdown = data["origin_lockdown"]
    if lockdown.get("saas_public_ipv4") is not False:
        fail("saas must stay private")
    if lockdown.get("after") != "lb_443_from_cloudflare_ranges_only":
        fail("origin lockdown target")
    staging = STAGING_MAIN.read_text(encoding="utf-8")
    if (
        "saas_public_ipv4" not in staging
        or "false" not in staging.split("saas_public_ipv4", 1)[1][:40]
    ):
        fail("staging terraform does not keep SaaS private")
    backup = data["backup"]
    if backup.get("object_must_be_encrypted_before_upload") is not True:
        fail("backup encryption")
    if backup.get("r2_credentials_are_not_the_backup_key") is not True:
        fail("key separation")
    if int(backup["retention_days_staging"]) < 7:
        fail("retention")
    print("GATE2_DRY_RUN=PASS")
    print("CLOUDFLARE_MUTATION=NO")
    print("DNS_MUTATION=NO")
    print("R2_MUTATION=NO")


if __name__ == "__main__":
    sys.exit(main())
