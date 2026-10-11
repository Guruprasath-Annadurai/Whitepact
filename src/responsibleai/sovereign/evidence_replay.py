# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Zero-effect replay and proof over exported governance evidence.

Replay reconstructs, validates, and explains evidence that was already
recorded. It never calls an executor and never re-issues a side effect.
Prove exports a verification artifact whose subject fields are copied
from evidence that passed the same integrity checks.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, NoReturn

from responsibleai.governance.evidence import compute_canonical_evidence_hash
from responsibleai.governance.evidence_bundle import (
    _record_from_dict,
    verify_evidence_bundle,
)
from responsibleai.sovereign.capsule import SovereignCapsule, validate_capsule
from responsibleai.sovereign.errors import SovereignError
from responsibleai.sovereign.exit_codes import EXIT_GOVERNANCE, EXIT_INVALID
from responsibleai.sovereign.protocol import PROTOCOL_VERSION, SOVEREIGN_VERSION

_REQUIRED_RECORD_FIELDS = (
    "evidence_id",
    "organization_id",
    "identity_id",
    "decision",
    "action_id",
    "agent_id",
    "action_type",
    "target",
    "authority_delegated_by",
    "hash",
    "evaluated_at",
    "integrity_version",
)


class EvidenceRejectedError(SovereignError):
    """Fail-closed rejection of missing, forged, tampered, or cross-tenant evidence."""

    def __init__(self, code: str, message: str, exit_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


def load_evidence_document(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise EvidenceRejectedError(
            "MISSING",
            f"Evidence file not found: {path}. Export a governance evidence record or bundle first.",
            EXIT_INVALID,
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceRejectedError(
            "INVALID",
            f"Evidence file is not valid JSON ({exc.msg}).",
            EXIT_INVALID,
        ) from exc
    if not isinstance(payload, dict):
        raise EvidenceRejectedError(
            "INVALID",
            "Evidence file must contain a JSON object (record, bundle, or capsule).",
            EXIT_INVALID,
        )
    return payload


def _reject(code: str, message: str) -> NoReturn:
    exit_code = EXIT_GOVERNANCE if code in {"CROSS_TENANT", "TAMPERED", "FORGED"} else EXIT_INVALID
    raise EvidenceRejectedError(code, message, exit_code)


def _require_record_fields(data: dict[str, Any]) -> None:
    missing = [key for key in _REQUIRED_RECORD_FIELDS if data.get(key) in (None, "")]
    if missing:
        _reject(
            "MISSING",
            "Evidence is missing required fields ("
            + ", ".join(missing)
            + "). Replay and prove fail closed and do not invent them.",
        )
    version = data.get("integrity_version")
    if not isinstance(version, int) or version < 2:
        _reject(
            "MISSING",
            "Evidence is not a canonical integrity v2 record. Non-canonical evidence is rejected.",
        )


def _verified_record(data: dict[str, Any]) -> dict[str, Any]:
    _require_record_fields(data)
    try:
        record = _record_from_dict(data)
    except (KeyError, TypeError, ValueError) as exc:
        _reject("INVALID", f"Evidence record could not be parsed ({exc}).")
    if record.integrity_version < 2 or not record.hash:
        _reject("MISSING", "Evidence has no canonical hash. Integrity cannot be checked.")
    recomputed = compute_canonical_evidence_hash(record.prev_hash, record)
    if recomputed != record.hash:
        _reject(
            "TAMPERED",
            "Evidence integrity check failed (hash mismatch). Tampered evidence is rejected.",
        )
    return record.to_dict()


def _bind_tenant(record_org: str | None, requested_org: str | None) -> str:
    if not record_org:
        _reject("MISSING", "Evidence has no tenant. Replay and prove fail closed.")
    if requested_org is not None and requested_org != record_org:
        _reject(
            "CROSS_TENANT",
            "Refusing to use this evidence: it belongs to a different tenant than --org. "
            "Cross-tenant replay and proof are forbidden.",
        )
    return record_org


def _records_from_document(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if "capsule_id" in payload and "digest" in payload:
        return _records_from_capsule(payload)
    if "bundle_digest" in payload and "records" in payload:
        return _records_from_bundle(payload)
    if "evidence_id" in payload or "decision" in payload:
        return [_verified_record(payload)]
    _reject(
        "INVALID",
        "Unrecognized evidence document. Expected an evidence record, an evidence bundle, "
        "or a capsule that embeds governance evidence.",
    )


def _records_from_bundle(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = verify_evidence_bundle(payload)
    if not result.valid:
        reason = result.failure_reason or "bundle verification failed"
        code = "TAMPERED" if "mismatch" in reason or "broken" in reason else "FORGED"
        if reason.startswith("malformed"):
            code = "INVALID"
        _reject(code, f"Evidence bundle rejected: {reason}.")
    raw_records = payload.get("records")
    if not isinstance(raw_records, list) or not raw_records:
        _reject("MISSING", "Evidence bundle contains no records.")
    verified: list[dict[str, Any]] = []
    bundle_org = payload.get("org_id")
    for raw in raw_records:
        if not isinstance(raw, dict):
            _reject("INVALID", "Evidence bundle records must be objects.")
        record = _verified_record(raw)
        if bundle_org and record.get("organization_id") != bundle_org:
            _reject(
                "FORGED",
                "Evidence bundle tenant does not match a record tenant. Forged evidence is rejected.",
            )
        verified.append(record)
    return verified


def _records_from_capsule(payload: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        capsule = SovereignCapsule.model_validate(payload)
    except (TypeError, ValueError) as exc:
        _reject("INVALID", f"Capsule could not be parsed ({exc}).")
    if not validate_capsule(capsule):
        _reject("TAMPERED", "Capsule digest mismatch. Tampered evidence is rejected.")
    embedded: list[dict[str, Any]] = []
    for source in (capsule.timeline, capsule.evidence_metadata):
        for item in source:
            if isinstance(item, dict) and item.get("evidence_id") and item.get("hash"):
                embedded.append(item)
    authority = capsule.authority_subset
    nested = authority.get("evidence") if isinstance(authority, dict) else None
    if isinstance(nested, dict) and nested.get("evidence_id"):
        embedded.append(nested)
    if not embedded:
        _reject(
            "MISSING",
            "Capsule digest is valid, but it contains no governance evidence to replay or prove. "
            "Export an evidence record or bundle. Nothing was executed.",
        )
    verified = [_verified_record(item) for item in embedded]
    for record in verified:
        if record.get("organization_id") != capsule.organization_id:
            _reject(
                "FORGED",
                "Capsule tenant does not match embedded evidence. Forged evidence is rejected.",
            )
    return verified


def _subject(record: dict[str, Any]) -> dict[str, Any]:
    authority: dict[str, Any] = {
        "authority_delegated_by": record.get("authority_delegated_by"),
    }
    if record.get("delegation_chain"):
        authority["delegation_chain"] = record["delegation_chain"]
    for key in ("approval_id", "execution_authorization_id", "policy_version", "authority_version"):
        if record.get(key) not in (None, "", []):
            authority[key] = record[key]
    subject: dict[str, Any] = {
        "evidence_id": record["evidence_id"],
        "organization_id": record["organization_id"],
        "identity_id": record["identity_id"],
        "decision": record["decision"],
        "action_id": record["action_id"],
        "action_type": record["action_type"],
        "authority": authority,
        "integrity": {
            "hash": record["hash"],
            "prev_hash": record.get("prev_hash"),
            "integrity_version": record.get("integrity_version"),
            "integrity_status": record.get("integrity_status"),
        },
        "timestamps": {"evaluated_at": record.get("evaluated_at")},
    }
    if record.get("recorded_at"):
        subject["timestamps"]["recorded_at"] = record["recorded_at"]
    return subject


def _prepare(payload: dict[str, Any], organization_id: str | None) -> list[dict[str, Any]]:
    records = _records_from_document(payload)
    bound: list[dict[str, Any]] = []
    for record in records:
        _bind_tenant(record.get("organization_id"), organization_id)
        bound.append(record)
    return bound


def replay_document(payload: dict[str, Any], *, organization_id: str | None) -> dict[str, Any]:
    """Reconstruct and explain evidence. ``executed`` is always false."""
    records = _prepare(payload, organization_id)
    subjects = [_subject(record) for record in records]
    explanations = []
    for subject in subjects:
        explanations.append(
            {
                "evidence_id": subject["evidence_id"],
                "summary": (
                    f"Decision {subject['decision']} for identity {subject['identity_id']} "
                    f"on {subject['action_type']} was reconstructed from hash "
                    f"{subject['integrity']['hash']}."
                ),
                "zero_effect": True,
            }
        )
    return {
        "operation": "replay",
        "disposition": "REPRODUCED",
        "zero_effect": True,
        "executed": False,
        "record_count": len(subjects),
        "organization_id": subjects[0]["organization_id"],
        "reconstruction": subjects,
        "explanation": explanations,
        "note": "Replay validated stored evidence. No tool, grant, or external effect was executed.",
    }


def prove_document(payload: dict[str, Any], *, organization_id: str | None) -> dict[str, Any]:
    """Export a verification artifact. Subject fields come only from verified evidence."""
    records = _prepare(payload, organization_id)
    subjects = [_subject(record) for record in records]
    return {
        "artifact_type": "whitepact.verification",
        "schema_version": "1.0.0",
        "disposition": "PROVED",
        "zero_effect": True,
        "executed": False,
        "generated_at": datetime.now(UTC).isoformat(),
        "verifier": {
            "product": "WhitePact",
            "protocol_version": PROTOCOL_VERSION,
            "sovereign_version": SOVEREIGN_VERSION,
        },
        "organization_id": subjects[0]["organization_id"],
        "record_count": len(subjects),
        "subjects": subjects,
        "note": "Proof packages verified evidence fields only. No evidence was invented or executed.",
    }
