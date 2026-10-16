# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add require_passkey_stepup to trust_fabric_bootstrap_records.

Revision ID: 0065
Revises: 0064
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_RETENTION_TABLE = "_alembic_0065_downgrade_retention"


def upgrade() -> None:
    op.add_column(
        "trust_fabric_bootstrap_records",
        sa.Column("require_passkey_stepup", sa.Integer(), nullable=False, server_default="0"),
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _RETENTION_TABLE in inspector.get_table_names():
        # Restore mandatory passkey requirements preserved during a previous fail-closed downgrade
        if bind.dialect.name == "sqlite":
            bind.execute(
                sa.text(
                    f"UPDATE trust_fabric_bootstrap_records "
                    f"SET require_passkey_stepup = ("
                    f"  SELECT r.require_passkey_stepup FROM {_RETENTION_TABLE} r "
                    f"  WHERE r.id = trust_fabric_bootstrap_records.id"
                    f") "
                    f"WHERE id IN (SELECT id FROM {_RETENTION_TABLE})"
                )
            )
        else:
            bind.execute(
                sa.text(
                    f"UPDATE trust_fabric_bootstrap_records t "
                    f"SET require_passkey_stepup = r.require_passkey_stepup "
                    f"FROM {_RETENTION_TABLE} r "
                    f"WHERE t.id = r.id"
                )
            )
        op.drop_table(_RETENTION_TABLE)


def downgrade() -> None:
    """Refuse a schema that cannot express an existing mandatory passkey gate."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Serialize the check with all bootstrap writers and the following DDL.
        bind.execute(sa.text("LOCK TABLE trust_fabric_bootstrap_records IN ACCESS EXCLUSIVE MODE"))
    has_mandatory = bind.execute(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM trust_fabric_bootstrap_records WHERE require_passkey_stepup != 0)"
        )
    ).scalar()
    if has_mandatory:
        raise RuntimeError(
            "Cannot downgrade 0065: mandatory passkey requirements exist; retain revision 0065"
        )
    op.drop_column("trust_fabric_bootstrap_records", "require_passkey_stepup")
