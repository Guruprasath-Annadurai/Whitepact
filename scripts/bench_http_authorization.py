#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated authorization latency over real HTTP against a real PostgreSQL.

What is measured: a separate uvicorn process (one worker) serving the dashboard application over a
loopback TCP socket, a disposable migrated PostgreSQL database, API-key authentication, tenant
resolution, policy evaluation and, per workload, a durable evidence write and an approval row. The
load generator is an asyncio httpx client in this process on the same machine, so client and server
compete for the same cores; that is stated in the report, not hidden.

What is NOT measured: TLS, a reverse proxy, more than one worker or replica, a database on another
host, governed execution in a container (no tool is executed: the DENY and REQUIRE_APPROVAL workloads
stop before execution by design), or the MCP transport.

Correctness is measured with latency: the effect counter must not move for any workload here, and the
number of approval rows must equal the number of REQUIRE_APPROVAL responses. A run with an
unauthorized effect is reported as FAIL regardless of speed. Saturation is reported, never hidden:
non-200 responses and timeouts are counted as errors and the run exits non-zero if any occur at a level
the report calls "within capacity".

    WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:55433/postgres \
        python scripts/bench_http_authorization.py --levels 1,10,100,1000 --out bench-http.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import socket
import statistics
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

PURPOSE = "http-benchmark"
TOOL = "test.counter.increment"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _pct(samples: list[float], pct: float) -> float:
    ordered = sorted(samples)
    return ordered[min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))]


async def _seed(url: str) -> tuple[str, str, str, str]:
    from responsibleai.db import PolicyRepository, create_engine
    from responsibleai.db.consent_proof_repository import ConsentProofRepository
    from responsibleai.db.delegation_repository import DelegationRepository
    from responsibleai.db.org_repository import OrgRepository
    from responsibleai.db.root_authority_repository import RootAuthorityRepository
    from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
    from responsibleai.governance.models import GovernanceDecision
    from responsibleai.governance.policy import PolicyRule
    from responsibleai.governance.root_authority import RootType, build_root_authority_record
    from responsibleai.rbac.models import Plan, Role

    engine = create_engine(url)
    await engine.init(auto_create_tables=False)
    try:
        org = await OrgRepository(engine).create_org(
            "Bench Co", f"bench-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE
        )
        key, raw = await OrgRepository(engine).create_key(
            org.id, "bench", role=Role.ADMIN, internal_unverified_fixture=True
        )
        # A separate key for the DENY workload: repeated violations quarantine the principal, which is
        # product behaviour worth measuring, but it must not poison the approval workload's key.
        _deny_key, deny_raw = await OrgRepository(engine).create_key(
            org.id, "bench-deny", role=Role.ADMIN, internal_unverified_fixture=True
        )
        owner = f"bench-owner:{org.id}"
        expires = datetime.now(UTC) + timedelta(hours=6)
        root = build_root_authority_record(
            owner,
            RootType.HUMAN,
            "bench",
            "explicit-bench-fixture",
            organization_id=org.id,
            evidence_refs=("bench-root",),
            expires_at=expires,
        )
        await RootAuthorityRepository(engine).create(root)
        consent = build_consent_proof(
            owner,
            root.root_id,
            key.id,
            "bench scope",
            PURPOSE,
            ConsentMethod.EXPLICIT_UI_ACTION,
            allowed_action_types=(TOOL,),
            allowed_targets=(TOOL,),
            evidence_refs=("bench-consent",),
            expires_at=expires,
        )
        await ConsentProofRepository(engine).create(consent, organization_id=org.id)
        await DelegationRepository(engine).grant(
            org.id,
            key.id,
            granted_action_types=frozenset((TOOL,)),
            constraints={"allowed_targets": [TOOL]},
            purpose=PURPOSE,
            granted_by=owner,
            expires_at=expires,
        )
        await PolicyRepository(engine).add_rule(
            org.id,
            PolicyRule(
                rule_id="bench-require-approval",
                reason_code="BENCH_REQUIRES_APPROVAL",
                effect=GovernanceDecision.REQUIRE_APPROVAL,
                action_types=frozenset({TOOL}),
            ),
        )
        return org.id, key.id, raw, deny_raw
    finally:
        await engine.close()


async def _scalar(url: str, sql: str, **params: object) -> int:
    from sqlalchemy import text

    from responsibleai.db import create_engine

    engine = create_engine(url)
    await engine.init(auto_create_tables=False)
    try:
        async with engine.raw.connect() as conn:
            return int((await conn.execute(text(sql), params)).scalar() or 0)
    finally:
        await engine.close()


async def _create_database(admin_url: str) -> tuple[str, str]:
    import asyncpg

    name = f"wp_bench_{uuid.uuid4().hex[:10]}"
    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(f'CREATE DATABASE "{name}"')
    finally:
        await conn.close()
    parsed = urlparse(admin_url)
    return name, urlunparse(parsed._replace(path=f"/{name}"))


