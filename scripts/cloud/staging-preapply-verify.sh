#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Parse terraform plan JSON and verify Gate-1 constraints (no secrets).
set -euo pipefail
PLAN_JSON="${1:?plan.json path required}"

python3 <<'PY' "$PLAN_JSON"
import json, sys
plan = json.load(open(sys.argv[1]))
resources = plan.get("resource_changes") or []
creates = [r for r in resources if "create" in r.get("change", {}).get("actions", [])]
types = sorted({r["type"] for r in creates})
print("CREATE resource types:", ", ".join(types))
print("CREATE count:", len(creates))

servers = [r for r in creates if r["type"] == "hcloud_server"]
for s in servers:
    name = s["change"]["after"].get("name", "?")
    pub = s["change"]["after"].get("public_net", {})
    ipv4 = pub.get("ipv4_enabled") if isinstance(pub, dict) else None
    print(f"  server {name}: public ipv4_enabled={ipv4}")

nat = [r for r in creates if r["type"] == "hcloud_server" and "nat" in r["change"]["after"].get("name", "")]
public_servers = [r for r in servers if r["change"]["after"].get("public_net", {}).get("ipv4_enabled")]
if len(public_servers) != 1:
    raise SystemExit(f"FAIL: expected exactly 1 server with public IPv4, got {len(public_servers)}")
if not nat:
    raise SystemExit("FAIL: expected nat gateway server in plan")
fw = [r for r in creates if r["type"] == "hcloud_firewall"]
if len(fw) != 1:
    raise SystemExit(f"FAIL: expected 1 hcloud_firewall (NAT only), got {len(fw)}")
print("Gate-1 static checks: OK")
PY
