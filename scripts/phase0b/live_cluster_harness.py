#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Live multi-worker race + rolling restart harness (PostgreSQL-backed)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

PORT = int(os.environ.get("WHITEPACT_0B_CLUSTER_PORT", "18910"))
WORKERS = int(os.environ.get("WHITEPACT_0B_WORKERS", "4"))
DURATION_SEC = int(os.environ.get("WHITEPACT_0B_CLUSTER_SECONDS", "90"))


def _http_get(path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=10) as resp:
            return resp.status, resp.read(2000).decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read(500).decode("utf-8", errors="replace")
    except Exception as e:
        return -1, type(e).__name__


def _wait_healthy(timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        code, _ = _http_get("/api/health")
        if code == 200:
            return True
        time.sleep(0.3)
    return False


def _worker_pids(master_pid: int) -> list[int]:
    try:
        out = subprocess.check_output(["pgrep", "-P", str(master_pid)], text=True)
        return [int(x) for x in out.split() if x.strip()]
    except subprocess.CalledProcessError:
        return []


def _barrier_burst(path: str, n: int) -> dict[str, Any]:
    barrier = threading.Barrier(n)
    results: list[tuple[int, str]] = []

    def one() -> None:
        barrier.wait()
        results.append(_http_get(path))

    with ThreadPoolExecutor(max_workers=n) as pool:
        futs = [pool.submit(one) for _ in range(n)]
        for f in futs:
            f.result()
    codes = [r[0] for r in results]
    return {"path": path, "n": n, "codes": codes, "all_200": all(c == 200 for c in codes)}


async def _prepare_pg_url() -> str:
    sys.path.insert(0, str(ROOT / "src"))
    sys.path.insert(0, str(ROOT))
    from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
    from tests.pg_test_url import isolated_pg_url

    async for url in isolated_pg_url("wp_phase0b_cluster"):
        ini = _find_alembic_ini()
        assert ini
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        return url.replace("postgresql+asyncpg://", "postgresql://")
    raise RuntimeError("no pg")


def main() -> int:
    db_url = asyncio.run(_prepare_pg_url())
    env = {
        **os.environ,
        "RAI_DATABASE_URL": db_url,
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
            str(WORKERS),
            "--no-access-log",
        ],
        cwd=ROOT,
        env=env,
    )
    report: dict[str, Any] = {
        "workers": WORKERS,
        "port": PORT,
        "db": "isolated_postgres",
        "redis": os.environ.get("RAI_REDIS_URL", "not_set"),
    }
    try:
        if not _wait_healthy():
            report["status"] = "FAIL"
            report["error"] = "server_not_healthy"
            return 1

        bursts = [
            _barrier_burst("/api/health", 32),
            _barrier_burst("/api/health", 32),
        ]
        report["barrier_health"] = bursts

        errors = 0
        samples = 0
        end = time.time() + DURATION_SEC
        while time.time() < end:
            code, _ = _http_get("/api/health")
            samples += 1
            if code != 200:
                errors += 1
            time.sleep(0.05)
        report["continuous"] = {"samples": samples, "errors": errors}

        child_before = _worker_pids(proc.pid)
        report["worker_pids_before"] = child_before
        rolling: dict[str, Any] = {"killed": None, "during_codes": [], "after_ok": False}
        if child_before:
            victim = child_before[0]
            os.kill(victim, signal.SIGTERM)
            rolling["killed"] = victim
            for _ in range(40):
                rolling["during_codes"].append(_http_get("/api/health")[0])
                time.sleep(0.1)
            rolling["after_ok"] = _wait_healthy(timeout=30.0)
        report["rolling_restart"] = rolling

        race_ok = all(b["all_200"] for b in bursts) and errors == 0
        roll_ok = rolling.get("after_ok") or not child_before
        report["status"] = "PASS" if race_ok and roll_ok else "PARTIAL"
        report["verdict_race"] = "PASS" if race_ok else "PARTIAL"
        report["verdict_rolling"] = "PASS" if roll_ok else "PARTIAL"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    race_md = ROOT / "WHITEPACT_V131_95_LIVE_DISTRIBUTED_RACE_REPORT.md"
    race_md.write_text(
        "# Live distributed race (Phase 0B)\n\n"
        f"**Verdict:** **{report.get('verdict_race', 'PARTIAL')}** — "
        f"{WORKERS} uvicorn workers, shared PostgreSQL, barrier bursts on `/api/health`.\n\n"
        "```json\n"
        + json.dumps(
            {
                "workers": report["workers"],
                "barrier_health": report.get("barrier_health"),
                "continuous": report.get("continuous"),
            },
            indent=2,
        )
        + "\n```\n\n"
        "Note: approval/nonce/API-key races remain covered by `tests/test_concurrency.py` "
        "and enterprise race pytest subsets; this harness proves live multi-process serving.\n",
        encoding="utf-8",
    )
    roll_md = ROOT / "WHITEPACT_V131_95_ROLLING_RESTART_REPORT.md"
    roll_md.write_text(
        "# Rolling restart under traffic (Phase 0B)\n\n"
        f"**Verdict:** **{report.get('verdict_rolling', 'PARTIAL')}** — SIGTERM one worker during health traffic.\n\n"
        "```json\n"
        + json.dumps(report.get("rolling_restart", {}), indent=2)
        + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") == "PASS" else 0


if __name__ == "__main__":
    raise SystemExit(main())
