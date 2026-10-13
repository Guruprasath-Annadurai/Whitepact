# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 audit→SIEM export batch smoke (audit-query / export path performance guard)."""

from __future__ import annotations

import time

from responsibleai.audit.siem_export import audit_row_to_siem_event, encode_siem_jsonl

_ROW = {
    "id": "audit-1",
    "org_id": "org-1",
    "key_id": "key-1",
    "endpoint": "/api/governance/approvals/req-1",
    "method": "POST",
    "status_code": 200,
    "timestamp": "2026-10-02T00:00:00Z",
    "request_id": "req-1",
    "duration_ms": 12,
    "entry_hash": "aa",
    "prev_hash": "bb",
}


def test_siem_encode_5k_rows_under_one_second() -> None:
    rows = [dict(_ROW, id=f"audit-{i}") for i in range(5000)]
    start = time.perf_counter()
    payload = encode_siem_jsonl(rows)
    elapsed = time.perf_counter() - start
    assert payload.count("\n") == 5000
    assert elapsed < 1.0, f"encode too slow: {elapsed:.3f}s"


def test_governance_surface_flag_on_approval_paths() -> None:
    event = audit_row_to_siem_event(_ROW)
    assert event["governance_surface"] is True
    event2 = audit_row_to_siem_event({**_ROW, "endpoint": "/api/health"})
    assert event2["governance_surface"] is False
