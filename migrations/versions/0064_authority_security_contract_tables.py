# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority M12-FS & M13 security contract tables.

Revision ID: 0064
Revises: 0063
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0064"
down_revision: str | None = "0063"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "authority_step_up_challenges",
        sa.Column("challenge_hash", sa.String(length=64), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("operation_digest", sa.String(length=64), nullable=False),
        sa.Column("rp_id", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=512), nullable=False),
        sa.Column("raw_challenge_b64", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_auth_stepup_user", "authority_step_up_challenges", ["user_id"])
    op.create_index("idx_auth_stepup_org", "authority_step_up_challenges", ["org_id"])
    op.create_index("idx_auth_stepup_digest", "authority_step_up_challenges", ["operation_digest"])

    op.create_table(
        "authority_containment_records",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("responder_user_id", sa.String(length=36), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=False),
        sa.Column("containment_action", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("revocation_epoch", sa.Integer(), nullable=False),
        sa.Column("evidence_id", sa.String(length=36), nullable=True),
        sa.Column("contained_at", sa.String(length=32), nullable=False),
    )
    op.create_index("idx_containment_org", "authority_containment_records", ["org_id"])
    op.create_index("idx_containment_target", "authority_containment_records", ["target_id"])

    op.create_table(
        "authority_recovery_requests",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("request_type", sa.String(length=32), nullable=False),
        sa.Column("target_root_id", sa.String(length=36), nullable=True),
        sa.Column("requester_user_id", sa.String(length=36), nullable=False),
        sa.Column("proposed_parameters_json", sa.Text(), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("required_quorum_m", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("eligible_quorum_n", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("executed_at", sa.String(length=32), nullable=True),
        sa.Column("executed_by_user_id", sa.String(length=36), nullable=True),
    )
    op.create_index("idx_rec_req_org", "authority_recovery_requests", ["org_id"])
    op.create_index("idx_rec_req_digest", "authority_recovery_requests", ["action_digest"])

    op.create_table(
        "authority_recovery_votes",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("authority_recovery_requests.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("voter_user_id", sa.String(length=36), nullable=False),
        sa.Column("decision", sa.String(length=20), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("voted_at", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("request_id", "voter_user_id", name="uq_rec_vote_request_voter"),
    )
    op.create_index("idx_rec_votes_req", "authority_recovery_votes", ["request_id"])

    op.add_column(
        "trust_fabric_bootstrap_records",
        sa.Column("require_passkey_stepup", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("trust_fabric_bootstrap_records", "require_passkey_stepup")
    op.drop_table("authority_recovery_votes")
    op.drop_table("authority_recovery_requests")
    op.drop_table("authority_containment_records")
    op.drop_table("authority_step_up_challenges")
