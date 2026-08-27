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
from typing import Any

from sqlalchemy import func, insert, select

from responsibleai.db.engine import DatabaseEngine, governance_evidence
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.workflow import TimestampedAction

_GENESIS_HASH = "0" * 64


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _compute_entry_hash(prev_hash: str | None, record: dict[str, Any]) -> str:
    parts = [
        prev_hash or _GENESIS_HASH,
        record["id"],
        record["org_id"] or "",
        record["action_id"],
        record["decision"],
        record["evaluated_at"],
        record["recorded_at"],
    ]
    # Preserve verification of evidence written before Heart integration;
    # Heart-bound entries extend the material with both new digests.
    if record.get("authority_grant_digest") or record.get("legitimacy_digest"):
        parts.extend(
            [
                record.get("authority_grant_digest") or "",
                record.get("legitimacy_digest") or "",
            ]
        )
    material = "|".join(parts)
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
        authority_grant_digest=getattr(row, "authority_grant_digest", None),
        legitimacy_digest=getattr(row, "legitimacy_digest", None),
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
        self._chain_lock = asyncio.Lock()
        self._last_hash_by_org: dict[str | None, str | None] = {}
        self._hydrated_orgs: set[str | None] = set()

    async def _hydrate_chain(self, org_id: str | None) -> None:
        if org_id in self._hydrated_orgs:
            return
        org_filter = (
            governance_evidence.c.org_id.is_(None)
            if org_id is None
            else governance_evidence.c.org_id == org_id
        )
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence.c.entry_hash, governance_evidence.c.recorded_at)
                    .where(org_filter)
                    .order_by(governance_evidence.c.recorded_at.desc())
                    .limit(1)
                )
            ).fetchone()
        self._last_hash_by_org[org_id] = row.entry_hash if row else None
        self._hydrated_orgs.add(org_id)

    async def record(self, evidence: EvidenceRecord) -> EvidenceRecord:
        """Persist *evidence*, chaining it onto its organization's last
        entry. Mutates and returns *evidence* with `prev_hash`/`hash`
        filled in — the same object, for caller convenience, not a copy.
        """
        async with self._chain_lock:
            await self._hydrate_chain(evidence.organization_id)
            prev_hash = self._last_hash_by_org.get(evidence.organization_id)
            recorded_at = _now()
            hashable = {
                "id": evidence.evidence_id,
                "org_id": evidence.organization_id,
                "action_id": evidence.action_id,
                "decision": evidence.decision,
                "evaluated_at": evidence.evaluated_at.isoformat(),
                "recorded_at": recorded_at,
                "authority_grant_digest": evidence.authority_grant_digest,
                "legitimacy_digest": evidence.legitimacy_digest,
            }
            entry_hash = _compute_entry_hash(prev_hash, hashable)

            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(governance_evidence).values(
                        id=evidence.evidence_id,
                        org_id=evidence.organization_id,
                        action_id=evidence.action_id,
                        agent_id=evidence.agent_id,
                        identity_id=evidence.identity_id,
                        action_type=evidence.action_type,
                        target=evidence.target,
                        argument_keys=json.dumps(evidence.argument_keys),
                        authority_delegated_by=evidence.authority_delegated_by,
                        delegation_chain=json.dumps(evidence.delegation_chain)
                        if evidence.delegation_chain
                        else None,
                        risk_tier=evidence.risk_tier,
                        policy_version=evidence.policy_version,
                        authority_grant_digest=evidence.authority_grant_digest,
                        legitimacy_digest=evidence.legitimacy_digest,
                        decision=evidence.decision,
                        reason_codes=json.dumps(evidence.reason_codes),
                        framework=evidence.framework,
                        provider=evidence.provider,
                        model=evidence.model,
                        evaluated_at=evidence.evaluated_at.isoformat(),
                        recorded_at=recorded_at,
                        entry_hash=entry_hash,
                        prev_hash=prev_hash,
                    )
                )
            self._last_hash_by_org[evidence.organization_id] = entry_hash

        evidence.prev_hash = prev_hash
        evidence.hash = entry_hash
        evidence.recorded_at = recorded_at
        return evidence

    async def get(self, evidence_id: str) -> EvidenceRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence).where(governance_evidence.c.id == evidence_id)
                )
            ).fetchone()
        return _row_to_record(row) if row else None

    async def get_for_org(self, org_id: str, evidence_id: str) -> EvidenceRecord | None:
        """Return evidence only when it belongs to *org_id*."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_evidence)
                    .where(governance_evidence.c.id == evidence_id)
                    .where(governance_evidence.c.org_id == org_id)
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
        query = query.order_by(governance_evidence.c.recorded_at.asc()).limit(limit)
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
                    .order_by(governance_evidence.c.recorded_at.asc())
                )
            ).fetchall()

        expected_prev: str | None = None
        for row in rows:
            if row.prev_hash != expected_prev:
                return False
            hashable = {
                "id": row.id,
                "org_id": row.org_id,
                "action_id": row.action_id,
                "decision": row.decision,
                "evaluated_at": row.evaluated_at,
                "recorded_at": row.recorded_at,
            }
            recomputed = _compute_entry_hash(row.prev_hash, hashable)
            if recomputed != row.entry_hash:
                return False
            expected_prev = row.entry_hash
        return True
