# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — lightweight load smoke (B9). Not enterprise capacity proof."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app

REPO = Path(__file__).resolve().parents[2]
EVIDENCE = REPO / "artifacts" / "production" / "b9-load-smoke.json"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    monkeypatch.setenv("WHITEPACT_DB_PATH", ":memory:")
    monkeypatch.setenv("WHITEPACT_AUTO_MIGRATE", "true")
    return TestClient(app)


def test_health_endpoint_load_smoke_records_measurements(client: TestClient) -> None:
    duration_s = 5.0
    deadline = time.monotonic() + duration_s
    latencies_ms: list[float] = []
    errors = 0
    count = 0
    while time.monotonic() < deadline:
        start = time.perf_counter()
        resp = client.get("/api/health")
        elapsed_ms = (time.perf_counter() - start) * 1000
        latencies_ms.append(elapsed_ms)
        count += 1
        if resp.status_code >= 500:
            errors += 1
    latencies_ms.sort()
    p95 = latencies_ms[int(len(latencies_ms) * 0.95) - 1] if latencies_ms else 0.0
    p99 = latencies_ms[int(len(latencies_ms) * 0.99) - 1] if latencies_ms else 0.0
    rps = count / duration_s
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(
            {
                "phase": "B9",
                "test": "health_load_smoke",
                "evidence_categories": ["LOAD_TESTED"],
                "environment": "pytest_testclient_in_memory_sqlite",
                "duration_seconds": duration_s,
                "requests": count,
                "errors": errors,
                "measured_rps": round(rps, 2),
                "measured_p95_ms": round(p95, 3),
                "measured_p99_ms": round(p99, 3),
                "soak_duration_seconds": 0,
                "limitations": "In-process TestClient only; not multi-replica or Postgres.",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    assert errors == 0
    assert count > 50
