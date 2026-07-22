"""Async repository for the public AI Incident Database — a CVE-style,
crowd-reported, moderated registry of publicly disclosed AI failures across
any model or provider. Distinct from `IncidentRepository` (db/incident_repository.py),
which tracks a single org's own private operational incidents.

Lifecycle: anyone can submit a report (PENDING_REVIEW, not publicly visible).
A super-admin reviews it and either approves (assigns a public "RAI-YYYY-NNNN"
identifier, PUBLISHED) or rejects it (REJECTED, with a reason). Once
published, an entry's core disclosure facts (title, type, severity, affected
system) are hash-chained the same way `audit_repository.py` chains the audit
log — this detects a published record being quietly edited after the fact,
which is exactly the kind of tamper a CVE-style trust anchor has to resist.
Only the lifecycle `status` field (e.g. PUBLISHED -> RESOLVED) can change
after publication; editing the disclosed facts themselves isn't supported in
this version — a stated limitation, not an oversight.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, or_, select, update

from responsibleai.db.engine import DatabaseEngine, public_incident_reports

_GENESIS_HASH = "0" * 64


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _compute_entry_hash(prev_hash: str, record: dict[str, Any]) -> str:
    material = "|".join([
        prev_hash,
        record["public_id"],
        record["title"],
        record["incident_type"],
        record["severity"],
        record["affected_model"],
        record["affected_provider"],
        record["published_at"],
    ])
    return hashlib.sha256(material.encode()).hexdigest()


class PublicIncidentRepository:
    """Write and query the public AI Incident Database."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._chain_lock = asyncio.Lock()
        self._last_hash: str | None = None
        self._hydrated = False

    async def _hydrate_chain(self) -> None:
        if self._hydrated:
            return
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(public_incident_reports.c.entry_hash)
                .where(public_incident_reports.c.entry_hash.is_not(None))
                .order_by(public_incident_reports.c.published_at.desc())
                .limit(1)
            )).fetchone()
        self._last_hash = row.entry_hash if row else None
        self._hydrated = True

    # ── Submission ───────────────────────────────────────────────────────────

    async def submit(
        self,
        *,
        title: str,
        description: str,
        incident_type: str,
        severity: str,
        affected_model: str,
        affected_provider: str,
        affected_version: str | None = None,
        reporter_name: str | None = None,
        reporter_contact: str | None = None,
        evidence: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        internal_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(public_incident_reports).values(
                id=internal_id,
                status="PENDING_REVIEW",
                title=title,
                description=description,
                incident_type=incident_type,
                severity=severity,
                affected_model=affected_model,
                affected_provider=affected_provider,
                affected_version=affected_version,
                reporter_name=reporter_name,
                reporter_contact=reporter_contact,
                evidence=json.dumps(evidence or {}),
                tags=json.dumps(tags or []),
                submitted_at=_now(),
            ))
        return await self.get_by_internal_id(internal_id)  # type: ignore[return-value]

    # ── Lookup ───────────────────────────────────────────────────────────────

    async def get_by_internal_id(self, internal_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(public_incident_reports).where(public_incident_reports.c.id == internal_id)
            )).fetchone()
        return self._row_to_dict(row) if row else None

    async def get_by_public_id(
        self, public_id: str, *, redact_reporter: bool = True,
    ) -> dict[str, Any] | None:
        """Defaults to redacting reporter_contact — this is the lookup path
        the public detail page and API use. Admin call sites that genuinely
        need the contact (none currently do) can pass redact_reporter=False
        explicitly; the safe default protects against a future public call
        site forgetting to redact."""
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(public_incident_reports).where(public_incident_reports.c.public_id == public_id)
            )).fetchone()
        return self._row_to_dict(row, redact_reporter=redact_reporter) if row else None

    async def list_pending(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(
                select(public_incident_reports)
                .where(public_incident_reports.c.status == "PENDING_REVIEW")
                .order_by(public_incident_reports.c.submitted_at.asc())
                .limit(limit)
                .offset(offset)
            )).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def list_published(
        self,
        severity: str | None = None,
        incident_type: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(public_incident_reports)
            .where(public_incident_reports.c.status.in_(["PUBLISHED", "DISPUTED", "RESOLVED"]))
            .order_by(public_incident_reports.c.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if severity:
            stmt = stmt.where(public_incident_reports.c.severity == severity)
        if incident_type:
            stmt = stmt.where(public_incident_reports.c.incident_type == incident_type)
        if model:
            stmt = stmt.where(public_incident_reports.c.affected_model.ilike(f"%{model}%"))
        if provider:
            stmt = stmt.where(public_incident_reports.c.affected_provider.ilike(f"%{provider}%"))
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(
                public_incident_reports.c.title.ilike(like),
                public_incident_reports.c.description.ilike(like),
            ))
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._row_to_dict(r, redact_reporter=True) for r in rows]

    async def check(self, model: str, provider: str) -> list[dict[str, Any]]:
        """Exact-match (case-insensitive) lookup for the pre-deployment check
        product — 'has anything been reported against the model I'm about to
        deploy'. Deliberately exact, not fuzzy, so a caller gets a precise
        yes/no rather than noisy partial matches."""
        stmt = (
            select(public_incident_reports)
            .where(
                public_incident_reports.c.status.in_(["PUBLISHED", "DISPUTED", "RESOLVED"]),
                public_incident_reports.c.affected_model.ilike(model),
                public_incident_reports.c.affected_provider.ilike(provider),
            )
            .order_by(public_incident_reports.c.published_at.desc())
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._row_to_dict(r, redact_reporter=True) for r in rows]

    # ── Moderation ───────────────────────────────────────────────────────────

    async def approve(self, internal_id: str, reviewed_by: str) -> dict[str, Any] | None:
        existing = await self.get_by_internal_id(internal_id)
        if existing is None or existing["status"] != "PENDING_REVIEW":
            return None

        async with self._chain_lock:
            await self._hydrate_chain()
            public_id = await self._next_public_id()
            published_at = _now()
            prev_hash = self._last_hash or _GENESIS_HASH
            entry_hash = _compute_entry_hash(prev_hash, {
                "public_id": public_id,
                "title": existing["title"],
                "incident_type": existing["incident_type"],
                "severity": existing["severity"],
                "affected_model": existing["affected_model"],
                "affected_provider": existing["affected_provider"],
                "published_at": published_at,
            })

            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(public_incident_reports)
                    .where(public_incident_reports.c.id == internal_id)
                    .values(
                        status="PUBLISHED", public_id=public_id,
                        reviewed_at=published_at, reviewed_by=reviewed_by,
                        published_at=published_at,
                        entry_hash=entry_hash, prev_hash=prev_hash,
                    )
                )
            self._last_hash = entry_hash

        return await self.get_by_internal_id(internal_id)

    async def reject(self, internal_id: str, reviewed_by: str, reason: str) -> dict[str, Any] | None:
        existing = await self.get_by_internal_id(internal_id)
        if existing is None or existing["status"] != "PENDING_REVIEW":
            return None
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(public_incident_reports)
                .where(public_incident_reports.c.id == internal_id)
                .values(
                    status="REJECTED", reviewed_at=_now(), reviewed_by=reviewed_by,
                    rejection_reason=reason,
                )
            )
        return await self.get_by_internal_id(internal_id)

    async def update_status(
        self, public_id: str, new_status: str, reviewed_by: str,
    ) -> dict[str, Any] | None:
        """Post-publish lifecycle transition (e.g. PUBLISHED -> RESOLVED or
        -> DISPUTED). Never touches entry_hash/prev_hash — the disclosed
        facts stay locked; only the status changes."""
        existing = await self.get_by_public_id(public_id)
        if existing is None or existing["status"] not in ("PUBLISHED", "DISPUTED", "RESOLVED"):
            return None
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(public_incident_reports)
                .where(public_incident_reports.c.public_id == public_id)
                .values(status=new_status, reviewed_at=_now(), reviewed_by=reviewed_by)
            )
        return await self.get_by_public_id(public_id)

    # ── Integrity ────────────────────────────────────────────────────────────

    async def verify_chain(self) -> dict[str, Any]:
        """Recompute the hash chain over every published entry and report the
        first broken link, if any. Public, unlike the internal audit log's
        verify endpoint — the whole point of a CVE-style database is that
        anyone can check its integrity, not just the operator."""
        stmt = (
            select(public_incident_reports)
            .where(public_incident_reports.c.entry_hash.is_not(None))
            .order_by(public_incident_reports.c.published_at.asc())
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()

        broken_at: list[dict[str, Any]] = []
        expected_prev = _GENESIS_HASH
        checked = 0
        for r in rows:
            checked += 1
            recomputed = _compute_entry_hash(expected_prev, {
                "public_id": r.public_id, "title": r.title, "incident_type": r.incident_type,
                "severity": r.severity, "affected_model": r.affected_model,
                "affected_provider": r.affected_provider, "published_at": r.published_at,
            })
            if r.prev_hash != expected_prev or recomputed != r.entry_hash:
                broken_at.append({
                    "public_id": r.public_id,
                    "published_at": r.published_at,
                    "expected_prev_hash": expected_prev,
                    "stored_prev_hash": r.prev_hash,
                })
            expected_prev = r.entry_hash

        return {
            "intact": len(broken_at) == 0,
            "entries_checked": checked,
            "broken_links": broken_at,
        }

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _next_public_id(self) -> str:
        """Sequential per-year ID, e.g. RAI-2026-0001. Queried and assigned
        within the same chain-lock critical section as the hash chain update,
        so two concurrent approvals can't race onto the same ID — acceptable
        at the low approval volume a human-reviewed queue actually sees;
        not designed for high-concurrency bulk publishing."""
        year = datetime.now(UTC).year
        prefix = f"RAI-{year}-"
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(public_incident_reports.c.public_id)
                .where(public_incident_reports.c.public_id.like(f"{prefix}%"))
                .order_by(public_incident_reports.c.public_id.desc())
                .limit(1)
            )).fetchone()
        if row is None or row.public_id is None:
            next_seq = 1
        else:
            next_seq = int(row.public_id.removeprefix(prefix)) + 1
        return f"{prefix}{next_seq:04d}"

    @staticmethod
    def _row_to_dict(r: Any, redact_reporter: bool = False) -> dict[str, Any]:
        d = {
            "id": r.id,
            "public_id": r.public_id,
            "status": r.status,
            "title": r.title,
            "description": r.description,
            "incident_type": r.incident_type,
            "severity": r.severity,
            "affected_model": r.affected_model,
            "affected_provider": r.affected_provider,
            "affected_version": r.affected_version,
            "reporter_name": r.reporter_name,
            "evidence": json.loads(r.evidence) if r.evidence else {},
            "tags": json.loads(r.tags) if r.tags else [],
            "submitted_at": r.submitted_at,
            "reviewed_at": r.reviewed_at,
            "reviewed_by": r.reviewed_by,
            "rejection_reason": r.rejection_reason,
            "published_at": r.published_at,
            "entry_hash": r.entry_hash,
            "prev_hash": r.prev_hash,
        }
        if not redact_reporter:
            d["reporter_contact"] = r.reporter_contact
        return d
