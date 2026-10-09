# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed release evidence checker.

Completeness, artifact verification, and independent authorization are
separate questions. A record that says ``ACCEPTED`` is a declaration,
not proof. This script does not contact GitHub, a cloud provider, or
an independent reviewer, so live verification is unavailable and the
production decision stays ``NO-GO``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

LOCAL_TEST = "local_test"
GITHUB_ACTIONS = "github_actions"
INDEPENDENT_AUDIT = "independent_audit"
LIVE_STAGING = "live_staging"
OWNER_APPROVAL = "owner_approval"

GO = "GO"
CONDITIONAL_GO = "CONDITIONAL_GO"
NO_GO = "NO-GO"
UNVERIFIED = "UNVERIFIED"

_PLACEHOLDER = re.compile(
    r"(placeholder|changeme|example\.com|example\.org|example\.net|"
    r"evidence\.example|\blocalhost\b|127\.0\.0\.1|\bTODO\b|\bTBD\b)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Gate:
    gate_id: str
    kind: str
    mandatory: bool = True
    requires_artifact: bool = False


# Live and owner gates require an artifact pointer. A bare status string
# is not evidence.
GATES: tuple[Gate, ...] = (
    Gate("runtime.authority", LOCAL_TEST),
    Gate("tenant.isolation", LOCAL_TEST),
    Gate("grant.replay", LOCAL_TEST),
    Gate("ci.canonical", GITHUB_ACTIONS, requires_artifact=True),
    Gate("independent.qualification", INDEPENDENT_AUDIT, requires_artifact=True),
    Gate("staging.live", LIVE_STAGING, requires_artifact=True),
    Gate("backup.restore.live", LIVE_STAGING, requires_artifact=True),
    Gate("cloud.security.live", LIVE_STAGING, requires_artifact=True),
    Gate("owner.infrastructure", OWNER_APPROVAL, requires_artifact=True),
    Gate("owner.commercial", OWNER_APPROVAL, requires_artifact=True),
    Gate("owner.legal", OWNER_APPROVAL, requires_artifact=True),
    Gate("public.launch", OWNER_APPROVAL, requires_artifact=True),
)


def _records(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("evidence", [])
    if not isinstance(raw, list):
        raise ValueError("evidence must be a list")
    found: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict) or "gate_id" not in item:
            raise ValueError("each evidence item needs gate_id")
        found[str(item["gate_id"])] = item
    return found


def _artifact_problem(artifact: object) -> str | None:
    if not isinstance(artifact, str) or not artifact.strip():
        return "accepted record has no artifact pointer"
    value = artifact.strip()
    if _PLACEHOLDER.search(value):
        return "placeholder artifact is not production proof"
    if not value.startswith("https://") or any(character.isspace() for character in value):
        return "artifact pointer is not a verifiable https URL"
    return None


def _declaration_problem(gate: Gate, record: dict[str, Any] | None) -> str | None:
    if record is None:
        return "missing evidence"
    if record.get("status") != "ACCEPTED":
        return f"status is {record.get('status')!r}"
    if record.get("kind") != gate.kind:
        return f"kind {record.get('kind')!r} does not match required {gate.kind}"
    if gate.requires_artifact:
        return _artifact_problem(record.get("artifact"))
    return None


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Separate a complete declaration from production proof.

    Caller-supplied ``decision``, ``artifact_verification``, and
    ``independent_authorization`` fields are ignored. ``GO`` and
    ``CONDITIONAL_GO`` are not produced while this process cannot
    verify artifacts or an independent authorization.
    """
    found = _records(payload)
    failures: list[dict[str, str]] = []
    declared: list[str] = []
    for gate in GATES:
        if not gate.mandatory:
            continue
        reason = _declaration_problem(gate, found.get(gate.gate_id))
        if reason is None:
            declared.append(gate.gate_id)
        else:
            failures.append({"gate_id": gate.gate_id, "reason": reason})

    completeness = "COMPLETE" if not failures else "INCOMPLETE"
    return {
        "decision": NO_GO,
        "completeness": completeness,
        "artifact_verification": UNVERIFIED,
        "independent_authorization": UNVERIFIED,
        "production_proof": False,
        "declared": declared,
        "accepted": [],
        "failures": failures,
        "conditional_scope": None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="JSON evidence packet")
    args = parser.parse_args(argv)
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = evaluate(payload)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    if result["decision"] == GO:
        return 0
    if result["decision"] == CONDITIONAL_GO:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
