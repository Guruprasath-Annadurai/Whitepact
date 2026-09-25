#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""LOCAL INSTRUMENTED SOAK — samples client latency + optional server /proc stats."""

from __future__ import annotations

import json
import os
import statistics
import subprocess
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _sample_server(pid: int) -> dict:
    try:
        with open(f"/proc/{pid}/status") as f:
            lines = dict(line.split(":", 1) for line in f if ":" in line)
        rss = int(lines.get("VmRSS", "0 kB").split()[0])
        threads = int(lines.get("Threads", "0"))
        return {"rss_kb": rss, "threads": threads}
    except OSError:
        return {}


def main() -> int:
    base = os.environ.get("WHITEPACT_0B_SOAK_URL", "http://127.0.0.1:18765")
    seconds = int(os.environ.get("WHITEPACT_0B_SOAK_SECONDS", "1800"))
    pid = int(os.environ.get("WHITEPACT_0B_SERVER_PID", "0") or "0")
    latencies: list[float] = []
    server_samples: list[dict] = []
    errors = 0
    t_end = time.time() + seconds
    while time.time() < t_end:
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(f"{base}/api/health", timeout=5) as r:
                if r.status >= 400:
                    errors += 1
        except Exception:
            errors += 1
        latencies.append((time.perf_counter() - t0) * 1000)
        if pid and len(server_samples) < 500 and len(latencies) % 60 == 0:
            server_samples.append(_sample_server(pid))
        time.sleep(0.2)
    latencies.sort()
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    body = (
        "# LOCAL INSTRUMENTED SOAK\n\n"
        f"Duration: **{seconds}s**\n\n"
        f"Target: `{base}/api/health`\n\n"
        f"| samples | errors | p95 ms |\n|---:|---:|---:|\n"
        f"| {len(latencies)} | {errors} | {p95:.2f} |\n\n"
    )
    if server_samples:
        body += f"Server samples: `{json.dumps(server_samples[:10])}`\n"
    else:
        body += "Server RSS/threads: **not captured** (set WHITEPACT_0B_SERVER_PID).\n"
    out = ROOT / "WHITEPACT_V131_95_INSTRUMENTED_SOAK_REPORT.md"
    out.write_text(body, encoding="utf-8")
    print(json.dumps({"seconds": seconds, "samples": len(latencies), "errors": errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
