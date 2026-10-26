# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""One provider session reference can qualify only one verification row."""

from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_identity_verification_provider_session",
        "identity_verifications",
        ["provider", "provider_reference_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "uq_identity_verification_provider_session",
        table_name="identity_verifications",
    )
