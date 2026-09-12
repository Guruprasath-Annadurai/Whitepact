# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM & Privileged Control Plane migration.

Creates:
- iam_step_up_nonces
- iam_sessions
- iam_api_key_lineage
- iam_scim_users
- iam_scim_groups
- iam_jit_grants
- iam_four_eyes_requests
- iam_break_glass_sessions
- iam_recovery_policies
- iam_recovery_challenges
- iam_privileged_audit_log
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0044"
down_revision: str | None = "0043"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. iam_step_up_nonces
    op.create_table(
        "iam_step_up_nonces",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("nonce_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_resource_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_nonce_hash", "iam_step_up_nonces", ["nonce_hash"])
    op.create_index("idx_iam_nonce_org_prin", "iam_step_up_nonces", ["org_id", "principal_id"])

    # 2. iam_sessions
    op.create_table(
        "iam_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("session_type", sa.String(32), nullable=False, server_default="INTERACTIVE"),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("last_seen_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_sess_token", "iam_sessions", ["token_hash"])
    op.create_index("idx_iam_sess_org_prin", "iam_sessions", ["org_id", "principal_id"])

    # 3. iam_api_key_lineage
    op.create_table(
        "iam_api_key_lineage",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("parent_key_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("scopes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_key_fprint", "iam_api_key_lineage", ["fingerprint"])
    op.create_index("idx_iam_key_org", "iam_api_key_lineage", ["org_id"])

    # 4. iam_scim_users
    op.create_table(
        "iam_scim_users",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("user_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("attributes_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_iam_scim_usr_org", "iam_scim_users", ["org_id"])
    op.create_index("idx_iam_scim_usr_ext", "iam_scim_users", ["org_id", "external_id"])
    op.create_index("idx_iam_scim_usr_name", "iam_scim_users", ["org_id", "user_name"])

    # 5. iam_scim_groups
    op.create_table(
        "iam_scim_groups",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("members_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_iam_scim_grp_org", "iam_scim_groups", ["org_id"])

    # 6. iam_jit_grants
    op.create_table(
        "iam_jit_grants",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("target_role", sa.String(32), nullable=False),
        sa.Column("allowed_actions_json", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="REQUESTED"),
        sa.Column("requested_at", sa.String(32), nullable=False),
        sa.Column("approved_at", sa.String(32), nullable=True),
        sa.Column("approver_principal_id", sa.String(64), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_jit_org_prin", "iam_jit_grants", ["org_id", "principal_id"])

    # 7. iam_four_eyes_requests
    op.create_table(
        "iam_four_eyes_requests",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("requester_principal_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_resource_id", sa.String(128), nullable=True),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("approver_principal_id", sa.String(64), nullable=True),
        sa.Column("approval_time", sa.String(32), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.String(32), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_iam_fe_org", "iam_four_eyes_requests", ["org_id"])
    op.create_index("idx_iam_fe_req", "iam_four_eyes_requests", ["requester_principal_id"])

    # 8. iam_break_glass_sessions
    op.create_table(
        "iam_break_glass_sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("incident_id", sa.String(64), nullable=False),
        sa.Column("capabilities_json", sa.Text(), nullable=False),
        sa.Column("justification", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("started_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("terminated_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_bg_org", "iam_break_glass_sessions", ["org_id"])
    op.create_index("idx_iam_bg_inc", "iam_break_glass_sessions", ["incident_id"])

    # 9. iam_recovery_policies
    op.create_table(
        "iam_recovery_policies",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("threshold", sa.Integer(), nullable=False),
        sa.Column("guardians_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("active", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("idx_iam_rec_pol_org", "iam_recovery_policies", ["org_id"])

    # 10. iam_recovery_challenges
    op.create_table(
        "iam_recovery_challenges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("new_root_principal_id", sa.String(64), nullable=False),
        sa.Column("new_root_public_key", sa.String(255), nullable=False),
        sa.Column("challenge_message", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("signatures_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_iam_chal_msg", "iam_recovery_challenges", ["challenge_message"])
    op.create_index("idx_iam_chal_org", "iam_recovery_challenges", ["org_id"])

    # 11. iam_privileged_audit_log
    op.create_table(
        "iam_privileged_audit_log",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(64), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("risk_tier", sa.String(32), nullable=False),
        sa.Column("allowed", sa.Integer(), nullable=False),
        sa.Column("target_resource_id", sa.String(128), nullable=True),
        sa.Column("recorded_at", sa.String(32), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_iam_audit_org", "iam_privileged_audit_log", ["org_id"])
    op.create_index("idx_iam_audit_ts", "iam_privileged_audit_log", ["recorded_at"])


def downgrade() -> None:
    op.drop_table("iam_privileged_audit_log")
    op.drop_table("iam_recovery_challenges")
    op.drop_table("iam_recovery_policies")
    op.drop_table("iam_break_glass_sessions")
    op.drop_table("iam_four_eyes_requests")
    op.drop_table("iam_jit_grants")
    op.drop_table("iam_scim_groups")
    op.drop_table("iam_scim_users")
    op.drop_table("iam_api_key_lineage")
    op.drop_table("iam_sessions")
    op.drop_table("iam_step_up_nonces")
