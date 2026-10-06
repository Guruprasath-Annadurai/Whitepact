#!/usr/bin/env bash
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
# Parse terraform plan JSON and verify Gate-1 constraints (no secrets).
set -euo pipefail
PLAN_JSON="${1:?plan.json path required}"

python3 - "$PLAN_JSON" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1]))
resources = plan.get("resource_changes") or []
creates = [r for r in resources if "create" in r.get("change", {}).get("actions", [])]
types = sorted({r["type"] for r in creates})
print("CREATE resource types:", ", ".join(types))
print("CREATE count:", len(creates))

def public_net(after):
    pub = (after or {}).get("public_net") or {}
    if isinstance(pub, list):
        pub = pub[0] if pub else {}
    return pub if isinstance(pub, dict) else {}

servers = [r for r in creates if r["type"] == "hcloud_server"]
for s in servers:
    name = s["change"]["after"].get("name", "?")
    ipv4 = public_net(s["change"]["after"]).get("ipv4_enabled")
    print(f"  server {name}: public ipv4_enabled={ipv4}")

def planned_servers(changes):
    found = []
    for r in changes:
        if r.get("type") != "hcloud_server":
            continue
        actions = r.get("change", {}).get("actions") or []
        if actions == ["delete"]:
            continue
        found.append(r)
    return found

def ssh_keys_attached(change):
    after = change.get("after") or {}
    keys = after.get("ssh_keys")
    unknown = change.get("after_unknown") or {}
    if unknown is True or (isinstance(unknown, dict) and unknown.get("ssh_keys") is True):
        return False
    if isinstance(unknown, dict) and isinstance(unknown.get("ssh_keys"), list):
        if any(flag is True for flag in unknown["ssh_keys"]):
            return False
    return isinstance(keys, list) and len(keys) > 0 and all(isinstance(k, str) and k.strip() for k in keys)

attached = planned_servers(resources)
if not attached:
    print("SSH_KEY_ATTACHMENT=FAIL")
    raise SystemExit("FAIL: no planned hcloud_server resources to check")
missing = []
for s in attached:
    if not ssh_keys_attached(s.get("change") or {}):
        missing.append(s.get("address", "?"))
if missing:
    print("SSH_KEY_ATTACHMENT=FAIL")
    raise SystemExit("FAIL: planned hcloud_server missing non-empty ssh_keys: " + ", ".join(missing))
print("SSH_KEY_ATTACHMENT=PASS")

nat = [r for r in creates if r["type"] == "hcloud_server" and "nat" in r["change"]["after"].get("name", "")]
public_servers = [r for r in servers if public_net(r["change"]["after"]).get("ipv4_enabled")]
if len(public_servers) != 1:
    raise SystemExit(f"FAIL: expected exactly 1 server with public IPv4, got {len(public_servers)}")
if not nat:
    raise SystemExit("FAIL: expected nat gateway server in plan")
fw = [r for r in creates if r["type"] == "hcloud_firewall"]
if len(fw) != 1:
    raise SystemExit(f"FAIL: expected 1 hcloud_firewall (NAT only), got {len(fw)}")
print("Gate-1 static checks: OK")
print("PLAN_VERIFIER=PASS")
PY
