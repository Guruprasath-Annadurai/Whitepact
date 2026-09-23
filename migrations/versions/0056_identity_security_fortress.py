# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise SaaS Layer 2 identity security fortress.

Revision ID: 0056
Revises: 0055
Create Date: 2026-09-19 00:00:00.000000

Authentication, session assurance, provider binding, and recovery state.
Does not grant execution authority. Does not alter Phase 7A tables.
Does not open Production Gate B.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0056"
down_revision: str | None = "0055"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "web_sessions",
        sa.Column("assurance_level", sa.String(length=32), nullable=False, server_default="PASSWORD"),
    )
    op.add_column(
        "web_sessions",
        sa.Column("auth_methods_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column("web_sessions", sa.Column("auth_time", sa.String(length=32), nullable=True))
    op.add_column(
        "web_sessions",
        sa.Column("phishing_resistant", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("web_sessions", sa.Column("ip_label", sa.String(length=64), nullable=True))
    op.add_column("web_sessions", sa.Column("user_agent", sa.String(length=512), nullable=True))
    op.add_column("web_sessions", sa.Column("last_step_up_at", sa.String(length=32), nullable=True))
    op.add_column("web_sessions", sa.Column("inactivity_expires_at", sa.String(length=32), nullable=True))
    op.add_column("web_sessions", sa.Column("rotated_from", sa.String(length=64), nullable=True))

    op.create_table(
        "webauthn_challenges",
        sa.Column("challenge_hash", sa.String(length=64), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("ceremony", sa.String(length=32), nullable=False),
        sa.Column("rp_id", sa.String(length=255), nullable=False),
        sa.Column("origin", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_webauthn_challenges_user", "webauthn_challenges", ["user_id"])
    op.create_index("idx_webauthn_challenges_expiry", "webauthn_challenges", ["expires_at"])

    op.create_table(
        "passkey_credentials",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("credential_id", sa.String(length=512), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("sign_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("rp_id", sa.String(length=255), nullable=False),
        sa.Column("transports_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("aaguid", sa.String(length=64), nullable=True),
        sa.Column("backup_eligible", sa.Integer(), nullable=True),
        sa.Column("backup_state", sa.Integer(), nullable=True),
        sa.Column("display_name", sa.String(length=200), nullable=False, server_default="Passkey"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("last_used_at", sa.String(length=32), nullable=True),
        sa.UniqueConstraint("rp_id", "credential_id", name="uq_passkey_rp_credential"),
    )
    op.create_index("idx_passkey_user", "passkey_credentials", ["user_id"])
    op.create_index("idx_passkey_credential", "passkey_credentials", ["credential_id"])

    op.create_table(
        "human_totp_factors",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("secret_encrypted", sa.Text(), nullable=False),
        sa.Column("pending_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("last_timestep", sa.Integer(), nullable=True),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("confirmed_at", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "recovery_code_hashes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("user_id", "code_hash", name="uq_recovery_code_user_hash"),
    )
    op.create_index("idx_recovery_codes_user", "recovery_code_hashes", ["user_id"])

    op.create_table(
        "account_recovery_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="RECOVERY_REQUESTED"),
        sa.Column("privileged", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_account_recovery_user", "account_recovery_requests", ["user_id"])

    op.create_table(
        "provider_identities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("hosted_domain", sa.String(length=255), nullable=True),
        sa.Column("account_kind", sa.String(length=32), nullable=False, server_default="PERSONAL"),
        sa.Column("email_at_link", sa.String(length=254), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("provider", "subject", "tenant_id", name="uq_provider_identity_subject"),
    )
    op.create_index("idx_provider_identities_user", "provider_identities", ["user_id"])

    op.create_table(
        "organization_idp_bindings",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("verified_domain", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("configured_by", sa.String(length=36), nullable=False),
        sa.Column("verified_at", sa.String(length=32), nullable=True),
        sa.Column("policy_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("org_id", "provider", name="uq_org_idp_provider"),
    )
    op.create_index("idx_org_idp_tenant", "organization_idp_bindings", ["provider", "tenant_id"])

    op.create_table(
        "organization_sso_configs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("protocol", sa.String(length=16), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=False),
        sa.Column("client_id", sa.String(length=255), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text(), nullable=True),
        sa.Column("discovery_url", sa.String(length=512), nullable=True),
        sa.Column("jwks_url", sa.String(length=512), nullable=True),
        sa.Column("redirect_uri", sa.String(length=512), nullable=False),
        sa.Column("enforcement", sa.String(length=32), nullable=False, server_default="SSO_OPTIONAL"),
        sa.Column("provisioning", sa.String(length=32), nullable=False, server_default="INVITE_ONLY"),
        sa.Column("idp_entity_id", sa.String(length=512), nullable=True),
        sa.Column("idp_sso_url", sa.String(length=512), nullable=True),
        sa.Column("idp_x509_cert", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "step_up_grants",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("grant_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("assurance_required", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_step_up_grants_session", "step_up_grants", ["session_id"])

    op.create_table(
        "auth_replay_records",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("replay_key", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("kind", "replay_key", name="uq_auth_replay_kind_key"),
    )

    op.create_table(
        "org_security_policies",
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("phishing_resistant_required", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("privileged_roles_json", sa.Text(), nullable=False, server_default='["OWNER","SECURITY_ADMIN"]'),
        sa.Column("sso_enforcement", sa.String(length=32), nullable=False, server_default="SSO_OPTIONAL"),
        sa.Column("dual_control_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("break_glass_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
        sa.Column("updated_by", sa.String(length=36), nullable=True),
    )

    op.create_table(
        "company_domain_challenges",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("method", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("verified_at", sa.String(length=32), nullable=True),
        sa.UniqueConstraint("org_id", "domain", "method", name="uq_company_domain_challenge"),
    )

    op.create_table(
        "identity_security_notifications",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_identity_security_notifications_user", "identity_security_notifications", ["user_id"])


def downgrade() -> None:
    op.drop_table("identity_security_notifications")
    op.drop_table("company_domain_challenges")
    op.drop_table("org_security_policies")
    op.drop_table("auth_replay_records")
    op.drop_table("step_up_grants")
    op.drop_table("organization_sso_configs")
    op.drop_table("organization_idp_bindings")
    op.drop_table("provider_identities")
    op.drop_table("account_recovery_requests")
    op.drop_table("recovery_code_hashes")
    op.drop_table("human_totp_factors")
    op.drop_table("passkey_credentials")
    op.drop_table("webauthn_challenges")
    op.drop_column("web_sessions", "rotated_from")
    op.drop_column("web_sessions", "inactivity_expires_at")
    op.drop_column("web_sessions", "last_step_up_at")
    op.drop_column("web_sessions", "user_agent")
    op.drop_column("web_sessions", "ip_label")
    op.drop_column("web_sessions", "phishing_resistant")
    op.drop_column("web_sessions", "auth_time")
    op.drop_column("web_sessions", "auth_methods_json")
    op.drop_column("web_sessions", "assurance_level")
