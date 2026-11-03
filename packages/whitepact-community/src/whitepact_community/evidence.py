"""Local evidence records with deterministic hash chaining.

Persistence is in-process / optional file JSONL — no hosted DB and no
enterprise EvidenceRepository dependency.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from whitepact_community.models import ActionRequest, AuthorityGrant, DecisionResult


@dataclass
class EvidenceRecord:
    action_id: str
    agent_id: str
    identity_id: str
    action_type: str
    target: str
    argument_keys: list[str]
    authority_delegated_by: str
    decision: str
    reason_codes: list[str]
    evaluated_at: datetime
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str | None = None
    risk_tier: str | None = None
    policy_version: int | None = None
    prev_hash: str | None = None
    hash: str | None = None
    recorded_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "organization_id": self.organization_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "identity_id": self.identity_id,
            "action_type": self.action_type,
            "target": self.target,
            "argument_keys": self.argument_keys,
            "authority_delegated_by": self.authority_delegated_by,
            "risk_tier": self.risk_tier,
            "policy_version": self.policy_version,
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "evaluated_at": self.evaluated_at.isoformat(),
            "recorded_at": self.recorded_at,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


def build_evidence_record(
    action: ActionRequest,
    authority: AuthorityGrant,
    decision: DecisionResult,
) -> EvidenceRecord:
    return EvidenceRecord(
        action_id=action.action_id,
        agent_id=action.agent_id,
        identity_id=action.identity.identity_id,
        action_type=action.action_type,
        target=action.target,
        argument_keys=sorted(action.arguments.keys()),
        authority_delegated_by=authority.delegated_by,
        decision=decision.decision.value,
        reason_codes=list(decision.reason_codes),
        evaluated_at=decision.evaluated_at,
        organization_id=authority.organization_id or action.identity.org_id,
        risk_tier=decision.risk_tier.value if decision.risk_tier is not None else None,
        policy_version=decision.policy_version,
    )


def _compute_entry_hash(record: EvidenceRecord, prev_hash: str | None, recorded_at: str) -> str:
    material = {
        "evidence_id": record.evidence_id,
        "action_id": record.action_id,
        "decision": record.decision,
        "reason_codes": record.reason_codes,
        "argument_keys": record.argument_keys,
        "authority_delegated_by": record.authority_delegated_by,
        "evaluated_at": record.evaluated_at.isoformat(),
        "recorded_at": recorded_at,
        "prev_hash": prev_hash or "",
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


class LocalEvidenceStore:
    """In-memory hash-chained evidence with optional JSONL durability."""

    def __init__(self, path: Path | None = None) -> None:
        self._path = path
        self._records: list[EvidenceRecord] = []
        self._last_hash: str | None = None
        if path is not None and path.exists():
            self._load(path)

    def _load(self, path: Path) -> None:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            data = json.loads(line)
            record = EvidenceRecord(
                evidence_id=data["evidence_id"],
                organization_id=data.get("organization_id"),
                action_id=data["action_id"],
                agent_id=data["agent_id"],
                identity_id=data["identity_id"],
                action_type=data["action_type"],
                target=data["target"],
                argument_keys=list(data["argument_keys"]),
                authority_delegated_by=data["authority_delegated_by"],
                risk_tier=data.get("risk_tier"),
                policy_version=data.get("policy_version"),
                decision=data["decision"],
                reason_codes=list(data["reason_codes"]),
                evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
                recorded_at=data.get("recorded_at"),
                prev_hash=data.get("prev_hash"),
                hash=data.get("hash"),
            )
            self._records.append(record)
            self._last_hash = record.hash

    def record(self, evidence: EvidenceRecord) -> EvidenceRecord:
        recorded_at = datetime.now(UTC).isoformat()
        entry_hash = _compute_entry_hash(evidence, self._last_hash, recorded_at)
        evidence.prev_hash = self._last_hash
        evidence.hash = entry_hash
        evidence.recorded_at = recorded_at
        self._records.append(evidence)
        self._last_hash = entry_hash
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(evidence.to_dict(), sort_keys=True) + "\n")
        return evidence

    def verify_chain(self) -> bool:
        prev: str | None = None
        for record in self._records:
            if record.recorded_at is None or record.hash is None:
                return False
            if record.prev_hash != prev:
                return False
            expected = _compute_entry_hash(record, prev, record.recorded_at)
            if expected != record.hash:
                return False
            prev = record.hash
        return True

    @property
    def records(self) -> list[EvidenceRecord]:
        return list(self._records)
