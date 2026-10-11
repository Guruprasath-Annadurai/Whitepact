# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Append-only, hash-chained history of governance policy mutations.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_policy_history",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("rules_digest", sa.String(length=64), nullable=False),
        sa.Column("prev_entry_digest", sa.String(length=64), nullable=False),
        sa.Column("entry_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("org_id", "version", name="uq_policy_history_org_version"),
    )
    op.create_index("ix_governance_policy_history_org_id", "governance_policy_history", ["org_id"])
    _backfill_baselines()


def _loads(value: object) -> list[str] | None:
    return json.loads(str(value)) if value else None


def _backfill_baselines() -> None:
    """One baseline row per organization that already has a policy version.

    Without it, an organization edited before this migration would have a policy version of N and an
    empty history, which a verifier cannot tell apart from a deleted history. The baseline records the
    rules in force at migration time, attributed to ``system:migration``. The hashing below must stay
    identical to ``responsibleai.db.policy_repository`` (the test suite replays it).
    """
    bind = op.get_bind()
    orgs = bind.execute(
        sa.text("SELECT org_id, version FROM governance_policy_versions WHERE version > 0")
    ).fetchall()
    for org_id, version in orgs:
        rows = bind.execute(
            sa.text(
                "SELECT rule_id, reason_code, effect, risk_tiers, action_types, targets "
                "FROM governance_policies WHERE org_id = :o ORDER BY position ASC"
            ),
            {"o": org_id},
        ).fetchall()
        rules = [
            {
                "rule_id": r[0],
                "reason_code": r[1],
                "effect": r[2],
                "risk_tiers": sorted(_loads(r[3]) or []) or None,
                "action_types": sorted(_loads(r[4]) or []) or None,
                "targets": sorted(_loads(r[5]) or []) or None,
            }
            for r in rows
        ]
        rules_json = json.dumps(rules, sort_keys=True, separators=(",", ":"))
        rules_digest = hashlib.sha256(rules_json.encode("utf-8")).hexdigest()
        prev = "0" * 64
        created_at = datetime.now(UTC).isoformat()
        entry_digest = hashlib.sha256(
            "|".join(
                [
                    prev,
                    str(org_id),
                    str(version),
                    "baseline",
                    "",
                    "system",
                    "migration-0062",
                    rules_digest,
                    created_at,
                ]
            ).encode("utf-8")
        ).hexdigest()
        bind.execute(
            sa.text(
                "INSERT INTO governance_policy_history (id, org_id, version, change, rule_id, "
                "actor_type, actor_id, rules_json, rules_digest, prev_entry_digest, entry_digest, "
                "created_at) VALUES (:id, :o, :v, 'baseline', NULL, 'system', 'migration-0062', "
                ":rj, :rd, :prev, :ed, :ca)"
            ),
            {
                "id": str(uuid.uuid4()),
                "o": org_id,
                "v": version,
                "rj": rules_json,
                "rd": rules_digest,
                "prev": prev,
                "ed": entry_digest,
                "ca": created_at,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_governance_policy_history_org_id", table_name="governance_policy_history")
    op.drop_table("governance_policy_history")
