# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only migration lineage validation; never infer or stamp a revision."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def _alembic_version_rows(connection: Connection) -> list[str]:
    return [
        str(version)
        for version in connection.execute(text("SELECT version_num FROM alembic_version"))
        .scalars()
        .all()
    ]


class SchemaLineageError(RuntimeError):
    """The stored revision does not establish a supported canonical schema."""


def validate_schema_lineage(connection: Connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names()) - {"sqlite_sequence"}
    if not tables or tables == {"alembic_version"}:
        if "alembic_version" not in tables:
            return
        rows = _alembic_version_rows(connection)
        if not rows:
            return
        raise SchemaLineageError(
            "Stored revision without canonical schema; preserve database and investigate"
        )
    if "alembic_version" not in tables:
        raise SchemaLineageError(
            "Refusing unversioned nonempty database; inventory schema before migration"
        )
    rows = _alembic_version_rows(connection)
    if len(rows) != 1 or not rows[0].isdigit():
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
        47: {
            "web_identity_providers",
            "web_invitations",
            "oauth_flow_states",
            "paddle_webhook_events",
        },
        50: {"runtime_execution_requests"},
        51: {"governance_execution_authorizations"},
        52: {"runtime_execution_attempts"},
        53: {
            "runtime_worker_leases",
            "runtime_execution_fences",
            "runtime_execution_dispatch_outbox",
        },
        54: {
            "enterprise_environments",
            "enterprise_service_accounts",
            "enterprise_service_account_environments",
            "enterprise_security_audit",
            "api_key_issuance_decisions",
        },
        55: {
            "identity_verifications",
            "organization_verifications",
            "identity_provider_events",
        },
        56: {
            "webauthn_challenges",
            "passkey_credentials",
            "human_totp_factors",
            "recovery_code_hashes",
            "account_recovery_requests",
            "provider_identities",
            "organization_idp_bindings",
            "organization_sso_configs",
            "step_up_grants",
            "auth_replay_records",
            "org_security_policies",
            "company_domain_challenges",
            "identity_security_notifications",
        },
        57: {
            "identity_oauth_transactions",
            "identity_rate_counters",
            "identity_four_eyes_requests",
        },
        58: {
            "dashboard_saml_transactions",
        },
        60: {
            "test_consequential_counters",
            "sovereign_shadow_observations",
        },
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
    if "governance_approvals" in tables:
        approval_columns = {c["name"] for c in inspector.get_columns("governance_approvals")}
        bound_approval_columns = {
            "authentication_method",
            "revocation_epoch",
            "authority_version",
            "policy_version",
            "target_fingerprint",
        }
        if revision >= 41 and not bound_approval_columns <= approval_columns:
            raise SchemaLineageError("Canonical approval security-binding columns are missing")
        if revision < 41 and bound_approval_columns & approval_columns:
            raise SchemaLineageError(
                f"Unexpected future approval columns at revision {rows[0]}; "
                "no automatic stamping or repair"
            )
    if revision >= 31:
        cols = {c["name"] for c in inspector.get_columns("organizations")}
        if "provisioner_key_id" not in cols or (
            revision >= 32 and "subscription_status" not in cols
        ):
            raise SchemaLineageError("Canonical website organization columns are missing")
        if revision >= 47:
            expected_entitlement_cols = {
                "paddle_customer_id",
                "paddle_subscription_id",
                "entitlement_version",
                "entitlement_updated_at",
                "paddle_last_occurred_at",
            }
            if not expected_entitlement_cols <= cols:
                raise SchemaLineageError("Canonical entitlement columns are missing")
            if "iam_step_up_nonces" in tables:
                nonce_cols = {c["name"] for c in inspector.get_columns("iam_step_up_nonces")}
                if "session_id" not in nonce_cols:
                    raise SchemaLineageError("Canonical step-up session_id column is missing")
