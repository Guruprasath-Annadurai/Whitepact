# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Separate launch-evidence completeness from release authorization.

This process reads a JSON packet. It does not contact GitHub, a cloud
provider, Antigravity, or an owner. A packet that says ACCEPTED, even
with a URL and a digest, is not proof. Production authorization from
this command is always NO-GO.

Four results are reported separately:

1. ``packet_completeness`` — the packet names every gate and binds each
   claim to a head, tree, environment, and, where required, an artifact
   digest. Placeholder values are incomplete.
2. ``independent_verification`` — always ``UNVERIFIED`` here. An
   external reviewer must fetch the named artifact and compare it to
   the candidate head and tree.
3. ``owner_approval`` — always ``NOT_AUTHORIZED`` here. A JSON field
   cannot authorize spend, staging, or launch.
4. ``production_authorization`` — always ``NO-GO``.
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

COMPLETE = "COMPLETE"
INCOMPLETE = "INCOMPLETE"
UNVERIFIED = "UNVERIFIED"
NOT_AUTHORIZED = "NOT_AUTHORIZED"
NO_GO = "NO-GO"

_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_PLACEHOLDER = re.compile(
    r"(example(?:\.(?:com|org|net))?|placeholder|changeme|\btodo\b|\btbd\b|dummy)",
    re.IGNORECASE,
)
_VERIFIER = (
    "Fetch the artifact outside this process. Compare its git head and "
    "tree to the candidate. Accept GitHub Actions only from a run whose "
    "headSha equals the candidate head. Accept independent qualification "
    "only from Antigravity's own report. Accept owner approval only from "
    "the owner, not from this packet."
)


@dataclass(frozen=True)
class Gate:
    gate_id: str
    kind: str
    mandatory: bool = True
    requires_artifact: bool = False


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


def _candidate(payload: dict[str, Any]) -> tuple[str, str] | str:
    raw = payload.get("candidate")
    if not isinstance(raw, dict):
        return "candidate head and tree are missing"
    head = raw.get("head")
    tree = raw.get("tree")
    if not isinstance(head, str) or _SHA.fullmatch(head) is None:
        return "candidate head is not a 40-character git sha"
    if not isinstance(tree, str) or _SHA.fullmatch(tree) is None:
        return "candidate tree is not a 40-character git sha"
    return head, tree


def _bound(record: dict[str, Any], head: str, tree: str, gate: Gate) -> str | None:
    if record.get("status") != "ACCEPTED":
        return f"status is {record.get('status')!r}"
    if record.get("kind") != gate.kind:
        return f"kind {record.get('kind')!r} does not match required {gate.kind}"
    if record.get("head") != head or record.get("tree") != tree:
        return "evidence head or tree does not match the candidate"
    environment = record.get("environment")
    if not isinstance(environment, str) or not environment.strip():
        return "environment is missing"
    if _PLACEHOLDER.search(environment):
        return "environment is a placeholder"
    authority = record.get("verification_authority")
    if not isinstance(authority, str) or not authority.strip():
        return "verification authority is missing"
    if _PLACEHOLDER.search(authority):
        return "verification authority is a placeholder"
    if not gate.requires_artifact:
        return None
    artifact = record.get("artifact")
    digest = record.get("artifact_digest")
    if not isinstance(artifact, str) or not artifact.startswith("https://"):
        return "artifact must be an https URL"
    if _PLACEHOLDER.search(artifact):
        return "artifact URL is a placeholder"
    if not isinstance(digest, str) or _DIGEST.fullmatch(digest) is None:
        return "artifact digest must be sha256:<64 hex>"
    if gate.kind in {LIVE_STAGING, OWNER_APPROVAL, INDEPENDENT_AUDIT} and environment in {
        "offline",
        "local",
        "unit-test",
    }:
        return "live, independent, and owner gates cannot use an offline environment"
    return None


def evaluate(payload: dict[str, Any]) -> dict[str, Any]:
    """Score completeness. Never authorize production."""
    failures: list[dict[str, str]] = []
    candidate = _candidate(payload)
    if isinstance(candidate, str):
        failures.append({"gate_id": "candidate", "reason": candidate})
        head = tree = ""
    else:
        head, tree = candidate
    try:
        found = _records(payload)
    except ValueError as exc:
        return _decision([{"gate_id": "packet", "reason": str(exc)}])

    for gate in GATES:
        if not gate.mandatory:
            continue
        record = found.get(gate.gate_id)
        if record is None:
            failures.append({"gate_id": gate.gate_id, "reason": "missing evidence"})
            continue
        if isinstance(candidate, str):
            continue
        reason = _bound(record, head, tree, gate)
        if reason is not None:
            failures.append({"gate_id": gate.gate_id, "reason": reason})
    return _decision(failures)


def _decision(failures: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "packet_completeness": INCOMPLETE if failures else COMPLETE,
        "independent_verification": UNVERIFIED,
        "owner_approval": NOT_AUTHORIZED,
        "production_authorization": NO_GO,
        "decision": NO_GO,
        "failures": failures,
        "verifier_procedure": _VERIFIER,
        "trust_boundary": (
            "This checker does not authenticate artifacts or approvals. "
            "production_authorization stays NO-GO."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="JSON evidence packet")
    args = parser.parse_args(argv)
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    result = evaluate(payload)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0 if result["production_authorization"] != NO_GO else 1


if __name__ == "__main__":
    raise SystemExit(main())
