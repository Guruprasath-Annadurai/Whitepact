# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only migration lineage validation; never infer or stamp a revision."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


class SchemaLineageError(RuntimeError):
    """The stored revision does not establish a supported canonical schema."""


def validate_schema_lineage(connection: Connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names()) - {"sqlite_sequence"}
    if not tables or tables == {"alembic_version"}:
        if "alembic_version" not in tables:
            return
        rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
        if not rows:
            return
        raise SchemaLineageError(
            "Stored revision without canonical schema; preserve database and investigate"
        )
    if "alembic_version" not in tables:
        raise SchemaLineageError(
            "Refusing unversioned nonempty database; inventory schema before migration"
        )
    rows = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if len(rows) != 1 or not isinstance(rows[0], str) or not rows[0].isdigit():
        raise SchemaLineageError("Refusing unversioned or ambiguous canonical migration lineage")
    revision = int(rows[0])
    requirements = {
        30: {
            "oauth_clients",
            "oauth_credentials",
            "oauth_authorization_codes",
            "oauth_authorization_requests",
            "oauth_auth_events",
        },
        31: {
            "web_users",
            "web_memberships",
            "web_sessions",
            "web_verification_tokens",
            "org_api_key_metadata",
        },
        32: {"stripe_webhook_events"},
        33: {"governance_crypto_keys"},
        34: {"governance_neural_consent", "governance_neural_vault_index"},
        35: {"governance_root_authority_records", "governance_consent_proofs"},
        38: {"governance_revocation_epochs"},
        39: {"governance_execution_nonces"},
    }
    for introduced, expected in requirements.items():
        if revision >= introduced and not expected <= tables:
            raise SchemaLineageError(
                f"Revision {rows[0]} does not match canonical schema; legacy transition requires explicit review"
            )
        if revision < introduced and expected & tables:
            raise SchemaLineageError(
                f"Unexpected future/legacy tables at revision {rows[0]}; no automatic stamping or repair"
            )
    if "organizations" not in tables:
        raise SchemaLineageError("Canonical organization table is missing")
    if revision >= 31:
        cols = {c["name"] for c in inspector.get_columns("organizations")}
        if "provisioner_key_id" not in cols or (
            revision >= 32 and "subscription_status" not in cols
        ):
            raise SchemaLineageError("Canonical website organization columns are missing")
