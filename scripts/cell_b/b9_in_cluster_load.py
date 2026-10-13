#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""B9 in-cluster distributed load — per-replica attribution + optional tenant auth mix."""

from __future__ import annotations

import argparse
import json
import os
import threading
import time
from collections import Counter
from pathlib import Path

import httpx


def _worker(
    base: str,
    deadline: float,
    lat: list[float],
    errors: Counter,
    replicas: Counter,
    outcomes: Counter,
    auth_headers: dict[str, str] | None,
    org_id: str | None,
    peer_org_id: str | None,
) -> None:
    client = httpx.Client(timeout=10.0, headers=auth_headers or {})
    i = 0
    while time.monotonic() < deadline:
        t0 = time.perf_counter()
        try:
            if auth_headers and org_id and i % 3 == 0:
                endpoint = f"/api/orgs/{org_id}/keys"
                r = client.get(f"{base}{endpoint}")
                outcomes[f"tenant_list_keys_{r.status_code}"] += 1
            elif auth_headers and peer_org_id and i % 5 == 0:
                endpoint = f"/api/orgs/{peer_org_id}/keys"
                r = client.get(f"{base}{endpoint}")
                outcomes[f"cross_tenant_probe_{r.status_code}"] += 1
            else:
                endpoint = ("/api/health", "/livez", "/readyz")[i % 3]
                r = client.get(f"{base}{endpoint}")
            lat.append((time.perf_counter() - t0) * 1000)
            if r.status_code >= 500:
                errors["http_5xx"] += 1
            elif endpoint == "/api/health" and r.status_code == 200:
                body = r.json()
                inst = body.get("instance_id") or body.get("checks", {}).get("instance_id")
                if inst:
                    replicas[str(inst)] += 1
                else:
                    errors["missing_instance_id"] += 1
            elif r.status_code >= 400 and not str(endpoint).startswith("/api/orgs"):
                errors[f"http_{r.status_code}"] += 1
        except httpx.HTTPError:
            errors["transport"] += 1
        i += 1
    client.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--duration", type=int, default=120)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("/tmp/b9-load.json"))
    args = parser.parse_args()

    api_key = os.environ.get("CELL_B_B9_API_KEY")
    org_id = os.environ.get("CELL_B_B9_ORG_ID")
    peer_org = os.environ.get("CELL_B_B9_PEER_ORG_ID")
    auth_headers = {"Authorization": f"Bearer {api_key}"} if api_key else None

    deadline = time.monotonic() + args.duration
    lat: list[float] = []
    errors: Counter = Counter()
    replicas: Counter = Counter()
    outcomes: Counter = Counter()
    threads = [
        threading.Thread(
            target=_worker,
            args=(
                args.base_url.rstrip("/"),
                deadline,
                lat,
                errors,
                replicas,
                outcomes,
                auth_headers,
                org_id,
                peer_org,
            ),
        )
        for _ in range(args.workers)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    lat.sort()
    n = len(lat)
    data = {
        "phase": "B9",
        "method": "in_cluster_service_load",
        "base_url": args.base_url,
        "soak_seconds": args.duration,
        "workers": args.workers,
        "authenticated_tenant_mix": bool(api_key and org_id),
        "requests": n,
        "errors": dict(errors),
        "functional_outcomes": dict(outcomes),
        "measured_rps": round(n / max(args.duration, 1), 2),
        "measured_p50_ms": round(lat[int(n * 0.5)], 3) if n else 0,
        "measured_p95_ms": round(lat[int(n * 0.95) - 1], 3) if n > 1 else 0,
        "per_replica_health_hits": dict(replicas),
        "distinct_replicas_observed": len(replicas),
        "limitations": (
            "Engineering soak on disposable kind; not Antigravity 4h/500 RPS gate. "
            "Set CELL_B_B9_API_KEY + CELL_B_B9_ORG_ID for tenant-scoped traffic. "
            "Replica attribution uses WHITEPACT_INSTANCE_ID on /api/health."
        ),
    }
    args.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data, indent=2))
    ok = n > 0 and errors.get("http_5xx", 0) == 0
    if data["distinct_replicas_observed"] < 2:
        ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
