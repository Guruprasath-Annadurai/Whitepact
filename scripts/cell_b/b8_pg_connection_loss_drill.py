#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""B8 — readiness fails closed when DB ping fails (runtime drill)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app


def main() -> int:
    class _BrokenEngine:
        async def ping(self, timeout_seconds: float = 2.0) -> bool:
            return False

    app_module._db_engine = _BrokenEngine()
    client = TestClient(app)
    live = client.get("/livez").status_code
    ready = client.get("/readyz").status_code
    out = REPO / "artifacts" / "production" / "b8-pg-connection-loss-drill.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "phase": "B8",
                "test": "synthetic_db_ping_failure",
                "timestamp": datetime.now(UTC).isoformat(),
                "livez_status": live,
                "readyz_status": ready,
                "expected": {"livez": 200, "readyz": 503},
                "passed": live == 200 and ready == 503,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0 if live == 200 and ready == 503 else 1


if __name__ == "__main__":
    raise SystemExit(main())
