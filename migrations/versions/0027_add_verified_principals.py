"""Add verified_principals table.

Revision ID: 0027
Revises: 0026
Create Date: 2026-08-20 00:00:00.000000

Authority Everywhere Phase 3 (Verified Principal): audit log of
non-human principals (service accounts, external attested agents)
authenticated via a Verifiable Credential (JWT-VC), separate from the
existing OIDC/SAML/API-key auth paths. See
governance/principal.py, auth/verifiable_credential.py, and
db/principal_repository.py. New, additive table; nothing existing is
touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "verified_principals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("principal_id", sa.String(255), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("credential_type", sa.String(128), nullable=False),
        sa.Column("holder_kind", sa.String(32), nullable=False),
        sa.Column("claim_keys", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_vp_principal", "verified_principals", ["principal_id"])
    op.create_index("idx_vp_org", "verified_principals", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_vp_org", table_name="verified_principals")
    op.drop_index("idx_vp_principal", table_name="verified_principals")
    op.drop_table("verified_principals")
