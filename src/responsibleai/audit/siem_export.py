# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Map tamper-evident audit rows to enterprise SIEM JSON events (P1-06)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any


def audit_row_to_siem_event(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize one audit-log row for external SIEM ingestion."""
    endpoint = str(row.get("endpoint") or "")
    governance = endpoint.startswith("/api/governance") or "/approvals" in endpoint
    return {
        "schema": "whitepact.siem.audit.v1",
        "event_type": "WHITEPACT_AUDIT",
        "tenant_id": row.get("org_id"),
        "principal_id": row.get("key_id"),
        "agent_id": None,
        "timestamp": row.get("timestamp"),
        "correlation_id": row.get("request_id"),
        "action": {
            "method": row.get("method"),
            "path": endpoint,
            "duration_ms": row.get("duration_ms"),
        },
        "decision": {"http_status": row.get("status_code")},
        "policy": None,
        "approval": None,
        "grant": None,
        "execution": None,
        "evidence": None,
        "governance_surface": governance,
        "integrity": {
            "entry_hash": row.get("entry_hash"),
            "prev_hash": row.get("prev_hash"),
            "audit_id": row.get("id"),
        },
    }


def encode_siem_jsonl(rows: Iterable[dict[str, Any]]) -> str:
    lines = [json.dumps(audit_row_to_siem_event(row), separators=(",", ":")) for row in rows]
    return "\n".join(lines) + ("\n" if lines else "")
