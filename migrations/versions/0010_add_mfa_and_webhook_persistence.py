"""Add TOTP MFA columns, persist webhook_configs, encrypt reporter_name.

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-23 00:00:00.000000

Three independent enterprise-hardening changes bundled into one migration
since they touch overlapping tables in the same area of the schema:

1. TOTP MFA (RFC 6238) — organizations.mfa_required (org-level enforcement
   toggle, same pattern as sso_required) and org_api_keys.mfa_secret /
   .mfa_enrolled / .mfa_backup_codes (per-key TOTP state). See
   responsibleai/auth/mfa.py and dashboard/app.py's /api/orgs/{id}/keys/{id}/mfa/*
   endpoints.

2. webhook_configs table — WebhookManager previously held registered
   webhooks only in an in-memory dict, so every registration vanished on
   restart. This table plus WebhookConfigRepository (db/webhook_repository.py)
   makes registrations durable across restarts, matching how
   webhook_deliveries already worked.

3. public_incident_reports.reporter_name widened to Text and switched to
   EncryptedString (opt-in via RAI_FIELD_ENCRYPTION_KEY, see db/encryption.py)
   — it's a person's name (PII) and was plaintext String(200); the other
   reporter field on this same table (reporter_contact) was already
   encrypted, so this closes an inconsistency, not a new decision.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column("mfa_required", sa.Integer, nullable=False, server_default="0")
        )

    with op.batch_alter_table("org_api_keys", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("mfa_secret", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("mfa_enrolled", sa.Integer, nullable=False, server_default="0")
        )
        batch_op.add_column(sa.Column("mfa_backup_codes", sa.Text(), nullable=True))

    with op.batch_alter_table("public_incident_reports", recreate="auto") as batch_op:
        batch_op.alter_column(
            "reporter_name",
            existing_type=sa.String(200),
            type_=sa.Text(),
            existing_nullable=True,
        )

    op.create_table(
        "webhook_configs",
        sa.Column("id",          sa.String(36),  nullable=False),
        sa.Column("org_id",      sa.String(36),  nullable=True),
        sa.Column("url",         sa.String(2048), nullable=False),
        sa.Column("provider",    sa.String(20),  nullable=False, server_default="generic"),
        sa.Column("events",      sa.Text(),      nullable=False),
        sa.Column("secret",      sa.Text(),      nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("enabled",     sa.Integer,     nullable=False, server_default="1"),
        sa.Column("max_retries", sa.Integer,     nullable=False, server_default="3"),
        sa.Column("created_at",  sa.String(32),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wc_org", "webhook_configs", ["org_id"])
    op.create_index("idx_wc_enabled", "webhook_configs", ["enabled"])


def downgrade() -> None:
    op.drop_index("idx_wc_enabled", table_name="webhook_configs")
    op.drop_index("idx_wc_org", table_name="webhook_configs")
    op.drop_table("webhook_configs")

    with op.batch_alter_table("public_incident_reports", recreate="auto") as batch_op:
        batch_op.alter_column(
            "reporter_name",
            existing_type=sa.Text(),
            type_=sa.String(200),
            existing_nullable=True,
        )

    with op.batch_alter_table("org_api_keys", recreate="auto") as batch_op:
        batch_op.drop_column("mfa_backup_codes")
        batch_op.drop_column("mfa_enrolled")
        batch_op.drop_column("mfa_secret")

    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.drop_column("mfa_required")
