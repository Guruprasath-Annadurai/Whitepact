"""Async repository for persisted Trust Passports — the citable, verifiable
artifact behind the open Trust Index standard (compliance/TRUST_INDEX_SPEC.md).

Before this repository existed, `PassportGenerator.generate()` produced an
`AIPassport` object that was returned to one caller and then discarded —
`POST /api/evaluate` only ever exposed a truncated hash, never a real record
anyone else could look up. That made "cite your score" an empty claim: there
was nothing durable to point at. This repository is what makes
`GET /api/trust-index/verify/{id}` possible.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, trust_passports
from responsibleai.trust.passport import AIPassport


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PassportRepository:
    """Write and query persisted Trust Passports."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(
        self,
        passport: AIPassport,
        *,
        org_id: str | None,
        source: str,
    ) -> dict[str, Any]:
        dims = passport.trust_score
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(trust_passports).values(
                id=passport.passport_id,
                org_id=org_id,
                source=source,
                spec_version=passport.version,
                model_name=passport.model_name,
                provider=passport.provider,
                overall_score=dims.overall,
                grade=dims.grade,
                risk_level=dims.risk_level,
                fairness=dims.fairness, privacy=dims.privacy, security=dims.security,
                robustness=dims.robustness, compliance=dims.compliance, authenticity=dims.authenticity,
                bias_summary=json.dumps(passport.bias_summary),
                hallucination_summary=json.dumps(passport.hallucination_summary),
                security_summary=json.dumps(passport.security_summary),
                compliance_summary=json.dumps(passport.compliance_summary),
                privacy_summary=json.dumps(passport.privacy_summary),
                generated_at=passport.generated_at.isoformat(),
                verification_hash=passport.verification_hash,
                certified=0,
            ))
        return await self.get(passport.passport_id)  # type: ignore[return-value]

    async def get(self, passport_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(trust_passports).where(trust_passports.c.id == passport_id)
            )).fetchone()
        return self._row_to_dict(row) if row else None

    async def certify(self, passport_id: str, certified_by: str) -> dict[str, Any] | None:
        """Mark a passport as certified. Returns None if no such passport
        exists (caller should 404), otherwise the updated record."""
        existing = await self.get(passport_id)
        if existing is None:
            return None
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(trust_passports)
                .where(trust_passports.c.id == passport_id)
                .values(certified=1, certified_at=_now(), certified_by=certified_by)
            )
        return await self.get(passport_id)

    async def list_certified(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(
                select(trust_passports)
                .where(trust_passports.c.certified == 1)
                .order_by(trust_passports.c.certified_at.desc())
                .limit(limit)
                .offset(offset)
            )).fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(r: Any) -> dict[str, Any]:
        return {
            "passport_id": r.id,
            "org_id": r.org_id,
            "source": r.source,
            "spec_version": r.spec_version,
            "model": {"name": r.model_name, "provider": r.provider},
            "trust_score": {
                "overall": r.overall_score,
                "grade": r.grade,
                "risk_level": r.risk_level,
                "dimensions": {
                    "fairness": round(r.fairness * 100, 2), "privacy": round(r.privacy * 100, 2),
                    "security": round(r.security * 100, 2), "robustness": round(r.robustness * 100, 2),
                    "compliance": round(r.compliance * 100, 2), "authenticity": round(r.authenticity * 100, 2),
                },
            },
            "bias_summary": json.loads(r.bias_summary) if r.bias_summary else {},
            "hallucination_summary": json.loads(r.hallucination_summary) if r.hallucination_summary else {},
            "security_summary": json.loads(r.security_summary) if r.security_summary else {},
            "compliance_summary": json.loads(r.compliance_summary) if r.compliance_summary else {},
            "privacy_summary": json.loads(r.privacy_summary) if r.privacy_summary else {},
            "generated_at": r.generated_at,
            "verification_hash": r.verification_hash,
            "certified": bool(r.certified),
            "certified_at": r.certified_at,
            "certified_by": r.certified_by,
        }
