# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Verified principal gate: identity and organization verification.

Revision ID: 0055
Revises: 0054
Create Date: 2026-09-19 00:00:00.000000

Identity verification is not execution authority. Raw identity documents
are not stored. Provider event IDs are unique for replay protection.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0055"
down_revision: str | None = "0054"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name != "sqlite"

    op.create_table(
        "identity_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "user_id",
            sa.String(length=36),
            sa.ForeignKey("web_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_reference_id", sa.String(length=128), nullable=True),
        sa.Column("legal_name_encrypted", sa.Text(), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("assurance_level", sa.String(length=32), nullable=True),
        sa.Column("review_status", sa.String(length=32), nullable=True),
        sa.Column("verified_at", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )
    op.create_index("idx_identity_verifications_user", "identity_verifications", ["user_id"])
    op.create_index(
        "idx_identity_verifications_provider_ref",
        "identity_verifications",
        ["provider", "provider_reference_id"],
    )

    op.create_table(
        "organization_verifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("legal_name", sa.String(length=300), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("registration_reference", sa.String(length=128), nullable=True),
        sa.Column(
            "accountable_owner_user_id",
            sa.String(length=36),
            sa.ForeignKey("web_users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(length=64), nullable=True),
        sa.Column("provider_reference_id", sa.String(length=128), nullable=True),
        sa.Column("verified_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "identity_provider_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=128), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("provider", "event_id", name="uq_identity_provider_event"),
    )

    if pg:
        op.create_check_constraint(
            "chk_identity_verification_status",
            "identity_verifications",
            "status IN ('UNVERIFIED','BASIC_VERIFIED','IDENTITY_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')",
        )
        op.create_check_constraint(
            "chk_org_verification_status",
            "organization_verifications",
            "status IN ('UNVERIFIED','DOMAIN_VERIFIED','ORGANIZATION_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')",
        )


def downgrade() -> None:
    op.drop_table("identity_provider_events")
    op.drop_table("organization_verifications")
    op.drop_table("identity_verifications")
