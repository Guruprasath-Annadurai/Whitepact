# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for persisted, hash-chained governance evidence
(SPEC.md Section 3.7, Phase 12). Same hash-chaining technique as
`public_incident_repository.py` and `audit_repository.py` — sha256 over
the previous entry's hash plus this entry's immutable fields — but
chained **per organization** rather than globally: each org's chain is
independently verifiable without needing any other org's records,
appropriate for evidence that's meant to be an org's own audit trail,
not a shared public registry.

Write-once: there is no `update`/`delete` here, deliberately — evidence
that could be edited after the fact isn't evidence.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.exc import IntegrityError, OperationalError

from responsibleai.db.engine import (
    DatabaseEngine,
    governance_evidence,
    governance_evidence_chain_heads,
)
from responsibleai.governance.evidence import EvidenceRecord, compute_canonical_evidence_hash
from responsibleai.governance.workflow import TimestampedAction

_GENESIS_HASH = "0" * 64


class ChainVerificationStatus(StrEnum):
    VALID = "VALID"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _compute_entry_hash(prev_hash: str | None, record: dict[str, Any]) -> str:
    if int(record.get("integrity_version") or 1) >= 2:
        return compute_canonical_evidence_hash(prev_hash, record)
    material = "|".join(
        [
            prev_hash or _GENESIS_HASH,
            record["id"],
            record["org_id"] or "",
            record["action_id"],
            record["decision"],
            record["evaluated_at"],
            record["recorded_at"],
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()


def _row_to_record(row: Any) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=row.id,
        organization_id=row.org_id,
        action_id=row.action_id,
        agent_id=row.agent_id,
        identity_id=row.identity_id,
        action_type=row.action_type,
        target=row.target,
        argument_keys=json.loads(row.argument_keys) if row.argument_keys else [],
        authority_delegated_by=row.authority_delegated_by,
        delegation_chain=json.loads(row.delegation_chain)
        if getattr(row, "delegation_chain", None)
        else [],
        risk_tier=row.risk_tier,
        policy_version=getattr(row, "policy_version", None),
        authentication_method=getattr(row, "authentication_method", None),
        request_fingerprint=getattr(row, "request_fingerprint", None),
        arguments_fingerprint=getattr(row, "arguments_fingerprint", None),
        purpose=getattr(row, "purpose", None),
        authority_version=getattr(row, "authority_version", None),
        consent_id=getattr(row, "consent_id", None),
        consent_version=getattr(row, "consent_version", None),
        consent_state=getattr(row, "consent_state", None),
        governance_epoch=getattr(row, "governance_epoch", None),
        approval_id=getattr(row, "approval_id", None),
        execution_authorization_id=getattr(row, "execution_authorization_id", None),
        execution_nonce_reference=getattr(row, "execution_nonce_reference", None),
        execution_target=getattr(row, "execution_target", None),
        integrity_version=getattr(row, "integrity_version", 1) or 1,
        integrity_status=getattr(row, "integrity_status", "LEGACY_CHAINED_V1"),
        chain_sequence=getattr(row, "chain_sequence", None),
        decision=row.decision,
        reason_codes=json.loads(row.reason_codes),
        framework=row.framework,
        provider=row.provider,
        model=row.model,
        evaluated_at=datetime.fromisoformat(row.evaluated_at),
        recorded_at=row.recorded_at,
        prev_hash=row.prev_hash,
        hash=row.entry_hash,
    )


class EvidenceRepository:
    """Write and query persisted governance evidence."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._chain_lock = asyncio.Lock()  # local contention reduction; DB is authoritative

    async def record(self, evidence: EvidenceRecord) -> EvidenceRecord:
        """Persist *evidence*, chaining it onto its organization's last
        entry. Mutates and returns *evidence* with `prev_hash`/`hash`
        filled in — the same object, for caller convenience, not a copy.
        """
        if evidence.organization_id is None:
            raise ValueError("Canonical evidence requires tenant ownership")
        for attempt in range(8):
            try:
                async with self._chain_lock, self._engine.raw.begin() as conn:
                    head = (
                        await conn.execute(
                            select(governance_evidence_chain_heads)
                            .where(
                                governance_evidence_chain_heads.c.org_id == evidence.organization_id
                            )
                            .with_for_update()
                        )
                    ).fetchone()
                    if head is None:
                        latest = (
                            await conn.execute(
                                select(governance_evidence.c.entry_hash)
                                .where(governance_evidence.c.org_id == evidence.organization_id)
                                .order_by(
                                    governance_evidence.c.recorded_at.desc(),
                                    governance_evidence.c.id.desc(),
                                )
                                .limit(1)
                            )
                        ).fetchone()
                        count = int(
                            (
                                await conn.execute(
                                    select(func.count())
                                    .select_from(governance_evidence)
                                    .where(governance_evidence.c.org_id == evidence.organization_id)
                                )
                            ).scalar()
                            or 0
                        )
                        await conn.execute(
                            insert(governance_evidence_chain_heads).values(
                                org_id=evidence.organization_id,
                                head_hash=latest.entry_hash if latest else None,
                                sequence=count,
                                updated_at=_now(),
                            )
                        )
                        prev_hash = latest.entry_hash if latest else None
                        sequence = count + 1
                    else:
                        prev_hash = head.head_hash
                        sequence = head.sequence + 1
                    recorded_at = _now()
                    values = {
                        "id": evidence.evidence_id,
                        "org_id": evidence.organization_id,
                        "action_id": evidence.action_id,
                        "agent_id": evidence.agent_id,
                        "identity_id": evidence.identity_id,
                        "action_type": evidence.action_type,
                        "target": evidence.target,
                        "argument_keys": json.dumps(evidence.argument_keys),
                        "authority_delegated_by": evidence.authority_delegated_by,
                        "delegation_chain": json.dumps(evidence.delegation_chain)
                        if evidence.delegation_chain
                        else None,
                        "risk_tier": evidence.risk_tier,
                        "policy_version": evidence.policy_version,
                        "authentication_method": evidence.authentication_method,
                        "request_fingerprint": evidence.request_fingerprint,
                        "arguments_fingerprint": evidence.arguments_fingerprint,
                        "purpose": evidence.purpose,
                        "authority_version": evidence.authority_version,
                        "consent_id": evidence.consent_id,
                        "consent_version": evidence.consent_version,
                        "consent_state": evidence.consent_state,
                        "governance_epoch": evidence.governance_epoch,
                        "approval_id": evidence.approval_id,
                        "execution_authorization_id": evidence.execution_authorization_id,
                        "execution_nonce_reference": evidence.execution_nonce_reference,
                        "execution_target": evidence.execution_target,
                        "integrity_version": 2,
                        "integrity_status": "CANONICAL_CHAINED",
                        "chain_sequence": sequence,
                        "decision": evidence.decision,
                        "reason_codes": json.dumps(evidence.reason_codes),
                        "framework": evidence.framework,
                        "provider": evidence.provider,
                        "model": evidence.model,
                        "evaluated_at": evidence.evaluated_at.isoformat(),
                        "recorded_at": recorded_at,
                        "prev_hash": prev_hash,
                    }
                    entry_hash = _compute_entry_hash(prev_hash, values)
                    values["entry_hash"] = entry_hash
                    await conn.execute(insert(governance_evidence).values(**values))
                    await conn.execute(
                        governance_evidence_chain_heads.update()
                        .where(governance_evidence_chain_heads.c.org_id == evidence.organization_id)
                        .values(head_hash=entry_hash, sequence=sequence, updated_at=recorded_at)
                    )
                evidence.prev_hash = prev_hash
                evidence.hash = entry_hash
                evidence.recorded_at = recorded_at
                evidence.chain_sequence = sequence
                evidence.integrity_version = 2
                evidence.integrity_status = "CANONICAL_CHAINED"
                return evidence
            except (IntegrityError, OperationalError):
                if attempt == 7:
                    raise
                await asyncio.sleep(0.01 * (attempt + 1))
        raise RuntimeError("Evidence append retry budget exhausted")

    async def get(self, evidence_id: str) -> EvidenceRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence).where(governance_evidence.c.id == evidence_id)
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def get_for_org(self, evidence_id: str, org_id: str) -> EvidenceRecord | None:
        """Tenant-scoped lookup for every externally reachable evidence API."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence).where(
                        governance_evidence.c.id == evidence_id,
                        governance_evidence.c.org_id == org_id,
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def get_latest_for_approval(self, org_id: str, approval_id: str) -> EvidenceRecord | None:
        """Latest persisted evidence row for one org-scoped approval, if any.

        Does not invent a record: returns None when this org has no evidence
        linked to *approval_id*.
        """
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence)
                    .where(
                        governance_evidence.c.org_id == org_id,
                        governance_evidence.c.approval_id == approval_id,
                    )
                    .order_by(governance_evidence.c.recorded_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def list_for_org(
        self,
        org_id: str | None,
        *,
        limit: int = 100,
        decision: str | None = None,
    ) -> list[EvidenceRecord]:
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        query = select(governance_evidence).where(org_filter)
        if decision is not None:
            query = query.where(governance_evidence.c.decision == decision)
        query = query.order_by(governance_evidence.c.recorded_at.desc()).limit(limit)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [_row_to_record(r) for r in rows]

    async def list_for_bundle(
        self,
        org_id: str | None,
        *,
        since: str | None = None,
        until: str | None = None,
        limit: int = 1000,
    ) -> list[EvidenceRecord]:
        """Chronological (ascending) slice of the org's evidence chain,
        for Evidence Bundle export (`governance/evidence_bundle.py`) --
        ascending order matches the actual chain-walk direction, unlike
        `list_for_org()`'s "most recent first" UI ordering. `since`/
        `until` are ISO-8601 `recorded_at` bounds, both optional and
        inclusive; omitting both exports the org's entire chain (up to
        `limit`)."""
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        query = select(governance_evidence).where(org_filter)
        if since is not None:
            query = query.where(governance_evidence.c.recorded_at >= since)
        if until is not None:
            query = query.where(governance_evidence.c.recorded_at <= until)
        query = query.order_by(
            func.coalesce(governance_evidence.c.chain_sequence, 0).asc(),
            governance_evidence.c.recorded_at.asc(),
            governance_evidence.c.id.asc(),
        ).limit(limit)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [_row_to_record(r) for r in rows]

    async def count_recent(
        self,
        org_id: str | None,
        agent_id: str,
        decision: str,
        *,
        since: str,
    ) -> int:
        """Count *decision*-outcome entries for *agent_id* recorded at or
        after *since* (an ISO-8601 timestamp) — the cross-request
        violation-pattern query `governance/quarantine.py` needs to
        actually produce `GovernanceDecision.QUARANTINE`, instead of it
        being a defined-but-unreachable enum member. A `COUNT(*)` query,
        not `list_for_org()` plus `len()`, so this stays cheap regardless
        of how much evidence history exists."""
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        query = (
            select(func.count())
            .select_from(governance_evidence)
            .where(org_filter)
            .where(governance_evidence.c.agent_id == agent_id)
            .where(governance_evidence.c.decision == decision)
            .where(governance_evidence.c.recorded_at >= since)
        )
        async with self._engine.raw.connect() as conn:
            result = (await conn.execute(query)).scalar()
        return int(result or 0)

    async def list_recent_actions(
        self,
        org_id: str | None,
        agent_id: str,
        *,
        since: str,
    ) -> list[TimestampedAction]:
        """*agent_id*'s action history at or after *since* (an ISO-8601
        timestamp), oldest first — the real source of
        ``governance.workflow.check_composition_violation()``'s
        ``recent_actions`` in the live MCP dispatch path
        (``mcp/governance_integration.py``). A plain ``(action_type,
        evaluated_at)`` projection, not a full ``list_for_org()``
        fetch — the composition check never needs the rest of an
        evidence row."""
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        query = (
            select(governance_evidence.c.action_type, governance_evidence.c.evaluated_at)
            .where(org_filter)
            .where(governance_evidence.c.agent_id == agent_id)
            .where(governance_evidence.c.evaluated_at >= since)
            .order_by(governance_evidence.c.evaluated_at.asc())
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(query)).fetchall()
        return [
            TimestampedAction(
                action_type=row.action_type, at=datetime.fromisoformat(row.evaluated_at)
            )
            for row in rows
        ]

    async def verify_chain(self, org_id: str | None) -> bool:
        """Re-walk *org_id*'s entire chain in insertion order and
        recompute every hash from scratch, comparing against what's
        stored. Returns False the moment any entry's hash, or the
        prev_hash link between consecutive entries, doesn't match --
        proof the record was edited or reordered after the fact, or
        that a hash was tampered with directly.
        """
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_evidence)
                    .where(org_filter)
                    .order_by(
                        func.coalesce(governance_evidence.c.chain_sequence, 0).asc(),
                        governance_evidence.c.recorded_at.asc(),
                        governance_evidence.c.id.asc(),
                    )
                )
            ).fetchall()

        expected_prev: str | None = None
        for expected_sequence, row in enumerate(rows, start=1):
            if row.prev_hash != expected_prev:
                return False
            hashable = dict(row._mapping)
            if (row.integrity_version or 1) >= 2:
                if row.chain_sequence != expected_sequence:
                    return False
            recomputed = _compute_entry_hash(row.prev_hash, hashable)
            if recomputed != row.entry_hash:
                return False
            expected_prev = row.entry_hash
        async with self._engine.raw.connect() as conn:
            head = (
                await conn.execute(
                    select(governance_evidence_chain_heads).where(
                        governance_evidence_chain_heads.c.org_id == org_id
                    )
                )
            ).fetchone()
        canonical_rows = [r for r in rows if (r.integrity_version or 1) >= 2]
        if head is not None:
            expected_head = rows[-1].entry_hash if rows else None
            if head.head_hash != expected_head or head.sequence != len(rows):
                return False
        elif canonical_rows:
            return False
        return True

    async def verify_chain_status(self, org_id: str) -> ChainVerificationStatus:
        """Return an honest tenant-chain verdict without conflating legacy proof."""
        try:
            if not await self.verify_chain(org_id):
                return ChainVerificationStatus.INVALID
            async with self._engine.raw.connect() as conn:
                legacy_count = int(
                    (
                        await conn.execute(
                            select(func.count())
                            .select_from(governance_evidence)
                            .where(
                                governance_evidence.c.org_id == org_id,
                                governance_evidence.c.integrity_version < 2,
                            )
                        )
                    ).scalar()
                    or 0
                )
            return (
                ChainVerificationStatus.INCOMPLETE
                if legacy_count
                else ChainVerificationStatus.VALID
            )
        except Exception:
            return ChainVerificationStatus.UNKNOWN

    async def get_chain_head(self, org_id: str) -> tuple[str | None, int] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence_chain_heads).where(
                        governance_evidence_chain_heads.c.org_id == org_id
                    )
                )
            ).fetchone()
        return (row.head_hash, row.sequence) if row else None
