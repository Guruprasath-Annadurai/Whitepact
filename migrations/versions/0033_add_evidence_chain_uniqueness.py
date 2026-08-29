"""Add uniqueness constraints preventing forked evidence hash chains.

Revision ID: 0033
Revises: 0032
Create Date: 2026-08-29 00:00:00.000000

Security Remediation Gap 5 (multi-instance sequencing safety):
db/evidence_repository.py's EvidenceRepository.record() previously
serialized writes only via a per-process asyncio.Lock and an
in-process _last_hash_by_org cache -- safe within one process, but two
concurrent replicas writing to the same org's chain could both read
the same "last hash" and each insert a row claiming it as prev_hash,
forking the chain. These two partial unique indexes turn that race
into a hard, detectable IntegrityError (the same "UNIQUE constraint
converts a race into a typed error, not silent corruption" pattern
governance/crypto/types.py's KeyVersionConflictError already
established for wrapped-key rotation) instead of a silent fork:

- idx_gev_chain_link: at most one row per (org_id, prev_hash) when
  prev_hash is set -- covers every non-genesis append, the
  high-volume case.
- idx_gev_chain_genesis: at most one row per org_id with prev_hash
  NULL -- covers the very first entry in an org's chain. Does not
  cover a race between two org_id=NULL ("no org") genesis entries,
  since standard SQL treats each NULL as distinct for uniqueness
  purposes -- an accepted, narrow gap: apply_governance() already
  asserts ctx.org_id is not None before any evidence write reaches
  this table on the live governed path, so an org_id=NULL evidence
  row does not occur there today.

New, additive indexes; nothing existing is touched or migrated.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "idx_gev_chain_link",
        "governance_evidence",
        ["org_id", "prev_hash"],
        unique=True,
        sqlite_where=sa.text("prev_hash IS NOT NULL"),
        postgresql_where=sa.text("prev_hash IS NOT NULL"),
    )
    op.create_index(
        "idx_gev_chain_genesis",
        "governance_evidence",
        ["org_id"],
        unique=True,
        sqlite_where=sa.text("prev_hash IS NULL"),
        postgresql_where=sa.text("prev_hash IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_gev_chain_genesis", table_name="governance_evidence")
    op.drop_index("idx_gev_chain_link", table_name="governance_evidence")
