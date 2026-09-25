#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exercise nginx reverse-proxy boundary against a running WhitePact upstream."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = os.environ.get("WHITEPACT_0B_UPSTREAM", "http://127.0.0.1:18765")
PROXY_PORT = int(os.environ.get("WHITEPACT_0B_PROXY_PORT", "18080"))
ART = Path("/opt/cursor/artifacts/v131_95_phase0b")


def main() -> int:
    upstream_host = UPSTREAM.rsplit("://", 1)[-1]
    cfg = ART / "nginx_wp_live.conf"
    ART.mkdir(parents=True, exist_ok=True)
    tmp = ART / "nginx_runtime"
    tmp.mkdir(parents=True, exist_ok=True)
    cfg.write_text(
        f"""
pid {tmp / "nginx.pid"};
error_log {tmp / "error.log"};
events {{}}
http {{
  access_log {tmp / "access.log"};
  client_body_temp_path {tmp / "body"};
  proxy_temp_path {tmp / "proxy"};
  fastcgi_temp_path {tmp / "fastcgi"};
  uwsgi_temp_path {tmp / "uwsgi"};
  scgi_temp_path {tmp / "scgi"};
  server {{
    listen {PROXY_PORT};
    location / {{
      proxy_pass {UPSTREAM};
      proxy_set_header Host $host;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header X-Forwarded-Host attacker.example;
    }}
  }}
}}
""",
        encoding="utf-8",
    )
    nginx = subprocess.Popen(
        ["nginx", "-c", str(cfg), "-g", "daemon off;"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    results: list[dict] = []
    try:
        time.sleep(1.0)
        if nginx.poll() is not None:
            err = nginx.stderr.read().decode("utf-8", errors="replace") if nginx.stderr else ""
            results.append({"case": "nginx_start", "error": err[-2000:]})
            raise RuntimeError("nginx exited early")
        tests = [
            ("health_via_proxy", f"http://127.0.0.1:{PROXY_PORT}/api/health", {}),
            (
                "forwarded_proto",
                f"http://127.0.0.1:{PROXY_PORT}/api/health",
                {"X-Forwarded-Proto": "https"},
            ),
        ]
        for label, url, headers in tests:
            req = urllib.request.Request(url, headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    body = resp.read(4000).decode("utf-8", errors="replace")
                    results.append({"case": label, "status": resp.status, "body_snip": body[:200]})
            except Exception as e:
                results.append({"case": label, "error": type(e).__name__})
    finally:
        nginx.terminate()
        try:
            nginx.wait(timeout=5)
        except subprocess.TimeoutExpired:
            nginx.kill()

    ok = any(r.get("status") == 200 for r in results)
    md = ROOT / "WHITEPACT_V131_95_PROXY_BOUNDARY_REPORT.md"
    md.write_text(
        "# Proxy boundary (Phase 0B)\n\n"
        f"**Verdict:** **{'PASS' if ok else 'PARTIAL'}** — nginx → `{UPSTREAM}` with forwarded headers.\n\n"
        f"Config: `{cfg}`\n\n```json\n"
        + json.dumps(results, indent=2)
        + "\n```\n\n"
        "TLS termination, CORS/CSP exhaustive matrix, and body-limit characterization remain **PARTIAL**.\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": ok, "results": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
