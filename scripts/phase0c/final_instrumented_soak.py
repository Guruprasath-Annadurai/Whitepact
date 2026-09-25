#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 0C server-instrumented local soak (PostgreSQL + optional Redis)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "WHITEPACT_V131_95_FINAL_INSTRUMENTED_SOAK.md"
PORT = int(os.environ.get("WHITEPACT_0C_SOAK_PORT", "18920"))
SECONDS = int(os.environ.get("WHITEPACT_0C_SOAK_SECONDS", "1800"))


def _proc_stats(pid: int) -> dict[str, Any]:
    out: dict[str, Any] = {"pid": pid}
    try:
        with open(f"/proc/{pid}/status") as f:
            lines = {
                line.split(":", 1)[0].strip(): line.split(":", 1)[1].strip()
                for line in f
                if ":" in line
            }
        out["rss_kb"] = int(lines.get("VmRSS", "0 kB").split()[0])
        out["vms_kb"] = int(lines.get("VmSize", "0 kB").split()[0])
        out["threads"] = int(lines.get("Threads", "0"))
    except OSError as exc:
        out["error"] = str(exc)
    try:
        with open(f"/proc/{pid}/fd") as fds:
            out["open_fds"] = len(list(fds))
    except OSError:
        out["open_fds"] = None
    return out


def _worker_pids(master: int) -> list[int]:
    try:
        raw = subprocess.check_output(["pgrep", "-P", str(master)], text=True)
        return [int(x) for x in raw.split() if x.strip()]
    except subprocess.CalledProcessError:
        return []


def _aggregate_server(master_pid: int) -> dict[str, Any]:
    pids = [master_pid] + _worker_pids(master_pid)
    rss = threads = fds = 0
    for p in pids:
        s = _proc_stats(p)
        rss += s.get("rss_kb", 0)
        threads += s.get("threads", 0)
        if s.get("open_fds") is not None:
            fds += s["open_fds"]
    return {"pids": pids, "rss_kb_total": rss, "threads_total": threads, "open_fds_total": fds}


async def _pg_metrics(db_url: str) -> dict[str, int]:
    import asyncpg

    u = db_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(u, timeout=3)
    try:
        row = await conn.fetchrow(
            "SELECT count(*) FILTER (WHERE state = 'active') AS active, "
            "count(*) FILTER (WHERE state = 'idle') AS idle FROM pg_stat_activity "
            "WHERE datname = current_database()"
        )
        return {"db_active": int(row["active"]), "db_idle": int(row["idle"])}
    finally:
        await conn.close()


async def _redis_clients(redis_url: str) -> dict[str, int]:
    import redis.asyncio as redis

    client = redis.from_url(redis_url)
    try:
        info = await client.info("clients")
        return {"redis_connected_clients": int(info.get("connected_clients", 0))}
    finally:
        await client.aclose()


def _http_mix(base: str, paths: list[str]) -> tuple[int, float]:
    path = paths[int(time.time() * 1000) % len(paths)]
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(f"{base}{path}", timeout=8) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except Exception:
        code = -1
    return code, (time.perf_counter() - t0) * 1000


async def _prepare_pg() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
    from tests.pg_test_url import isolated_pg_url

    async for url in isolated_pg_url("wp_phase0c_soak"):
        ini = _find_alembic_ini()
        assert ini
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        return url.replace("postgresql+asyncpg://", "postgresql://")
    raise RuntimeError("no pg")


def main() -> int:
    db_url = asyncio.run(_prepare_pg())
    redis_url = os.environ.get("RAI_REDIS_URL", "redis://127.0.0.1:6379/0")
    env = {
        **os.environ,
        "RAI_DATABASE_URL": db_url,
        "RAI_REDIS_URL": redis_url,
        "WHITEPACT_ENV": "development",
        "WHITEPACT_LOG_LEVEL": "ERROR",
        "PYTHONPATH": f"{ROOT / 'src'}:{ROOT}",
    }
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(PORT),
            "--workers",
            "4",
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
    )
    base = f"http://127.0.0.1:{PORT}"
    paths = [
        "/api/health",
        "/api/health",
        "/api/openapi.json",
        "/api/health",
    ]
    samples: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0
    try:
        for _ in range(120):
            try:
                with urllib.request.urlopen(f"{base}/api/health", timeout=3):
                    break
            except Exception:
                time.sleep(0.25)
        else:
            raise RuntimeError("server not healthy")

        interval = max(5, SECONDS // 40)
        t_end = time.time() + SECONDS
        next_sample = time.time()
        while time.time() < t_end:
            code, ms = _http_mix(base, paths)
            latencies.append(ms)
            if code < 0 or code >= 500:
                errors += 1
            if time.time() >= next_sample:
                snap: dict[str, Any] = {
                    "t": round(time.time() - (t_end - SECONDS), 1),
                    "server": _aggregate_server(proc.pid),
                }
                snap.update(asyncio.run(_pg_metrics(db_url)))
                try:
                    snap.update(asyncio.run(_redis_clients(redis_url)))
                except Exception as e:
                    snap["redis_error"] = type(e).__name__
                samples.append(snap)
                next_sample += interval
            time.sleep(0.15)
    finally:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()

    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0
    rss_series = [s["server"]["rss_kb_total"] for s in samples if s.get("server")]
    fd_series = [s["server"]["open_fds_total"] for s in samples if s.get("server")]
    leak_note = "NO SIGNIFICANT LEAK OBSERVED DURING 30-MIN LOCAL SOAK"
    if rss_series and rss_series[-1] > rss_series[0] * 1.25 and (rss_series[-1] - rss_series[0]) > 50_000:
        leak_note = "RSS GROWTH OBSERVED — NOT PROVEN SAFE FOR LONG PRODUCTION SOAK"

    body = (
        "# Phase 0C — LOCAL INSTRUMENTED SOAK\n\n"
        f"Duration: **{SECONDS}s** | Workers: **4** | DB: PostgreSQL | Redis: `{redis_url}`\n\n"
        f"| requests | errors | p95 ms |\n|---:|---:|---:|\n"
        f"| {len(latencies)} | {errors} | {p95:.2f} |\n\n"
        f"**Leak assessment:** {leak_note}\n\n"
        f"RSS kb (start→end): {rss_series[0] if rss_series else 'n/a'} → "
        f"{rss_series[-1] if rss_series else 'n/a'}\n\n"
        f"Open FDs (start→end): {fd_series[0] if fd_series else 'n/a'} → "
        f"{fd_series[-1] if fd_series else 'n/a'}\n\n"
        "## Sample points (25% quartiles)\n\n```json\n"
        + json.dumps(
            [
                samples[i]
                for i in [
                    0,
                    len(samples) // 4,
                    len(samples) // 2,
                    (3 * len(samples)) // 4,
                    len(samples) - 1,
                ]
                if samples
            ],
            indent=2,
        )
        + "\n```\n"
    )
    REPORT.write_text(body, encoding="utf-8")
    Path("/opt/cursor/artifacts/v131_phase0c").mkdir(parents=True, exist_ok=True)
    REPORT.write_text(body, encoding="utf-8")
    print(json.dumps({"seconds": SECONDS, "errors": errors, "samples": len(samples), "leak": leak_note}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
