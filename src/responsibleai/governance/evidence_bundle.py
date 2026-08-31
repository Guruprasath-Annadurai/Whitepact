# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence Bundle (v3 authority-layer work): a self-contained,
OFFLINE-verifiable export of an org's governance evidence chain (or a
scoped time-range slice of it) -- the actual deliverable an auditor,
regulator, or insurer wants, distinct from
``db/evidence_repository.py``'s ``verify_chain()`` (which requires
hitting the live system, a DB connection, and an org-scoped credential
every time someone wants to re-check it).

**Reuses the existing hash chain entirely** -- this module invents
nothing new about how individual entries are hashed
(``db/evidence_repository.py``'s ``_compute_entry_hash()``, duplicated
here byte-for-byte since a bundle must be verifiable without importing
the DB layer at all). What it adds is exactly one thing the live chain
doesn't have: a **bundle-level digest** over every included record's
own hash, in order -- so the export itself, as a single artifact
handed to a third party, is tamper-evident as a unit, not just
link-by-link.

**Honest scoping for a time-scoped bundle**: when a bundle covers less
than an org's entire chain, its first record's ``prev_hash`` points to
a record that ISN'T included in the export -- an external anchor, not
something the bundle alone can verify. ``verify_evidence_bundle()``
checks internal consistency from that anchor forward (every record's
``prev_hash`` matches the previous record's ``hash``) and does not
claim to prove the bundle connects all the way back to genesis; a
caller who needs that guarantee should export the full, unscoped chain
(omit ``since``/``until``) or separately confirm the anchor hash
against the live system's own ``verify_chain()``.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from responsibleai.governance.evidence import EvidenceRecord

_GENESIS_HASH = "0" * 64


def _compute_entry_hash(prev_hash: str | None, record: EvidenceRecord) -> str:
    """Identical formula to ``db/evidence_repository.py``'s
    ``_compute_entry_hash()``, deliberately duplicated (not imported)
    -- this module must stay independently verifiable from a bundle's
    own serialized data, with no DB-layer import at all."""
    material = "|".join(
        [
            prev_hash or _GENESIS_HASH,
            record.evidence_id,
            record.organization_id or "",
            record.action_id,
            record.decision,
            record.evaluated_at.isoformat(),
            record.recorded_at or "",
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _bundle_digest(records: tuple[EvidenceRecord, ...]) -> str:
    """Sha256 over every included record's own hash, in order -- a
    single digest that changes if any record is added, removed,
    reordered, or edited, without needing to re-walk the internal
    chain to notice."""
    material = "|".join(r.hash or "" for r in records)
    return hashlib.sha256(material.encode()).hexdigest()


@dataclass(frozen=True)
class EvidenceBundle:
    bundle_id: str
    org_id: str | None
    generated_at: datetime
    records: tuple[EvidenceRecord, ...]
    bundle_digest: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "org_id": self.org_id,
            "generated_at": self.generated_at.isoformat(),
            "record_count": len(self.records),
            "bundle_digest": self.bundle_digest,
            "records": [r.to_dict() for r in self.records],
        }


def build_evidence_bundle(
    records: list[EvidenceRecord],
    *,
    org_id: str | None,
    bundle_id: str | None = None,
) -> EvidenceBundle:
    """*records* must already be in chain (ascending, insertion) order
    -- ``EvidenceRepository.list_for_bundle()`` returns them that way.
    This function does not re-sort them; a caller passing records out
    of order will get a bundle whose internal ``prev_hash`` links
    don't verify, which is the correct, honest outcome (the bundle
    reflects what it was actually given)."""
    ordered = tuple(records)
    return EvidenceBundle(
        bundle_id=bundle_id or str(uuid.uuid4()),
        org_id=org_id,
        generated_at=datetime.now(UTC),
        records=ordered,
        bundle_digest=_bundle_digest(ordered),
    )


@dataclass(frozen=True)
class BundleVerificationResult:
    valid: bool
    chain_intact: bool
    digest_matches: bool
    failure_reason: str | None = None


def _record_from_dict(data: dict[str, Any]) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=data["evidence_id"],
        organization_id=data.get("organization_id"),
        action_id=data["action_id"],
        agent_id=data["agent_id"],
        identity_id=data["identity_id"],
        action_type=data["action_type"],
        target=data["target"],
        argument_keys=list(data.get("argument_keys") or []),
        authority_delegated_by=data["authority_delegated_by"],
        delegation_chain=list(data.get("delegation_chain") or []),
        risk_tier=data.get("risk_tier"),
        policy_version=data.get("policy_version"),
        decision=data["decision"],
        reason_codes=list(data.get("reason_codes") or []),
        framework=data.get("framework"),
        provider=data.get("provider"),
        model=data.get("model"),
        evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
        recorded_at=data.get("recorded_at"),
        prev_hash=data.get("prev_hash"),
        hash=data.get("hash"),
    )


def verify_evidence_bundle(bundle_dict: dict[str, Any]) -> BundleVerificationResult:
    """Verifies a bundle purely from its own serialized dict form (as
    produced by ``EvidenceBundle.to_dict()``, e.g. loaded straight from
    a downloaded JSON file) -- no DB access, no live
    ``EvidenceRepository``. This is the actual offline proof: a party
    who received ``bundle.json`` can run this against the file alone,
    with no WhitePact credential or network access at all.

    Checks, in order (first failure wins):
    1. Every record's ``prev_hash`` matches the previous record's
       ``hash`` (the first record's own ``prev_hash`` is accepted as
       the external anchor, not checked against anything -- see this
       module's docstring).
    2. Every record's ``hash`` matches what recomputing
       ``_compute_entry_hash()`` from its own fields produces.
    3. The bundle-level digest matches recomputing it over all
       (now-verified) record hashes.
    """
    try:
        records_data = bundle_dict.get("records", [])
        if not isinstance(records_data, list) or not all(
            isinstance(record, dict) for record in records_data
        ):
            raise TypeError("records must be a list of objects")
        records = [_record_from_dict(d) for d in records_data]
        declared_count = bundle_dict.get("record_count")
        if declared_count is not None and declared_count != len(records):
            return BundleVerificationResult(
                valid=False,
                chain_intact=False,
                digest_matches=False,
                failure_reason="record count mismatch",
            )
    except (AttributeError, KeyError, TypeError, ValueError) as exc:
        # Bundles are externally supplied serialized evidence. Malformed
        # structures must produce a deterministic invalid verdict rather
        # than leak parser exceptions into a verifier or API caller.
        return BundleVerificationResult(
            valid=False,
            chain_intact=False,
            digest_matches=False,
            failure_reason=f"malformed bundle: {exc}",
        )

    expected_prev: str | None = None
    for i, record in enumerate(records):
        if i > 0 and record.prev_hash != expected_prev:
            return BundleVerificationResult(
                valid=False,
                chain_intact=False,
                digest_matches=False,
                failure_reason=f"chain broken at record {i} ({record.evidence_id})",
            )
        recomputed = _compute_entry_hash(record.prev_hash, record)
        if recomputed != record.hash:
            return BundleVerificationResult(
                valid=False,
                chain_intact=False,
                digest_matches=False,
                failure_reason=f"hash mismatch at record {i} ({record.evidence_id})",
            )
        expected_prev = record.hash

    recomputed_digest = _bundle_digest(tuple(records))
    digest_matches = recomputed_digest == bundle_dict.get("bundle_digest")
    if not digest_matches:
        return BundleVerificationResult(
            valid=False,
            chain_intact=True,
            digest_matches=False,
            failure_reason="bundle digest mismatch",
        )

    return BundleVerificationResult(
        valid=True, chain_intact=True, digest_matches=True, failure_reason=None
    )
