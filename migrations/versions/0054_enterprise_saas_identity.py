# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise SaaS Layer 1 identity, membership, environments, keys, service accounts.

Revision ID: 0054
Revises: 0053
Create Date: 2026-09-19 00:00:00.000000

Extends the canonical organizations tenant. Does not create a second
tenant model. Does not alter Phase 7A runtime tables. Does not open
Production Gate B.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "0054"
down_revision: str | None = "0053"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name != "sqlite"

    op.add_column(
        "organizations",
        sa.Column("workspace_kind", sa.String(length=20), nullable=False, server_default="ORGANIZATION"),
    )
    op.add_column("organizations", sa.Column("owner_user_id", sa.String(length=36), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("settings_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column("organizations", sa.Column("deactivated_at", sa.String(length=32), nullable=True))

    op.add_column(
        "web_users",
        sa.Column(
            "verification_status",
            sa.String(length=32),
            nullable=False,
            server_default="UNVERIFIED",
        ),
    )
    op.add_column("web_users", sa.Column("phone_verified_at", sa.String(length=32), nullable=True))
    op.add_column(
        "web_users",
        sa.Column("abuse_hold", sa.Integer(), nullable=False, server_default="0"),
    )

    op.add_column(
        "web_memberships",
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
    )
    op.add_column("web_memberships", sa.Column("invited_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("web_memberships", sa.Column("accepted_at", sa.String(length=32), nullable=True))
    op.add_column("web_memberships", sa.Column("revoked_at", sa.String(length=32), nullable=True))
    op.add_column("web_memberships", sa.Column("updated_at", sa.String(length=32), nullable=True))

    op.add_column("web_sessions", sa.Column("session_id", sa.String(length=36), nullable=True))
    op.create_index("uq_web_sessions_session_id", "web_sessions", ["session_id"], unique=True)

    op.add_column("org_api_keys", sa.Column("created_by_user_id", sa.String(length=36), nullable=True))
    op.add_column("org_api_keys", sa.Column("accountable_human_user_id", sa.String(length=36), nullable=True))
    op.add_column("org_api_keys", sa.Column("service_account_id", sa.String(length=36), nullable=True))
    op.add_column("org_api_keys", sa.Column("environment_id", sa.String(length=36), nullable=True))
    op.add_column(
        "org_api_keys",
        sa.Column("holder_kind", sa.String(length=32), nullable=False, server_default="human_key"),
    )
    op.add_column("org_api_keys", sa.Column("overlap_expires_at", sa.String(length=32), nullable=True))
    op.add_column("org_api_keys", sa.Column("revoked_at", sa.String(length=32), nullable=True))
    op.create_index("idx_oak_environment", "org_api_keys", ["environment_id"])
    op.create_index("idx_oak_service_account", "org_api_keys", ["service_account_id"])

    if pg:
        op.alter_column(
            "org_api_key_metadata",
            "environment",
            existing_type=sa.String(length=8),
            type_=sa.String(length=16),
            existing_nullable=False,
        )
        op.create_check_constraint(
            "chk_org_workspace_kind",
            "organizations",
            "workspace_kind IN ('ORGANIZATION','INDIVIDUAL')",
        )
        op.create_check_constraint(
            "chk_web_membership_status",
            "web_memberships",
            "status IN ('INVITED','ACTIVE','SUSPENDED','REVOKED')",
        )
        op.create_check_constraint(
            "chk_web_user_verification_status",
            "web_users",
            "verification_status IN ('UNVERIFIED','BASIC_VERIFIED','IDENTITY_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')",
        )

    op.create_table(
        "enterprise_environments",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.UniqueConstraint("org_id", "name", name="uq_enterprise_environment_org_name"),
    )
    op.create_index("idx_enterprise_env_org", "enterprise_environments", ["org_id"])
    if pg:
        op.create_check_constraint(
            "chk_enterprise_environment_type",
            "enterprise_environments",
            "type IN ('DEVELOPMENT','STAGING','PRODUCTION')",
        )
        op.create_check_constraint(
            "chk_enterprise_environment_status",
            "enterprise_environments",
            "status IN ('ACTIVE','DISABLED','DELETED')",
        )

    op.create_table(
        "enterprise_service_accounts",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="ACTIVE"),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column(
            "created_by_user_id",
            sa.String(length=36),
            sa.ForeignKey("web_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("revoked_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_enterprise_sa_org", "enterprise_service_accounts", ["org_id"])
    if pg:
        op.create_check_constraint(
            "chk_enterprise_sa_status",
            "enterprise_service_accounts",
            "status IN ('ACTIVE','DISABLED','REVOKED')",
        )
        op.create_check_constraint(
            "chk_enterprise_sa_not_owner",
            "enterprise_service_accounts",
            "role <> 'OWNER'",
        )

    op.create_table(
        "enterprise_service_account_environments",
        sa.Column(
            "service_account_id",
            sa.String(length=36),
            sa.ForeignKey("enterprise_service_accounts.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "environment_id",
            sa.String(length=36),
            sa.ForeignKey("enterprise_environments.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
    )

    op.create_table(
        "enterprise_security_audit",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("environment_id", sa.String(length=36), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("result", sa.String(length=24), nullable=False),
        sa.Column("timestamp", sa.String(length=32), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_enterprise_audit_org_ts", "enterprise_security_audit", ["org_id", "timestamp"])
    op.create_index("idx_enterprise_audit_action", "enterprise_security_audit", ["action"])

    op.create_table(
        "api_key_issuance_decisions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("principal_user_id", sa.String(length=36), nullable=True),
        sa.Column("environment_id", sa.String(length=36), nullable=True),
        sa.Column("allowed", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(length=64), nullable=False),
        sa.Column("requested_scopes", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )
    op.create_index("idx_api_key_issuance_org", "api_key_issuance_decisions", ["org_id"])

    bind.execute(
        sa.text(
            """
            UPDATE web_users
            SET verification_status = 'BASIC_VERIFIED'
            WHERE email_verified_at IS NOT NULL AND verification_status = 'UNVERIFIED'
            """
        )
    )

    now = datetime.now(UTC).isoformat()
    orgs = bind.execute(sa.text("SELECT id FROM organizations")).fetchall()
    for org in orgs:
        org_id = org[0]
        for env_type, env_name, meta in (
            ("DEVELOPMENT", "Development", {"stricter_defaults": False}),
            ("STAGING", "Staging", {"stricter_defaults": False}),
            ("PRODUCTION", "Production", {"stricter_defaults": True}),
        ):
            bind.execute(
                sa.text(
                    """
                    INSERT INTO enterprise_environments
                    (id, org_id, type, name, status, created_at, metadata_json)
                    VALUES (:id, :org_id, :type, :name, 'ACTIVE', :created_at, :metadata_json)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "org_id": org_id,
                    "type": env_type,
                    "name": env_name,
                    "created_at": now,
                    "metadata_json": json.dumps(meta),
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    pg = bind.dialect.name != "sqlite"
    op.drop_table("api_key_issuance_decisions")
    op.drop_table("enterprise_security_audit")
    op.drop_table("enterprise_service_account_environments")
    op.drop_table("enterprise_service_accounts")
    op.drop_table("enterprise_environments")
    op.drop_index("idx_oak_service_account", table_name="org_api_keys")
    op.drop_index("idx_oak_environment", table_name="org_api_keys")
    op.drop_column("org_api_keys", "revoked_at")
    op.drop_column("org_api_keys", "overlap_expires_at")
    op.drop_column("org_api_keys", "holder_kind")
    op.drop_column("org_api_keys", "environment_id")
    op.drop_column("org_api_keys", "service_account_id")
    op.drop_column("org_api_keys", "accountable_human_user_id")
    op.drop_column("org_api_keys", "created_by_user_id")
    op.drop_index("uq_web_sessions_session_id", table_name="web_sessions")
    op.drop_column("web_sessions", "session_id")
    op.drop_column("web_memberships", "updated_at")
    op.drop_column("web_memberships", "revoked_at")
    op.drop_column("web_memberships", "accepted_at")
    op.drop_column("web_memberships", "invited_by_user_id")
    op.drop_column("web_memberships", "status")
    op.drop_column("web_users", "abuse_hold")
    op.drop_column("web_users", "phone_verified_at")
    op.drop_column("web_users", "verification_status")
    op.drop_column("organizations", "deactivated_at")
    op.drop_column("organizations", "settings_json")
    op.drop_column("organizations", "owner_user_id")
    op.drop_column("organizations", "workspace_kind")
    if pg:
        op.alter_column(
            "org_api_key_metadata",
            "environment",
            existing_type=sa.String(length=16),
            type_=sa.String(length=8),
            existing_nullable=False,
        )
