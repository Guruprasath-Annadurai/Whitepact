# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Data Classification and Sensitivity Tier definitions for WhitePact Phase 5."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class DataClassification(StrEnum):
    PUBLIC = "PUBLIC"
    TENANT_OPERATIONAL = "TENANT_OPERATIONAL"
    PERSONAL = "PERSONAL"
    SENSITIVE_SECURITY = "SENSITIVE_SECURITY"
    CREDENTIAL_SECRET = "CREDENTIAL_SECRET"
    CANONICAL_SECURITY_EVIDENCE = "CANONICAL_SECURITY_EVIDENCE"
    DERIVED_CACHE = "DERIVED_CACHE"
    SYSTEM_METADATA = "SYSTEM_METADATA"
    UNCLASSIFIED = "UNCLASSIFIED"


class UnclassifiedTableError(Exception):
    """Raised when an unknown table lacks an explicit classification under fail-closed security."""


class SensitivityTier(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class TableClassification:
    table_name: str
    classification: DataClassification
    sensitivity: SensitivityTier
    retention_default: str
    exportable: bool
    erasable: bool


TABLE_CLASSIFICATIONS: dict[str, TableClassification] = {
    "audit_log": TableClassification("audit_log", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "credential_issuances": TableClassification("credential_issuances", DataClassification.SENSITIVE_SECURITY, SensitivityTier.HIGH, "ACTIVE_LIFETIME", False, True),
    "data_holds": TableClassification("data_holds", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.HIGH, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "data_lifecycle_requests": TableClassification("data_lifecycle_requests", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.HIGH, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "data_retention_policies": TableClassification("data_retention_policies", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "eval_baselines": TableClassification("eval_baselines", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "eval_runs": TableClassification("eval_runs", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_approval_votes": TableClassification("governance_approval_votes", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_approvals": TableClassification("governance_approvals", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_authority_passports": TableClassification("governance_authority_passports", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_consent_proofs": TableClassification("governance_consent_proofs", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_crypto_keys": TableClassification("governance_crypto_keys", DataClassification.CREDENTIAL_SECRET, SensitivityTier.CRITICAL, "KEY_LIFETIME", False, True),
    "governance_delegations": TableClassification("governance_delegations", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_evidence": TableClassification("governance_evidence", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_evidence_chain_heads": TableClassification("governance_evidence_chain_heads", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_execution_nonces": TableClassification("governance_execution_nonces", DataClassification.SENSITIVE_SECURITY, SensitivityTier.HIGH, "ACTIVE_LIFETIME", False, True),
    "governance_intent_contracts": TableClassification("governance_intent_contracts", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_neural_consent": TableClassification("governance_neural_consent", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.HIGH, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_neural_vault_index": TableClassification("governance_neural_vault_index", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_outcomes": TableClassification("governance_outcomes", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_policies": TableClassification("governance_policies", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_policy_activations": TableClassification("governance_policy_activations", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.HIGH, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_policy_revisions": TableClassification("governance_policy_revisions", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.HIGH, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_policy_versions": TableClassification("governance_policy_versions", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_revocation_epochs": TableClassification("governance_revocation_epochs", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "governance_root_authority_records": TableClassification("governance_root_authority_records", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "governance_workflow_rules": TableClassification("governance_workflow_rules", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "iam_api_key_lineage": TableClassification("iam_api_key_lineage", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "iam_break_glass_sessions": TableClassification("iam_break_glass_sessions", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "iam_four_eyes_requests": TableClassification("iam_four_eyes_requests", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "iam_jit_grants": TableClassification("iam_jit_grants", DataClassification.SENSITIVE_SECURITY, SensitivityTier.HIGH, "ACTIVE_LIFETIME", False, True),
    "iam_privileged_audit_log": TableClassification("iam_privileged_audit_log", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "iam_recovery_challenges": TableClassification("iam_recovery_challenges", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "iam_recovery_policies": TableClassification("iam_recovery_policies", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "iam_scim_groups": TableClassification("iam_scim_groups", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "iam_scim_users": TableClassification("iam_scim_users", DataClassification.PERSONAL, SensitivityTier.HIGH, "ACCOUNT_LIFETIME", True, True),
    "iam_sessions": TableClassification("iam_sessions", DataClassification.PERSONAL, SensitivityTier.CRITICAL, "SESSION_EXPIRY", False, True),
    "iam_step_up_nonces": TableClassification("iam_step_up_nonces", DataClassification.SENSITIVE_SECURITY, SensitivityTier.HIGH, "ACTIVE_LIFETIME", False, True),
    "incidents": TableClassification("incidents", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "leaderboard_models": TableClassification("leaderboard_models", DataClassification.PUBLIC, SensitivityTier.LOW, "INDEFINITE", True, False),
    "leaderboard_runs": TableClassification("leaderboard_runs", DataClassification.PUBLIC, SensitivityTier.LOW, "INDEFINITE", True, False),
    "mcp_tool_calls": TableClassification("mcp_tool_calls", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "oauth_auth_events": TableClassification("oauth_auth_events", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "oauth_authorization_codes": TableClassification("oauth_authorization_codes", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "oauth_authorization_requests": TableClassification("oauth_authorization_requests", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "oauth_clients": TableClassification("oauth_clients", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "oauth_credentials": TableClassification("oauth_credentials", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "oauth_flow_states": TableClassification("oauth_flow_states", DataClassification.PERSONAL, SensitivityTier.HIGH, "SESSION_EXPIRY", False, True),
    "org_api_key_metadata": TableClassification("org_api_key_metadata", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "org_api_keys": TableClassification("org_api_keys", DataClassification.SENSITIVE_SECURITY, SensitivityTier.CRITICAL, "ACTIVE_LIFETIME", False, True),
    "org_authority_ceilings": TableClassification("org_authority_ceilings", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "org_autonomy_budgets": TableClassification("org_autonomy_budgets", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "organizations": TableClassification("organizations", DataClassification.SYSTEM_METADATA, SensitivityTier.HIGH, "PERMANENT", False, False),
    "public_incident_reports": TableClassification("public_incident_reports", DataClassification.PUBLIC, SensitivityTier.LOW, "INDEFINITE", True, False),
    "restore_reconciliation_records": TableClassification("restore_reconciliation_records", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "SECURITY_EVIDENCE_DEFAULT", True, False),
    "paddle_webhook_events": TableClassification("paddle_webhook_events", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "stripe_webhook_events": TableClassification("stripe_webhook_events", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "tenant_tombstones": TableClassification("tenant_tombstones", DataClassification.CANONICAL_SECURITY_EVIDENCE, SensitivityTier.CRITICAL, "PERMANENT", True, False),
    "token_usage": TableClassification("token_usage", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "tool_trust_scores": TableClassification("tool_trust_scores", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_assertions": TableClassification("trust_fabric_assertions", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_authority_edges": TableClassification("trust_fabric_authority_edges", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_bootstrap_records": TableClassification("trust_fabric_bootstrap_records", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_challenges": TableClassification("trust_fabric_challenges", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_conflicts": TableClassification("trust_fabric_conflicts", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_federated_assertions": TableClassification("trust_fabric_federated_assertions", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_identifiers": TableClassification("trust_fabric_identifiers", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_passports": TableClassification("trust_fabric_passports", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_principals": TableClassification("trust_fabric_principals", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_relationships": TableClassification("trust_fabric_relationships", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_sources": TableClassification("trust_fabric_sources", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_fabric_trust_roots": TableClassification("trust_fabric_trust_roots", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_passports": TableClassification("trust_passports", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "trust_scores": TableClassification("trust_scores", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "upstream_mcp_servers": TableClassification("upstream_mcp_servers", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "verified_principals": TableClassification("verified_principals", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "web_identity_providers": TableClassification("web_identity_providers", DataClassification.PERSONAL, SensitivityTier.HIGH, "ACCOUNT_LIFETIME", True, True),
    "web_invitations": TableClassification("web_invitations", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "web_memberships": TableClassification("web_memberships", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "web_sessions": TableClassification("web_sessions", DataClassification.PERSONAL, SensitivityTier.CRITICAL, "SESSION_EXPIRY", False, True),
    "web_users": TableClassification("web_users", DataClassification.PERSONAL, SensitivityTier.HIGH, "ACCOUNT_LIFETIME", True, True),
    "web_verification_tokens": TableClassification("web_verification_tokens", DataClassification.PERSONAL, SensitivityTier.HIGH, "SESSION_EXPIRY", False, True),
    "webhook_configs": TableClassification("webhook_configs", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
    "webhook_deliveries": TableClassification("webhook_deliveries", DataClassification.TENANT_OPERATIONAL, SensitivityTier.MEDIUM, "90D_DEFAULT", True, True),
}


def classify_table(table_name: str, *, fail_closed: bool = True) -> TableClassification:
    """Return classification for a table.

    Under fail-closed semantics (default): raises UnclassifiedTableError or classifies
    as UNCLASSIFIED with exportable=False, erasable=False.
    """
    if table_name in TABLE_CLASSIFICATIONS:
        return TABLE_CLASSIFICATIONS[table_name]
    if fail_closed:
        raise UnclassifiedTableError(
            f"Table {table_name!r} is unclassified. Fail-closed policy prohibits export or erasure."
        )
    return TableClassification(
        table_name=table_name,
        classification=DataClassification.UNCLASSIFIED,
        sensitivity=SensitivityTier.CRITICAL,
        retention_default="SECURITY_EVIDENCE_DEFAULT",
        exportable=False,
        erasable=False,
    )
