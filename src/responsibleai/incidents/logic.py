"""Shared incident-record construction, used by both the `rai_incident_log`
MCP tool (`responsibleai.mcp.tools`) and the dashboard's `POST /api/incidents`
/ `POST /api/alerts/webhook` endpoints (`responsibleai.dashboard.app`).

Pulled out as a pure function (no DB access, no I/O) so the two callers
can't drift out of sync on severity → SLA-hours mapping, SIEM event-type
classification, or evidence hashing — previously this logic only existed
inline in the MCP tool handler.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any

_SLA_HOURS_BY_SEVERITY = {"critical": 1, "high": 4, "medium": 24, "low": 72}

_SIEM_EVENT_TYPE_BY_INCIDENT_TYPE = {
    "pii_leak": "DATA_EXPOSURE",
    "jailbreak_attempt": "SECURITY_VIOLATION",
    "bias_trigger": "FAIRNESS_VIOLATION",
    "hallucination": "RELIABILITY_INCIDENT",
    "policy_violation": "POLICY_BREACH",
    "cost_overrun": "FINANCIAL_ALERT",
    "drift_alert": "MODEL_DEGRADATION",
    "other": "AI_GOVERNANCE_INCIDENT",
}

_NEXT_STEPS_BY_SEVERITY = {
    "critical": "Escalate to security team and CAIO within 1 hour.",
    "high": "Assign to AI Risk Analyst for root cause analysis.",
    "medium": "Log in incident tracker and schedule review.",
    "low": "Track and include in next weekly governance report.",
}


def build_incident_record(
    *,
    incident_type: str = "other",
    severity: str = "medium",
    model_name: str = "unknown",
    provider: str = "unknown",
    description: str = "",
    evidence: dict[str, Any] | None = None,
    mitigated: bool = False,
    source: str = "manual",
) -> dict[str, Any]:
    """Build a structured incident record. Pure — does not persist anything;
    callers decide whether/how to store the result."""
    evidence = evidence or {}
    incident_id = str(uuid.uuid4())
    now = datetime.now(UTC).isoformat()

    sla_hours = _SLA_HOURS_BY_SEVERITY.get(severity, 24)
    siem_event_type = _SIEM_EVENT_TYPE_BY_INCIDENT_TYPE.get(incident_type, "AI_GOVERNANCE_INCIDENT")
    evidence_hash = hashlib.sha256(f"{incident_id}{incident_type}{description}".encode()).hexdigest()[:16]

    return {
        "incident_id": incident_id,
        "created_at": now,
        "source": source,
        "incident_type": incident_type,
        "severity": severity,
        "siem_event_type": siem_event_type,
        "model_name": model_name,
        "provider": provider,
        "description": description,
        "mitigated": mitigated,
        "evidence_hash": evidence_hash,
        "evidence_keys": list(evidence.keys()),
        "sla_resolution_hours": sla_hours,
        "status": "MITIGATED" if mitigated else "OPEN",
        "next_steps": _NEXT_STEPS_BY_SEVERITY.get(severity, _NEXT_STEPS_BY_SEVERITY["medium"]),
        "siem_payload": {
            "event_type": siem_event_type,
            "incident_id": incident_id,
            "severity": severity.upper(),
            "timestamp": now,
            "model": f"{provider}/{model_name}",
            "evidence_hash": evidence_hash,
        },
    }
