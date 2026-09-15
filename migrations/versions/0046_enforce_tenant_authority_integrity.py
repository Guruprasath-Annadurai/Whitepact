# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enforce tenant-level relational authority and principal integrity.

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-15 00:00:00.000000

Remediates WP-PG-REV-01:
Enforces composite tenant-aware foreign keys so that an authority edge,
relationship, identifier, or trust root cannot reference a grantor,
grantee, subject, target, or principal belonging to a different tenant.
Fails closed with a clear diagnostic if historical corrupt rows are found.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0046"
down_revision: str | None = "0045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Integrity preflight: Fail closed if invalid cross-tenant authority data exists.
    # Check authority edges where grantor does not belong to the edge tenant.
    corrupt_grantors = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM trust_fabric_authority_edges e
            JOIN trust_fabric_principals p ON e.grantor_principal_id = p.id
            WHERE e.org_id != p.org_id
            """
        )
    ).scalar()
    if corrupt_grantors and corrupt_grantors > 0:
        raise RuntimeError(
            f"Migration 0046 aborted (FAIL CLOSED): Found {corrupt_grantors} cross-tenant authority edge(s) "
            "where grantor does not belong to the authority edge's tenant."
        )

    # Check authority edges where grantee does not belong to the edge tenant.
    corrupt_grantees = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM trust_fabric_authority_edges e
            JOIN trust_fabric_principals p ON e.grantee_principal_id = p.id
            WHERE e.org_id != p.org_id
            """
        )
    ).scalar()
    if corrupt_grantees and corrupt_grantees > 0:
        raise RuntimeError(
            f"Migration 0046 aborted (FAIL CLOSED): Found {corrupt_grantees} cross-tenant authority edge(s) "
            "where grantee does not belong to the authority edge's tenant."
        )

    # Check relationships where subject or target does not belong to relationship tenant.
    corrupt_relationships = bind.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM trust_fabric_relationships r
            JOIN trust_fabric_principals s ON r.subject_principal_id = s.id
            JOIN trust_fabric_principals t ON r.target_principal_id = t.id
            WHERE r.org_id != s.org_id OR r.org_id != t.org_id
            """
        )
    ).scalar()
    if corrupt_relationships and corrupt_relationships > 0:
        raise RuntimeError(
            f"Migration 0046 aborted (FAIL CLOSED): Found {corrupt_relationships} cross-tenant relationship(s)."
        )

    # 2. Add composite unique constraint on trust_fabric_principals(id, org_id)
    with op.batch_alter_table("trust_fabric_principals") as batch_op:
        batch_op.create_unique_constraint(
            "uq_tf_principals_id_org",
            ["id", "org_id"],
        )

    # 3. Add composite tenant-aware foreign keys to trust_fabric_authority_edges
    with op.batch_alter_table("trust_fabric_authority_edges") as batch_op:
        batch_op.create_foreign_key(
            "fk_tf_auth_grantor_tenant",
            "trust_fabric_principals",
            ["grantor_principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="RESTRICT",
        )
        batch_op.create_foreign_key(
            "fk_tf_auth_grantee_tenant",
            "trust_fabric_principals",
            ["grantee_principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="CASCADE",
        )

    # 4. Add composite tenant-aware foreign keys to trust_fabric_relationships
    with op.batch_alter_table("trust_fabric_relationships") as batch_op:
        batch_op.create_foreign_key(
            "fk_tf_rel_subject_tenant",
            "trust_fabric_principals",
            ["subject_principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_tf_rel_target_tenant",
            "trust_fabric_principals",
            ["target_principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="CASCADE",
        )

    # 5. Add composite tenant-aware foreign key to trust_fabric_identifiers
    with op.batch_alter_table("trust_fabric_identifiers") as batch_op:
        batch_op.create_foreign_key(
            "fk_tf_ident_principal_tenant",
            "trust_fabric_principals",
            ["principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="CASCADE",
        )

    # 6. Add composite tenant-aware foreign key to trust_fabric_trust_roots
    with op.batch_alter_table("trust_fabric_trust_roots") as batch_op:
        batch_op.create_foreign_key(
            "fk_tf_roots_principal_tenant",
            "trust_fabric_principals",
            ["root_principal_id", "org_id"],
            ["id", "org_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("trust_fabric_trust_roots") as batch_op:
        batch_op.drop_constraint("fk_tf_roots_principal_tenant", type_="foreignkey")
    with op.batch_alter_table("trust_fabric_identifiers") as batch_op:
        batch_op.drop_constraint("fk_tf_ident_principal_tenant", type_="foreignkey")
    with op.batch_alter_table("trust_fabric_relationships") as batch_op:
        batch_op.drop_constraint("fk_tf_rel_target_tenant", type_="foreignkey")
        batch_op.drop_constraint("fk_tf_rel_subject_tenant", type_="foreignkey")
    with op.batch_alter_table("trust_fabric_authority_edges") as batch_op:
        batch_op.drop_constraint("fk_tf_auth_grantee_tenant", type_="foreignkey")
        batch_op.drop_constraint("fk_tf_auth_grantor_tenant", type_="foreignkey")
    with op.batch_alter_table("trust_fabric_principals") as batch_op:
        batch_op.drop_constraint("uq_tf_principals_id_org", type_="unique")