async def _drop_database(admin_url: str, name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
    finally:
        await conn.close()


async def _migrate(url: str) -> None:
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic

    ini = _find_alembic_ini()
    assert ini is not None
    await _run_alembic(ini, _migration_env(url), "upgrade", "head")


_LAUNCHER = """
import sys
import uvicorn
import responsibleai.dashboard.app as app_module
if sys.argv[3] == "off":
    # The per-route slowapi limit ("30/minute" per organization on the governed tool call) caps one
    # tenant's whole fleet far below any capacity this script could measure. It is switched off for the
    # capacity runs only; the plan rate limiter (ENTERPRISE: unlimited) stays enabled.
    app_module.limiter.enabled = False
uvicorn.run(app_module.app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
"""


def _start_server(url: str, port: int, route_limiter: str) -> subprocess.Popen[bytes]:
    env = os.environ.copy()
    env.update(
        WHITEPACT_DATABASE_URL=url.replace("postgresql://", "postgresql+asyncpg://"),
        WHITEPACT_AUTO_MIGRATE="false",
        WHITEPACT_ENV="development",
        RAI_AUTH_ENABLED="true",
        WHITEPACT_AUTH_ENABLED="true",
        WHITEPACT_ALLOW_UNISOLATED_EXECUTION="",
    )
    for noisy in ("WHITEPACT_REDIS_URL", "RAI_REDIS_URL"):
        env.pop(noisy, None)
    return subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", _LAUNCHER, "-", str(port), route_limiter],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _server_usage(pid: int) -> dict[str, float]:
    try:
        out = subprocess.run(  # noqa: S603, S607
            ["ps", "-o", "rss=,time=", "-p", str(pid)], capture_output=True, text=True
        ).stdout.split()
        rss_mb = int(out[0]) / 1024
        parts = out[1].replace("-", ":").split(":")
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        return {"rss_mb": round(rss_mb, 1), "cpu_seconds": round(seconds, 2)}
    except Exception:
        return {}


async def _level(client, label: str, make, concurrency: int, total: int) -> dict:
    latencies: list[float] = []
    errors: dict[str, int] = {}
    sem = asyncio.Semaphore(concurrency)
    ok_bodies = 0
    outcomes: dict[str, int] = {}

    async def one() -> None:
        nonlocal ok_bodies
        async with sem:
            start = time.perf_counter()
            try:
                response = await make(client)
                took = (time.perf_counter() - start) * 1000
                if response.status_code == 200:
                    latencies.append(took)
                    ok_bodies += 1
                    try:
                        body = response.json()
                        tag = body.get("error") or body.get("decision") or "ok"
                    except Exception:
                        tag = "non_json"
                    outcomes[str(tag)] = outcomes.get(str(tag), 0) + 1
                else:
                    key = f"http_{response.status_code}"
                    errors[key] = errors.get(key, 0) + 1
            except Exception as exc:
                key = type(exc).__name__
                errors[key] = errors.get(key, 0) + 1

    began = time.perf_counter()
    await asyncio.gather(*(one() for _ in range(total)))
    elapsed = time.perf_counter() - began
    result: dict = {
        "workload": label,
        "concurrency": concurrency,
        "requests": total,
        "ok": ok_bodies,
        "errors": errors,
        "outcomes": outcomes,
        "error_rate": round(sum(errors.values()) / total, 4),
        "duration_s": round(elapsed, 2),
        "throughput_rps": round(ok_bodies / elapsed, 1) if elapsed else 0.0,
    }
    if latencies:
        result.update(
            p50_ms=round(_pct(latencies, 50), 1),
            p95_ms=round(_pct(latencies, 95), 1),
            p99_ms=round(_pct(latencies, 99), 1),
            mean_ms=round(statistics.fmean(latencies), 1),
        )
    return result


async def main_async(args: argparse.Namespace) -> int:
    import httpx

    admin = os.environ.get("WHITEPACT_TEST_PG_ADMIN_URL", "")
    if not admin:
        print("WHITEPACT_TEST_PG_ADMIN_URL is required", file=sys.stderr)
        return 2
    admin = admin.replace("postgresql+asyncpg://", "postgresql://")
    db_name, url = await _create_database(admin)
    server: subprocess.Popen[bytes] | None = None
    exit_code = 0
    report: dict = {}
    try:
        await _migrate(url)
        org_id, _key_id, raw, deny_raw = await _seed(url)
        port = _free_port()
        server = _start_server(url, port, "on" if args.keep_route_limiter else "off")
        base = f"http://127.0.0.1:{port}"
        headers = {"Authorization": f"Bearer {raw}"}
        deny_headers = {"Authorization": f"Bearer {deny_raw}"}
        async with httpx.AsyncClient(base_url=base, timeout=args.timeout) as probe:
            for _ in range(120):
                try:
                    if (await probe.get("/livez")).status_code == 200:
                        break
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            else:
                print("server did not become ready", file=sys.stderr)
                return 3

        workloads = {
            "authenticated read": lambda c: c.get(
                "/api/v1/governance/test-counter", headers=headers
            ),
            "DENY / quarantine refusal (no authority) + evidence write": lambda c: c.post(
                "/api/v1/governance/tools/call",
                headers=deny_headers,
                json={"name": "rai_scan", "arguments": {"text": "x"}, "purpose": PURPOSE},
            ),
            "REQUIRE_APPROVAL + evidence + approval row": lambda c: c.post(
                "/api/v1/governance/tools/call",
                headers=headers,
                json={"name": TOOL, "arguments": {}, "purpose": PURPOSE},
            ),
        }
        results: list[dict] = []
        effects_before = await _scalar(
            url, "SELECT COALESCE(SUM(counter),0) FROM test_consequential_counters"
        )
        for level in [int(x) for x in args.levels.split(",")]:
            total = max(args.requests, level * args.per_connection)
            limits = httpx.Limits(max_connections=level, max_keepalive_connections=level)
            async with httpx.AsyncClient(
                base_url=base, timeout=args.timeout, limits=limits
            ) as client:
                for _ in range(10):  # warm the path before measuring
                    await workloads["authenticated read"](client)
                for label, make in workloads.items():
                    approvals_before = await _scalar(
                        url, "SELECT count(*) FROM governance_approvals WHERE org_id = :o", o=org_id
                    )
                    row = await _level(client, label, make, level, total)
                    approvals_after = await _scalar(
                        url, "SELECT count(*) FROM governance_approvals WHERE org_id = :o", o=org_id
                    )
                    if label.startswith("REQUIRE_APPROVAL"):
                        row["approval_rows_created"] = approvals_after - approvals_before
                        row["approval_rows_match_ok_responses"] = (
                            approvals_after - approvals_before == row["ok"]
                        )
                    results.append(row)
                    print(json.dumps(row), flush=True)
            row_usage = _server_usage(server.pid)
            results[-1]["server_after_level"] = row_usage
        effects_after = await _scalar(
            url, "SELECT COALESCE(SUM(counter),0) FROM test_consequential_counters"
        )
        unauthorized_effects = effects_after - effects_before
        chain_ok = await _scalar(
            url,
            "SELECT count(*) FROM governance_evidence WHERE org_id = :o",
            o=org_id,
        )
        report = {
            "measurement": "real HTTP (uvicorn, 1 worker) + real PostgreSQL, API-key authenticated",
            "not_included": [
                "TLS",
                "reverse proxy",
                "multiple workers or replicas",
                "database on another host",
                "governed execution in a container",
                "MCP transport",
                "client and server on separate machines (they share this host)",
            ],
            "is_an_slo": False,
            "route_limiter": "ON (capped by 429s)"
            if args.keep_route_limiter
            else "OFF (plan limiter ON)",
            "unauthorized_effects": unauthorized_effects,
            "evidence_rows_for_org": chain_ok,
            "hardware": {
                "machine": platform.machine(),
                "os": platform.platform(),
                "python": platform.python_version(),
            },
            "source_commit": subprocess.run(  # noqa: S603, S607
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True
            ).stdout.strip(),
            "results": results,
        }
        if unauthorized_effects != 0:
            print(f"FAIL: {unauthorized_effects} unauthorized effect(s)", file=sys.stderr)
            exit_code = 1
        bad = [
            r
            for r in results
            if r["error_rate"] > args.max_error_rate
            or r.get("approval_rows_match_ok_responses") is False
        ]
        if bad:
            print(
                "FAIL: error rate above "
                f"{args.max_error_rate:.1%} or approval rows do not match at: "
                + ", ".join(f"{r['workload']}@{r['concurrency']}" for r in bad),
                file=sys.stderr,
            )
            exit_code = max(exit_code, 1)
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=15)
            except subprocess.TimeoutExpired:
                server.kill()
        await _drop_database(admin, db_name)
    Path(args.out).write_text(json.dumps(report, indent=2) + "\n")
    print(f"wrote {args.out}; exit {exit_code}")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--levels", default="1,10,100,1000")
    parser.add_argument(
        "--requests", type=int, default=400, help="minimum requests per workload per level"
    )
    parser.add_argument(
        "--per-connection", type=int, default=3, help="requests per connection at high levels"
    )
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-error-rate", type=float, default=0.0)
    parser.add_argument(
        "--keep-route-limiter",
        action="store_true",
        help="leave the per-route 30/minute slowapi limit on (reports the 429 cap instead of capacity)",
    )
    parser.add_argument("--out", default="bench-http.json")
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
