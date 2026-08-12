"""Add encrypted arguments to governance_approvals.

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-12 00:00:00.000000

Closes the resume-after-approval gap: an approved REQUIRE_APPROVAL
action previously had nothing to execute against later -- the original
arguments weren't persisted anywhere, by design, to avoid storing raw/
PII arguments unencrypted. This column stores them JSON-serialized
through EncryptedString (opt-in via RAI_FIELD_ENCRYPTION_KEY, see
db/encryption.py) -- application-layer only, so the migration itself
just adds a plain Text column, same pattern as every other
EncryptedString column in this schema (e.g. 0005/0010's ip_address/
reporter_name). See governance/approval.py's build_resume_action() and
mcp/governance_integration.py's resume_approval().
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_approvals",
        sa.Column("arguments", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("governance_approvals", "arguments")
