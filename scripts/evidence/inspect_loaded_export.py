# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline structural inspection, NOT proof of authority or external effects.

The bounded console export omits canonical hash preimages and signatures. This
tool deliberately cannot verify those properties and never contacts a server.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

FORMAT = "whitepact-bounded-evidence-v1"
MAX_BYTES = 4 * 1024 * 1024
DECISIONS = {"ALLOW", "ALLOW_WITH_REDACTION", "REQUIRE_APPROVAL", "DENY", "QUARANTINE"}
OUTCOMES = {"SUCCEEDED", "FAILED", "UNKNOWN", "NOT_ATTEMPTED"}
FIELDS = {
    "evidence_id",
    "action_type",
    "target",
    "agent_id",
    "identity_id",
    "purpose",
    "risk_tier",
    "decision",
    "policy_version",
    "recorded_at",
    "evaluated_at",
    "approval_id",
    "execution_authorization_id",
    "hash",
    "prev_hash",
    "integrity_status",
    "outcome_status",
    "reconciliation_status",
}


class ExportError(ValueError):
    """Safe fixed diagnostics; do not echo potentially sensitive input."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ExportError("Duplicate JSON field")
        result[key] = value
    return result


def load_export(path: Path) -> dict:
    # Read only a bounded amount even if the file grows after stat().
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ExportError("Export exceeds inspection size limit")
    try:
        return json.loads(raw, object_pairs_hook=_object, parse_constant=_invalid_number)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ExportError("Export is not valid JSON") from None


def _invalid_number(value: str):
    raise ExportError("Invalid JSON number")


def inspect_export(value: object) -> dict:
    if not isinstance(value, dict) or set(value) != {"format", "scope", "records"}:
        raise ExportError("Invalid bounded export envelope")
    if value["format"] != FORMAT or not isinstance(value["scope"], str):
        raise ExportError("Unsupported bounded export format")
    records = value["records"]
    if not isinstance(records, list) or len(records) > 200:
        raise ExportError("Export must contain at most 200 loaded records")
    seen = set()
    hashes = {}
    decisions, outcomes = Counter(), Counter()
    for record in records:
        if not isinstance(record, dict) or not set(record).issubset(FIELDS):
            raise ExportError("Unsupported record fields")
        if any(not (v is None or type(v) in (str, int, float, bool)) for v in record.values()):
            raise ExportError("Record values must be scalar")
        if any(type(v) is float and not math.isfinite(v) for v in record.values()):
            raise ExportError("Invalid JSON number")
        identity = record.get("evidence_id")
        if not isinstance(identity, str) or not identity or identity in seen:
            raise ExportError("Evidence IDs must be present and distinct")
        seen.add(identity)
        for field in ("hash", "prev_hash"):
            digest = record.get(field)
            if digest is not None and (
                not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)
            ):
                raise ExportError("Invalid hash reference")
        digest = record.get("hash")
        if digest is not None:
            if digest in hashes:
                raise ExportError("Duplicate hash reference")
            hashes[digest] = record
        decision, outcome = record.get("decision"), record.get("outcome_status")
        decisions[
            decision
            if isinstance(decision, str) and decision in DECISIONS
            else "UNRECOGNIZED_OR_MISSING"
        ] += 1
        outcomes[
            outcome
            if isinstance(outcome, str) and outcome in OUTCOMES
            else "UNRECOGNIZED_OR_MISSING"
        ] += 1
    # Membership is only an observation about supplied references. Missing links
    # can reflect a partial window, not tampering. Matching links prove nothing
    # about omitted payloads, supplied hashes, anchors, signatures or outcomes.
    observed_links = sum(r.get("prev_hash") in hashes for r in records if r.get("prev_hash"))
    return {
        "inspection": "STRUCTURAL_ONLY",
        "record_count": len(records),
        "decisions": dict(sorted(decisions.items())),
        "outcomes": dict(sorted(outcomes.items())),
        "unknown_outcomes": outcomes["UNKNOWN"],
        "references_to_loaded_hashes": observed_links,
        "cryptographic_verification": "NOT_POSSIBLE_FROM_BOUNDED_EXPORT",
        "authority_proven": False,
        "external_effect_proven": False,
        "external_anchor_checked": False,
        "scope": "Loaded scalar records only; no complete-history or signature claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_export(load_export(args.export))
    except (OSError, ExportError):
        # Paths, JSON payloads, details and provider exceptions may contain
        # private data. CLI failure intentionally has one stable safe message.
        print(
            json.dumps({"inspection": "REJECTED", "error": "Invalid or unreadable bounded export"})
        )
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
