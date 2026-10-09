# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed release evidence checker.

A local test log cannot satisfy a live, independent, or owner gate.
``GO`` is returned only when every mandatory gate has an accepted
evidence record of the required kind. Missing evidence is ``NO-GO``.
This script does not contact GitHub, a cloud provider, or Antigravity.
"""

from __future__ import annotations

import argparse
import json
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


def _accepted(gate: Gate, record: dict[str, Any] | None) -> str | None:
    if record is None:
        return "missing evidence"
    if record.get("status") != "ACCEPTED":
        return f"status is {record.get('status')!r}"
    if record.get("kind") != gate.kind:
        return f"kind {record.get('kind')!r} does not match required {gate.kind}"
    artifact = record.get("artifact")
    if gate.requires_artifact and not (isinstance(artifact, str) and artifact.strip()):
        return "accepted record has no artifact pointer"
    return None


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a decision that fails closed.

    ``CONDITIONAL_GO`` is never inferred. A caller must set
    ``conditional_scope`` to a non-empty string and every blocking
    failure must be absent. Any mandatory failure is ``NO-GO``.
    """
    found = _records(payload)
    failures: list[dict[str, str]] = []
    accepted: list[str] = []
    for gate in GATES:
        if not gate.mandatory:
            continue
        reason = _accepted(gate, found.get(gate.gate_id))
        if reason is None:
            accepted.append(gate.gate_id)
        else:
            failures.append({"gate_id": gate.gate_id, "reason": reason})

    scope = payload.get("conditional_scope")
    if not failures and isinstance(scope, str) and scope.strip():
        decision = CONDITIONAL_GO
    elif not failures:
        decision = GO
    else:
        decision = NO_GO

    return {
        "decision": decision,
        "accepted": accepted,
        "failures": failures,
        "conditional_scope": scope if decision == CONDITIONAL_GO else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="JSON evidence packet")
    args = parser.parse_args(argv)
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = evaluate(payload)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["decision"] == GO else 2 if result["decision"] == CONDITIONAL_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
