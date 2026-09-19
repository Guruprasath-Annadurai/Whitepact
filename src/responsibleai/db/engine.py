# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async SQLAlchemy engine factory — SQLite for dev/test, PostgreSQL for production."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool

from responsibleai.db.encryption import EncryptedString

logger = logging.getLogger(__name__)

metadata = MetaData()

token_usage = Table(
    "token_usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("request_id", String(64), nullable=False, unique=True),
    Column("org_id", String(36), nullable=True),
    Column("provider", String(50), nullable=False),
    Column("model", String(100), nullable=False),
    Column("team", String(100), nullable=False, default="default"),
    Column("application", String(100), nullable=False, default="default"),
    Column("input_tokens", Integer, nullable=False),
    Column("output_tokens", Integer, nullable=False),
    Column("cached_tokens", Integer, nullable=False, default=0),
    Column("input_cost", Float, nullable=False, default=0.0),
    Column("output_cost", Float, nullable=False, default=0.0),
    Column("total_cost", Float, nullable=False, default=0.0),
    Column("prompt_hash", String(64), nullable=True),
    Column("metadata", Text, nullable=True),
    Column("recorded_at", String(32), nullable=False),
    Index("idx_tu_org", "org_id"),
    Index("idx_tu_provider", "provider"),
    Index("idx_tu_model", "model"),
    Index("idx_tu_team", "team"),
    Index("idx_tu_recorded", "recorded_at"),
)

trust_scores = Table(
    "trust_scores",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("org_id", String(36), nullable=True),
    Column("model_name", String(100), nullable=False),
    Column("provider", String(100), nullable=False),
    Column("overall", Float, nullable=False),
    Column("grade", String(2), nullable=False),
    Column("risk_level", String(20), nullable=False),
    Column("fairness", Float, nullable=False),
    Column("privacy", Float, nullable=False),
    Column("security", Float, nullable=False),
    Column("robustness", Float, nullable=False),
    Column("compliance", Float, nullable=False),
    Column("authenticity", Float, nullable=False),
    Column("metadata", Text, nullable=True),
    Column("recorded_at", String(32), nullable=False),
    Index("idx_ts_org", "org_id"),
    Index("idx_ts_model", "model_name"),
    Index("idx_ts_provider", "provider"),
    Index("idx_ts_recorded", "recorded_at"),
)

organizations = Table(
    "organizations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("name", String(200), nullable=False),
    Column("slug", String(100), nullable=False, unique=True),
    Column("monthly_budget_usd", Float, nullable=False, default=10_000.0),
    Column("created_at", String(32), nullable=False),
    Column("plan", String(20), nullable=False, default="FREE"),
    Column("stripe_customer_id", String(64), nullable=True),
    Column("stripe_subscription_id", String(64), nullable=True),
    Column("plan_renews_at", String(32), nullable=True),
    Column("subscription_status", String(32), nullable=False, default="inactive"),
    Column("governance_status", String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"),
    Column("sso_required", Integer, nullable=False, default=0),
    Column("mfa_required", Integer, nullable=False, default=0),
    Column("provisioner_key_id", String(64), nullable=True),
    Column("paddle_customer_id", String(64), nullable=True),
    Column("paddle_subscription_id", String(64), nullable=True),
    Column("entitlement_version", Integer, nullable=False, default=0),
    Column("entitlement_updated_at", String(32), nullable=True),
    Column("paddle_last_occurred_at", String(36), nullable=True),
    Column("workspace_kind", String(20), nullable=False, server_default="ORGANIZATION"),
    Column("owner_user_id", String(36), nullable=True),
    Column("settings_json", Text, nullable=False, server_default="{}"),
    Column("deactivated_at", String(32), nullable=True),
    Index("idx_org_slug", "slug"),
    Index("idx_org_stripe_customer", "stripe_customer_id"),
    Index("idx_org_paddle_customer", "paddle_customer_id", unique=True),
    Index("idx_org_paddle_subscription", "paddle_subscription_id", unique=True),
)

mcp_tool_calls = Table(
    "mcp_tool_calls",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=True),
    Column("tool_name", String(64), nullable=False),
    Column("tier", String(20), nullable=False),
    Column("timestamp", String(32), nullable=False),
    Column("allowed", Integer, nullable=False, default=1),
    Index("idx_mcp_calls_org", "org_id"),
    Index("idx_mcp_calls_ts", "timestamp"),
)

org_api_keys = Table(
    "org_api_keys",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("name", String(200), nullable=False),
    Column("role", String(20), nullable=False, default="ANALYST"),
    Column("created_at", String(32), nullable=False),
    Column("last_used_at", String(32), nullable=True),
    Column("revoked", Integer, nullable=False, default=0),
    # TOTP MFA (RFC 6238) — see auth/mfa.py. mfa_secret is opt-in encrypted
    # (EncryptedString, see db/encryption.py); mfa_backup_codes is a JSON list
    # of SHA-256 hashes, each single-use. enrolled=0 until the first
    # verify() call succeeds, so a secret that was issued but never
    # confirmed can't silently gate login.
    Column("mfa_secret", EncryptedString(), nullable=True),
    Column("mfa_enrolled", Integer, nullable=False, default=0),
    Column("mfa_backup_codes", Text, nullable=True),
    Column("created_by_user_id", String(36), nullable=True),
    Column("accountable_human_user_id", String(36), nullable=True),
    Column("service_account_id", String(36), nullable=True),
    Column("environment_id", String(36), nullable=True),
    Column("holder_kind", String(32), nullable=False, server_default="human_key"),
    Column("overlap_expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_oak_org", "org_id"),
    Index("idx_oak_hash", "key_hash"),
    Index("idx_oak_environment", "environment_id"),
    Index("idx_oak_service_account", "service_account_id"),
)

# Human identities and browser sessions are intentionally separate from
# machine API keys. API keys authenticate workloads; these tables authenticate
# people and bind them to organizations through explicit memberships.
web_users = Table(
    "web_users",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(254), nullable=False, unique=True),
    Column("full_name", String(200), nullable=False),
    Column("password_hash", Text, nullable=False),
    Column("email_verified_at", String(32), nullable=True),
    Column("disabled", Integer, nullable=False, default=0),
    Column("verification_status", String(32), nullable=False, server_default="UNVERIFIED"),
    Column("phone_verified_at", String(32), nullable=True),
    Column("abuse_hold", Integer, nullable=False, server_default="0"),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_web_users_email", "email"),
)

web_memberships = Table(
    "web_memberships",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
    Column(
        "org_id", String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    ),
    Column("role", String(20), nullable=False),
    Column("status", String(20), nullable=False, server_default="ACTIVE"),
    Column("invited_by_user_id", String(36), nullable=True),
    Column("accepted_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("updated_at", String(32), nullable=True),
    Column("created_at", String(32), nullable=False),
    UniqueConstraint("user_id", "org_id", name="uq_web_membership_user_org"),
    Index("idx_web_memberships_user", "user_id"),
    Index("idx_web_memberships_org", "org_id"),
)

web_sessions = Table(
    "web_sessions",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("session_id", String(36), nullable=True, unique=True),
    Column("user_id", String(36), ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True),
    Column("csrf_hash", String(64), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("last_seen_at", String(32), nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
    Index("idx_web_sessions_user", "user_id"),
    Index("idx_web_sessions_expires", "expires_at"),
)

web_verification_tokens = Table(
    "web_verification_tokens",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("user_id", String(36), ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
    Column("purpose", String(32), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_web_verification_user", "user_id"),
    Index("idx_web_verification_expiry", "expires_at"),
)

web_identity_providers = Table(
    "web_identity_providers",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
    Column("issuer", String(512), nullable=False),
    Column("subject", String(255), nullable=False),
    Column("email_at_link", String(254), nullable=True),
    Column("created_at", String(32), nullable=False),
    UniqueConstraint("issuer", "subject", name="uq_web_identity_provider_subject"),
    Index("idx_web_identity_provider_user", "user_id"),
)

web_invitations = Table(
    "web_invitations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
    Column("email", String(254), nullable=False),
    Column("role", String(20), nullable=False),
    Column("invited_by_user_id", String(36), ForeignKey("web_users.id", ondelete="RESTRICT"), nullable=False),
    Column("accepted_by_user_id", String(36), ForeignKey("web_users.id", ondelete="SET NULL"), nullable=True),
    Column("status", String(24), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_web_invitations_org", "org_id"),
    Index("idx_web_invitations_email", "email"),
)

oauth_flow_states = Table(
    "oauth_flow_states",
    metadata,
    Column("state_hash", String(64), primary_key=True),
    Column("provider", String(64), nullable=False),
    Column("tenant_id", String(36), nullable=True),
    Column("session_id", String(64), nullable=True),
    Column("nonce", String(64), nullable=False),
    Column("pkce_verifier", String(128), nullable=True),
    Column("redirect_uri", String(512), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_oauth_flow_states_expiry", "expires_at"),
)

org_api_key_metadata = Table(
    "org_api_key_metadata",
    metadata,
    Column(
        "key_id", String(36), ForeignKey("org_api_keys.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("prefix", String(20), nullable=False),
    Column("environment", String(16), nullable=False),
    Column("scopes", Text, nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("rotated_from_id", String(36), nullable=True),
    Index("idx_api_key_metadata_prefix", "prefix"),
)

stripe_webhook_events = Table(
    "stripe_webhook_events",
    metadata,
    Column("event_id", String(255), primary_key=True),
    Column("event_type", String(100), nullable=False),
    Column(
        "org_id", String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    ),
    Column("status", String(24), nullable=False),
    Column("received_at", String(32), nullable=False),
    Column("processed_at", String(32), nullable=True),
    Column("last_error", Text, nullable=True),
    Index("idx_stripe_events_org", "org_id"),
    Index("idx_stripe_events_status", "status"),
)

paddle_webhook_events = Table(
    "paddle_webhook_events",
    metadata,
    Column("event_id", String(100), primary_key=True),
    Column("event_type", String(100), nullable=False),
    Column("occurred_at", String(36), nullable=True),
    Column("entity_id", String(100), nullable=True),
    Column("org_id", String(36), nullable=True),
    Column("payload_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False, default="processing"),
    Column("received_at", String(32), nullable=False),
    Column("processed_at", String(32), nullable=True),
    Column("last_error", Text, nullable=True),
    Index("idx_paddle_events_org", "org_id"),
)


audit_log = Table(
    "audit_log",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("timestamp", String(32), nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("key_id", String(36), nullable=True),
    Column("endpoint", String(256), nullable=False),
    Column("method", String(10), nullable=False),
    Column("status_code", Integer, nullable=True),
    # EncryptedString: opt-in via RAI_FIELD_ENCRYPTION_KEY (see db/encryption.py).
    # Stored as Text (not a fixed-width String) to fit Fernet ciphertext,
    # which is longer than a raw IP address — see migration 0005.
    Column("ip_address", EncryptedString(), nullable=True),
    Column("request_id", String(64), nullable=True),
    Column("duration_ms", Float, nullable=True),
    Column("user_agent", String(512), nullable=True),
    Column("entry_hash", String(64), nullable=True),
    Column("prev_hash", String(64), nullable=True),
    Index("idx_al_timestamp", "timestamp"),
    Index("idx_al_org", "org_id"),
    Index("idx_al_endpoint", "endpoint"),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("run_type", String(20), nullable=False),  # "comparison" | "benchmark" | "dataset_scan"
    Column("model", String(100), nullable=False),
    Column("provider", String(100), nullable=False, default=""),
    Column("suite", String(50), nullable=True),
    Column("org_id", String(36), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("payload", Text, nullable=False),  # JSON-serialised result dict
    Index("idx_er_model", "model"),
    Index("idx_er_run_type", "run_type"),
    Index("idx_er_created_at", "created_at"),
    Index("idx_er_org", "org_id"),
)

eval_baselines = Table(
    "eval_baselines",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("model", String(100), nullable=False),
    Column("suite", String(50), nullable=False),
    Column("metric", String(100), nullable=False),
    Column("score", Float, nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("updated_at", String(32), nullable=False),
    Index("idx_eb_model", "model"),
    Index("idx_eb_suite", "suite"),
    Index("idx_eb_org", "org_id"),
)

webhook_configs = Table(
    "webhook_configs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=True),  # null = legacy/dev flat-key registration
    Column("url", String(2048), nullable=False),
    Column("provider", String(20), nullable=False, default="generic"),
    Column("events", Text, nullable=False),  # JSON list of WebhookEvent values
    Column("secret", EncryptedString(), nullable=True),  # HMAC signing secret — opt-in encrypted
    Column("description", String(500), nullable=True),
    Column("enabled", Integer, nullable=False, default=1),
    Column("max_retries", Integer, nullable=False, default=3),
    Column("created_at", String(32), nullable=False),
    Index("idx_wc_org", "org_id"),
    Index("idx_wc_enabled", "enabled"),
)

webhook_deliveries = Table(
    "webhook_deliveries",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("webhook_id", String(36), nullable=False),
    Column("event", String(64), nullable=False),
    Column("payload", Text, nullable=False),  # JSON
    Column("status", String(20), nullable=False, default="pending"),
    Column("attempts", Integer, nullable=False, default=0),
    Column("max_retries", Integer, nullable=False, default=3),
    Column("status_code", Integer, nullable=True),
    Column("last_error", Text, nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("next_retry_at", String(32), nullable=True),
    Column("delivered_at", String(32), nullable=True),
    Index("idx_wd_webhook", "webhook_id"),
    Index("idx_wd_status", "status"),
    Index("idx_wd_retry", "next_retry_at"),
)

incidents = Table(
    "incidents",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("created_at", String(32), nullable=False),
    Column("org_id", String(36), nullable=True),
    # "manual" (POST /api/incidents) | "alertmanager" (POST /api/alerts/webhook) | "mcp_tool" (informational only, never persisted from there directly)
    Column("source", String(20), nullable=False, default="manual"),
    Column("incident_type", String(50), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("siem_event_type", String(50), nullable=False),
    Column("model_name", String(100), nullable=True),
    Column("provider", String(100), nullable=True),
    Column("description", Text, nullable=False),
    Column("evidence_hash", String(16), nullable=False),
    Column("evidence_keys", Text, nullable=True),  # JSON list
    Column("mitigated", Integer, nullable=False, default=0),
    Column("status", String(20), nullable=False, default="OPEN"),
    Column("sla_resolution_hours", Integer, nullable=False, default=24),
    Column(
        "raw_payload", Text, nullable=True
    ),  # JSON — original alert payload, for source=alertmanager
    Index("idx_inc_org", "org_id"),
    Index("idx_inc_created", "created_at"),
    Index("idx_inc_severity", "severity"),
    Index("idx_inc_status", "status"),
)

leaderboard_models = Table(
    "leaderboard_models",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("model", String(100), nullable=False),
    Column("provider", String(50), nullable=False),
    Column("display_name", String(150), nullable=True),
    Column(
        "adapter", String(20), nullable=False, default="mock"
    ),  # "openai"|"anthropic"|"google"|"mock"
    Column("active", Integer, nullable=False, default=1),
    Column("added_at", String(32), nullable=False),
    Index("idx_lbm_active", "active"),
    Index("idx_lbm_model_provider", "model", "provider", unique=True),
)

leaderboard_runs = Table(
    "leaderboard_runs",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("model", String(100), nullable=False),
    Column("provider", String(50), nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("methodology_version", String(20), nullable=False),
    Column("overall_score", Float, nullable=False),
    Column("grade", String(2), nullable=False),
    Column("risk_level", String(20), nullable=False),
    Column("fairness", Float, nullable=False),
    Column("privacy", Float, nullable=False),
    Column("security", Float, nullable=False),
    Column("robustness", Float, nullable=False),
    Column("compliance", Float, nullable=False),
    Column("authenticity", Float, nullable=False),
    Column("dimensions_live", Text, nullable=False),  # JSON: {dim: bool}
    Column("truthfulqa_accuracy", Float, nullable=False),
    Column("bbq_bias_rate", Float, nullable=False),
    Column("hellaswag_accuracy", Float, nullable=False),
    Column("security_score", Float, nullable=False),
    Column("privacy_pii_leak_rate", Float, nullable=False),
    Column("avg_hallucination_risk", Float, nullable=False),
    Column("sample_size", Integer, nullable=False),
    Column("findings", Text, nullable=False),  # JSON list — the paid diagnostic
    Index("idx_lbr_model_provider", "model", "provider"),
    Index("idx_lbr_created", "created_at"),
)

trust_passports = Table(
    "trust_passports",
    metadata,
    Column("id", String(36), primary_key=True),  # passport_id
    Column("org_id", String(36), nullable=True),  # null for public self-assessments
    Column("source", String(20), nullable=False),  # "evaluate" | "self_assessment"
    Column("spec_version", String(20), nullable=False),
    Column("model_name", String(100), nullable=False),
    Column("provider", String(100), nullable=False),
    Column("overall_score", Float, nullable=False),
    Column("grade", String(2), nullable=False),
    Column("risk_level", String(20), nullable=False),
    Column("fairness", Float, nullable=False),
    Column("privacy", Float, nullable=False),
    Column("security", Float, nullable=False),
    Column("robustness", Float, nullable=False),
    Column("compliance", Float, nullable=False),
    Column("authenticity", Float, nullable=False),
    Column("bias_summary", Text, nullable=True),  # JSON
    Column("hallucination_summary", Text, nullable=True),  # JSON
    Column("security_summary", Text, nullable=True),  # JSON
    Column("compliance_summary", Text, nullable=True),  # JSON
    Column("privacy_summary", Text, nullable=True),  # JSON
    Column("generated_at", String(32), nullable=False),
    Column("verification_hash", String(64), nullable=False),
    Column("certified", Integer, nullable=False, default=0),
    Column("certified_at", String(32), nullable=True),
    Column("certified_by", String(200), nullable=True),
    Index("idx_tp_org", "org_id"),
    Index("idx_tp_model", "model_name", "provider"),
    Index("idx_tp_certified", "certified"),
    Index("idx_tp_generated", "generated_at"),
)

public_incident_reports = Table(
    "public_incident_reports",
    metadata,
    Column("id", String(36), primary_key=True),  # internal ID, always present
    Column("public_id", String(20), nullable=True, unique=True),  # "RAI-YYYY-NNNN", set on publish
    Column("status", String(20), nullable=False, default="PENDING_REVIEW"),
    Column("title", String(300), nullable=False),
    Column("description", Text, nullable=False),
    Column("incident_type", String(50), nullable=False),
    Column("severity", String(20), nullable=False),
    Column("affected_model", String(100), nullable=False),
    Column("affected_provider", String(100), nullable=False),
    Column("affected_version", String(100), nullable=True),
    Column(
        "reporter_name", EncryptedString(), nullable=True
    ),  # null = anonymous; PII — opt-in encrypted
    Column(
        "reporter_contact", EncryptedString(), nullable=True
    ),  # PII — opt-in encrypted, never public
    Column("evidence", Text, nullable=True),  # JSON: {urls: [...], reproduction_steps: "..."}
    Column("tags", Text, nullable=True),  # JSON list
    Column("submitted_at", String(32), nullable=False),
    Column("reviewed_at", String(32), nullable=True),
    Column("reviewed_by", String(200), nullable=True),
    Column("rejection_reason", Text, nullable=True),
    Column("published_at", String(32), nullable=True),
    Column("entry_hash", String(64), nullable=True),
    Column("prev_hash", String(64), nullable=True),
    Index("idx_pir_status", "status"),
    Index("idx_pir_model", "affected_model", "affected_provider"),
    Index("idx_pir_severity", "severity"),
    Index("idx_pir_submitted", "submitted_at"),
    Index("idx_pir_published_at", "published_at"),
)

# Phase 12 (SPEC.md Section 3.7) — persisted, hash-chained
# GovernanceDecision evidence. Chained per-org (unlike
# public_incident_reports' single global chain above): each
# organization's evidence trail must be independently verifiable
# without needing knowledge of any other org's records. Never stores
# raw argument values -- argument_keys is field names only, see
# governance/evidence.py's module docstring for why.
governance_evidence = Table(
    "governance_evidence",
    metadata,
    Column("id", String(36), primary_key=True),  # evidence_id
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", name="fk_evidence_org", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action_id", String(36), nullable=False),
    Column("agent_id", String(36), nullable=False),
    Column("identity_id", String(200), nullable=False),
    Column("action_type", String(50), nullable=False),
    Column("target", String(200), nullable=False),
    Column("argument_keys", Text, nullable=True),  # JSON list of field names, never values
    Column("authority_delegated_by", String(200), nullable=False),
    # JSON list -- AuthorityContext.delegation_chain, empty for every
    # action that never set one (see governance/models.py's docstring).
    Column("delegation_chain", Text, nullable=True),
    Column("risk_tier", String(20), nullable=True),
    # NULL when no Policy reached evaluation for this action at all --
    # see governance/policy.py's Policy.version docstring.
    Column("policy_version", Integer, nullable=True),
    Column("policy_digest", String(64), nullable=True),
    Column("authentication_method", String(20), nullable=True),
    Column("request_fingerprint", String(64), nullable=True),
    Column("arguments_fingerprint", String(64), nullable=True),
    Column("purpose", Text, nullable=True),
    Column("authority_version", String(64), nullable=True),
    Column("consent_id", String(36), nullable=True),
    Column("consent_version", String(64), nullable=True),
    Column("consent_state", String(20), nullable=True),
    Column("governance_epoch", Integer, nullable=True),
    Column("approval_id", String(36), nullable=True),
    Column("execution_authorization_id", String(36), nullable=True),
    Column("execution_nonce_reference", String(64), nullable=True),
    Column("execution_target", String(200), nullable=True),
    Column("integrity_version", Integer, nullable=False, default=2),
    Column("integrity_status", String(32), nullable=False, default="CANONICAL_CHAINED"),
    Column("chain_sequence", Integer, nullable=True),
    Column("decision", String(30), nullable=False),
    Column("reason_codes", Text, nullable=False),  # JSON list
    Column("framework", String(50), nullable=True),
    Column("provider", String(50), nullable=True),
    Column("model", String(100), nullable=True),
    Column("evaluated_at", String(32), nullable=False),
    Column("recorded_at", String(32), nullable=False),
    Column("entry_hash", String(64), nullable=False),
    Column("prev_hash", String(64), nullable=True),
    Index("idx_gev_org", "org_id"),
    Index("idx_gev_action", "action_id"),
    Index("idx_gev_decision", "decision"),
    Index("idx_gev_recorded", "recorded_at"),
    UniqueConstraint("org_id", "chain_sequence", name="uq_gev_org_sequence"),
    Index(
        "idx_gev_chain_link",
        "org_id",
        "prev_hash",
        unique=True,
        sqlite_where=text("prev_hash IS NOT NULL"),
        postgresql_where=text("prev_hash IS NOT NULL"),
    ),
    Index(
        "idx_gev_chain_genesis",
        "org_id",
        unique=True,
        sqlite_where=text("prev_hash IS NULL"),
        postgresql_where=text("prev_hash IS NULL"),
    ),
)

governance_evidence_chain_heads = Table(
    "governance_evidence_chain_heads",
    metadata,
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", name="fk_evidence_head_org", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("head_hash", String(64), nullable=True),
    Column("sequence", Integer, nullable=False, default=0),
    Column("updated_at", String(32), nullable=False),
)

# Phase 11 — persisted GovernanceDecision.REQUIRE_APPROVAL requests,
# resolvable by a human/delegated authority. evidence_id links back to
# the governance_evidence row for the same action_id, when one was
# recorded for it (optional -- evidence recording and approval
# creation are independent operations, see db/approval_repository.py).
governance_approvals = Table(
    "governance_approvals",
    metadata,
    Column("id", String(36), primary_key=True),  # approval_id
    Column("org_id", String(36), nullable=True),
    Column("action_id", String(36), nullable=False),
    Column("evidence_id", String(36), nullable=True),
    Column("action_type", String(50), nullable=False),
    Column("target", String(200), nullable=False),
    # SHA-256 over action_type/target/arguments — what "this approval
    # matches this exact action" actually means. See
    # governance/approval.py's compute_action_digest()/matches_action().
    Column("action_digest", String(64), nullable=False, server_default=""),
    # The original action's arguments, JSON-serialized -- encrypted at
    # rest (EncryptedString, opt-in via RAI_FIELD_ENCRYPTION_KEY, see
    # db/encryption.py) since this is exactly the raw/PII-bearing
    # payload every other part of the governance pipeline deliberately
    # avoids persisting unencrypted. NULL for approvals created before
    # this column existed -- those can never be resumed (see
    # governance/approval.py's build_resume_action()), only
    # resolved/viewed, which was already all they supported.
    Column("arguments", EncryptedString(), nullable=True),
    Column("reason_codes", Text, nullable=False),  # JSON list
    Column("risk_tier", String(20), nullable=True),
    Column("status", String(20), nullable=False, default="PENDING"),
    Column("requested_by", String(200), nullable=True),
    Column("requested_at", String(32), nullable=False),
    # NULL = no expiry enforced (only true for rows persisted before
    # this column existed; every new approval always gets one — see
    # governance/approval.py's DEFAULT_APPROVAL_TTL_HOURS).
    Column("expires_at", String(32), nullable=True),
    # How many distinct APPROVED votes are needed before this approval
    # transitions out of PENDING -- see governance/approval.py's
    # required_approvals docstring for the risk-tier-based default and
    # db/approval_repository.py's resolve()/cast_vote() for the quorum
    # logic. 1 (the default) preserves the exact single-approver
    # behavior every approval had before this column existed.
    Column("required_approvals", Integer, nullable=False, server_default="1"),
    Column("resolved_by", String(200), nullable=True),
    Column("resolved_at", String(32), nullable=True),
    Column("resolution_notes", Text, nullable=True),
    Column("purpose", Text, nullable=True),
    Column("authentication_method", String(20), nullable=True),
    Column("revocation_epoch", Integer, nullable=True),
    Column("authority_version", String(64), nullable=True),
    Column("policy_version", Integer, nullable=True),
    Column("target_fingerprint", String(64), nullable=True),
    Index("idx_gap_org", "org_id"),
    Index("idx_gap_status", "status"),
    Index("idx_gap_requested", "requested_at"),
    Index("idx_gap_action", "action_id"),
)

# One row per (approval, resolver) -- the individual votes a quorum-N
# approval accumulates before the parent governance_approvals row
# transitions out of PENDING. A single-approver (required_approvals=1)
# approval also gets exactly one row here; the parent row's own
# resolved_by/resolved_at/resolution_notes columns still reflect the
# vote that actually closed it, so nothing reading only the parent row
# needs to change to keep working.
governance_approval_votes = Table(
    "governance_approval_votes",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("approval_id", String(36), nullable=False),
    Column("resolver_identity_id", String(200), nullable=False),
    Column("outcome", String(20), nullable=False),  # APPROVED | DENIED
    Column("notes", Text, nullable=True),
    Column("resolved_at", String(32), nullable=False),
    Index("idx_gapv_approval", "approval_id"),
    # A given identity may cast at most one vote per approval -- the
    # replay/double-vote guard (db/approval_repository.py's
    # AlreadyVotedError), enforced at the DB layer, not just in
    # application code.
    UniqueConstraint("approval_id", "resolver_identity_id", name="uq_gapv_approval_resolver"),
)

# Phase 26 gap-closure — persisted governance policy rules (see
# db/policy_repository.py, governance/policy.py). One row per
# `PolicyRule`; `position` is the first-match-wins evaluation order
# within an org, since `Policy.evaluate()` has no other conflict
# resolution model. `risk_tiers`/`action_types`/`targets` are JSON lists
# or null (meaning "matches any"), mirroring `PolicyRule`'s own
# `frozenset | None` fields.
governance_policies = Table(
    "governance_policies",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("rule_id", String(100), nullable=False),
    Column("reason_code", String(100), nullable=False),
    Column("effect", String(30), nullable=False),
    Column("risk_tiers", Text, nullable=True),  # JSON list or null
    Column("action_types", Text, nullable=True),  # JSON list or null
    Column("targets", Text, nullable=True),  # JSON list or null
    Column("position", Integer, nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_gpol_org", "org_id"),
    Index("idx_gpol_position", "org_id", "position"),
)

# One row per org: a monotonically increasing counter bumped by
# PolicyRepository on every rule-set mutation (add/remove/reorder).
# Deliberately a separate table, not a column derived from MAX(rows'
# updated_at) or COUNT(rows) -- a removal must still advance the
# version (evidence recorded before the removal referenced a real,
# distinct rule set), which a row-count-based scheme would get wrong.
governance_policy_versions = Table(
    "governance_policy_versions",
    metadata,
    Column("org_id", String(36), primary_key=True),
    Column("version", Integer, nullable=False, default=0),
    Column("updated_at", String(32), nullable=False),
)

# One row per org: a structural ceiling no per-call `AuthorityContext`
# built for that org can ever exceed, enforced via
# `governance.validate_attenuation()` as the live `parent_authority` on
# every hosted MCP tool call (`mcp/governance_integration.py`). Unlike
# `governance_policies` (rule matching), this is the same fixed
# constraint shape `AuthorityContext.constraints` already recognizes --
# see `governance/ceiling.py`'s `OrgAuthorityCeiling.to_authority_context()`.
# All-null row (or no row at all) means "no ceiling configured" -- every
# org before this table existed behaves identically.

# v3 authority-layer work (Core Invariant #2, Delegation Graph): the
# actual persisted graph of who delegated authority to whom -- distinct
# from `AuthorityContext.delegation_chain` (an in-memory, per-call list).
# `from_identity_id` null means a root grant. Enables
# `DelegationRepository.get_authority_chain()`, `.explain_authority()`,
# and `.revoke_branch()` (cascading revocation).
governance_delegations = Table(
    "governance_delegations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("from_identity_id", String(200), nullable=True),
    Column("to_identity_id", String(200), nullable=False),
    Column("granted_action_types", Text, nullable=False),  # JSON list
    Column("constraints", Text, nullable=True),  # JSON dict or null
    Column("require_approval_for", Text, nullable=True),  # JSON list or null
    Column("purpose", Text, nullable=False),
    Column("granted_by", String(200), nullable=False),
    Column("granted_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("revoked_by", String(200), nullable=True),
    Column("revoke_reason", Text, nullable=True),
    Index("idx_gdel_org", "org_id"),
    Index("idx_gdel_to", "org_id", "to_identity_id"),
    Index("idx_gdel_from", "org_id", "from_identity_id"),
)

governance_workflow_rules = Table(
    "governance_workflow_rules",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("rule_id", String(100), nullable=False),
    Column("action_types", Text, nullable=False),  # JSON ordered list
    Column("window_minutes", Integer, nullable=False),
    Column("created_at", String(32), nullable=False),
    Index("idx_gwr_org", "org_id"),
)

org_authority_ceilings = Table(
    "org_authority_ceilings",
    metadata,
    Column("org_id", String(36), primary_key=True),
    Column("max_value_usd", Float, nullable=True),
    Column("allowed_targets", Text, nullable=True),  # JSON list or null
    Column("denied_targets", Text, nullable=True),  # JSON list or null
    Column("max_delegation_depth", Integer, nullable=True),
    Column("allowed_action_types", Text, nullable=True),  # JSON list or null; null = unrestricted
    Column("require_approval_for", Text, nullable=True),  # JSON list or null
    Column("updated_at", String(32), nullable=False),
)

# Autonomy Budget (v3 authority-layer work): one row per org, a rolling-
# window cap on how many ALLOW/ALLOW_WITH_REDACTION decisions a single
# identity may accrue before the next one is forced to REQUIRE_APPROVAL
# -- see governance/autonomy_budget.py's module docstring for why this
# is a distinct control from the quarantine circuit breaker (which
# reacts to bad outcomes, not volume). No row for an org means no
# budget configured -- every org before this table existed behaves
# identically (no cap).
org_autonomy_budgets = Table(
    "org_autonomy_budgets",
    metadata,
    Column("org_id", String(36), primary_key=True),
    Column("max_autonomous_actions", Integer, nullable=False),
    Column("window_minutes", Integer, nullable=False),
    Column("updated_at", String(32), nullable=False),
)

# The MCP Upstream Gateway's registry (v3 authority-layer work): one row
# per org-registered, SSRF-validated external MCP server. Registration
# is the approval step -- a call naming an unregistered/disabled/other-
# org's server_id is denied (ReasonCode.UNAPPROVED_MCP_SERVER) before
# any network connection is attempted. See governance/upstream.py and
# governance/upstream_executor.py.
upstream_mcp_servers = Table(
    "upstream_mcp_servers",
    metadata,
    Column("id", String(36), primary_key=True),  # server_id
    Column("org_id", String(36), nullable=False),
    Column("name", String(200), nullable=False),
    Column("url", String(2048), nullable=False),
    Column("enabled", Integer, nullable=False, server_default="1"),
    # Bearer credential for the upstream server itself -- opt-in
    # encrypted (EncryptedString, RAI_FIELD_ENCRYPTION_KEY), same
    # protection as every other credential column in this schema.
    Column("auth_token", EncryptedString(), nullable=True),
    Column("added_by", String(200), nullable=True),
    Column("created_at", String(32), nullable=False),
    Index("idx_ums_org", "org_id"),
)

# Tool Trust Network (Authority Everywhere Phase 8): one row per
# org-registered upstream MCP server, holding its current trust score
# and tier -- see governance/tool_trust.py for how the score is
# computed (from a supply-chain scan + incident history) and how an
# admin override is layered on top. No row for a server means it has
# never been scanned; governance/tool_trust.py's unscanned_score()
# defines what that server is treated as until a scan runs.
tool_trust_scores = Table(
    "tool_trust_scores",
    metadata,
    Column("server_id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("score", Integer, nullable=False),
    Column("tier", String(20), nullable=False),
    Column("has_been_scanned", Integer, nullable=False, server_default="0"),
    Column("incident_count", Integer, nullable=False, server_default="0"),
    Column("scan_report_id", String(36), nullable=True),
    Column("scan_summary", Text, nullable=True),
    Column("last_scanned_at", String(32), nullable=True),
    Column("admin_override_tier", String(20), nullable=True),
    Column("admin_override_by", String(200), nullable=True),
    Column("admin_override_reason", Text, nullable=True),
    Column("admin_override_at", String(32), nullable=True),
    Column("updated_at", String(32), nullable=False),
    Index("idx_tts_org", "org_id"),
)

# JIT Credential Broker (Authority Everywhere Phase 10): an audit trail
# of credential *issuance* events -- never the credential value itself.
# One row per JITCredential actually issued by
# governance/jit_credential.py's issue_jit_credential(), recorded by
# UpstreamMCPExecutor.execute() regardless of whether the proxied call
# that used it succeeded. See db/credential_issuance_repository.py.
credential_issuances = Table(
    "credential_issuances",
    metadata,
    Column("credential_id", String(36), primary_key=True),
    Column("authorization_id", String(36), nullable=False),
    Column("action_id", String(36), nullable=False),
    Column("server_id", String(36), nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("agent_id", String(200), nullable=True),
    Column("had_credential", Integer, nullable=False),  # server had a standing auth_token or not
    Column("issued_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_ci_org", "org_id"),
    Index("idx_ci_server", "server_id"),
)

# Outcome Observation (Authority Everywhere Phase 12): what actually
# happened when a governed action's permit was consumed, linked to the
# governance_evidence row that authorized the attempt. See
# governance/outcome.py and db/outcome_repository.py.
governance_outcomes = Table(
    "governance_outcomes",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("evidence_id", String(36), nullable=False),
    Column("action_id", String(36), nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("status", String(16), nullable=False),
    Column("result_summary", Text, nullable=True),
    Column("observed_at", String(32), nullable=False),
    Index("idx_go_evidence", "evidence_id"),
    Index("idx_go_org", "org_id"),
)

verified_principals = Table(
    "verified_principals",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("principal_id", String(255), nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("issuer", String(255), nullable=False),
    Column("credential_type", String(128), nullable=False),
    Column("holder_kind", String(32), nullable=False),
    Column("claim_keys", Text, nullable=False),
    Column("verified_at", String(32), nullable=False),
    Index("idx_vp_principal", "principal_id"),
    Index("idx_vp_org", "org_id"),
)

governance_intent_contracts = Table(
    "governance_intent_contracts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("agent_id", String(200), nullable=False),
    Column("goal", Text, nullable=False),
    Column("max_value_usd", Float, nullable=True),
    Column("allowed_targets", Text, nullable=True),  # JSON list or null
    Column("denied_targets", Text, nullable=True),  # JSON list or null
    Column("allowed_action_types", Text, nullable=True),  # JSON list or null
    Column("declared_at", String(32), nullable=False),
    Column("valid_from", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Index("idx_gic_org", "org_id"),
    Index("idx_gic_agent", "org_id", "agent_id"),
)

governance_authority_passports = Table(
    "governance_authority_passports",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False),
    Column("principal_id", String(200), nullable=False),
    Column("source", String(32), nullable=False),
    Column("source_id", String(200), nullable=False),
    Column("granted_action_types", Text, nullable=False),  # JSON list
    Column("max_value_usd", Float, nullable=True),
    Column("allowed_targets", Text, nullable=True),  # JSON list or null
    Column("denied_targets", Text, nullable=True),  # JSON list or null
    Column("require_approval_for", Text, nullable=True),  # JSON list or null
    Column("max_delegation_depth", Integer, nullable=True),
    Column("issued_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("revoked_by", String(200), nullable=True),
    Column("revoke_reason", Text, nullable=True),
    Index("idx_ap_org", "org_id"),
    Index("idx_ap_principal", "org_id", "principal_id"),
)

# OAuth 2.1 state for hosted MCP clients. Secrets (authorization codes,
# access tokens, refresh tokens, and pending-request handles) are represented
# only by SHA-256 digests. Raw values exist only in the response that creates
# them and are never persisted.
oauth_clients = Table(
    "oauth_clients",
    metadata,
    Column("client_id", String(80), primary_key=True),
    Column("client_name", String(200), nullable=False),
    Column("redirect_uris", Text, nullable=False),  # JSON list
    Column("created_at", String(32), nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
)

oauth_authorization_requests = Table(
    "oauth_authorization_requests",
    metadata,
    Column("request_hash", String(64), primary_key=True),
    Column("client_id", String(80), nullable=False),
    Column("redirect_uri", String(512), nullable=False),
    Column("state", String(512), nullable=False),
    Column("code_challenge", String(128), nullable=False),
    Column("scopes", Text, nullable=False),  # JSON list
    Column("resource", String(512), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("used", Integer, nullable=False, default=0),
    Index("idx_oar_client", "client_id"),
)

oauth_authorization_codes = Table(
    "oauth_authorization_codes",
    metadata,
    Column("code_hash", String(64), primary_key=True),
    Column("client_id", String(80), nullable=False),
    Column("redirect_uri", String(512), nullable=False),
    Column("code_challenge", String(128), nullable=False),
    Column("org_id", String(36), nullable=False),
    Column("subject_id", String(80), nullable=False),
    Column("role", String(20), nullable=False),
    Column("scopes", Text, nullable=False),
    Column("resource", String(512), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("used", Integer, nullable=False, default=0),
    Index("idx_oac_client", "client_id"),
)

oauth_credentials = Table(
    "oauth_credentials",
    metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("token_type", String(16), nullable=False),
    Column("family_id", String(80), nullable=False),
    Column("client_id", String(80), nullable=False),
    Column("org_id", String(36), nullable=False),
    Column("subject_id", String(80), nullable=False),
    Column("role", String(20), nullable=False),
    Column("scopes", Text, nullable=False),
    Column("resource", String(512), nullable=False),
    Column("issued_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_oc_family", "family_id"),
    Index("idx_oc_org", "org_id"),
    Index("idx_oc_subject", "subject_id"),
)

oauth_auth_events = Table(
    "oauth_auth_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("event_type", String(64), nullable=False),
    Column("outcome", String(16), nullable=False),
    Column("org_id", String(36), nullable=True),
    Column("subject_id", String(80), nullable=True),
    Column("client_id", String(80), nullable=True),
    Column("created_at", String(32), nullable=False),
    Index("idx_oae_created", "created_at"),
    Index("idx_oae_org", "org_id"),
)


governance_root_authority_records = Table(
    "governance_root_authority_records",
    metadata,
    Column("root_id", String(36), primary_key=True),
    Column("subject_id", String(255), nullable=False),
    Column("root_type", String(32), nullable=False),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("issuer", String(255), nullable=False),
    Column("verification_method", String(128), nullable=False),
    Column("authority_source", String(36), nullable=True),  # another root_id, or null
    Column("jurisdiction", String(64), nullable=True),
    Column("evidence_refs", Text, nullable=False),  # JSON list
    Column("issued_at", String(32), nullable=False),
    Column("not_before", String(32), nullable=True),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("revoked_by", String(200), nullable=True),
    Column("revoke_reason", Text, nullable=True),
    Column("canonical_digest", String(64), nullable=False),
    Index("idx_rar_subject", "subject_id"),
    Index("idx_rar_org", "organization_id"),
    Index("idx_rar_source", "authority_source"),
    UniqueConstraint("root_id", "organization_id", name="uq_root_tenant"),
    ForeignKeyConstraint(
        ["authority_source", "organization_id"],
        [
            "governance_root_authority_records.root_id",
            "governance_root_authority_records.organization_id",
        ],
        name="fk_root_parent_tenant",
        ondelete="RESTRICT",
    ),
)

governance_consent_proofs = Table(
    "governance_consent_proofs",
    metadata,
    Column("consent_id", String(36), primary_key=True),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("subject_id", String(255), nullable=False),
    Column("consenting_root_id", String(36), nullable=False),
    Column("grantee_id", String(200), nullable=False),
    Column("scope_description", Text, nullable=False),
    Column("purpose", Text, nullable=False),
    Column("consent_method", String(32), nullable=False),
    Column("allowed_action_types", Text, nullable=False, server_default="[]"),
    Column("allowed_targets", Text, nullable=False, server_default="[]"),
    Column("evidence_refs", Text, nullable=False),  # JSON list
    Column("consented_at", String(32), nullable=False),
    Column("not_before", String(32), nullable=True),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("revoked_by", String(200), nullable=True),
    Column("revoke_reason", Text, nullable=True),
    Column("canonical_digest", String(64), nullable=False),
    Index("idx_cp_grantee", "grantee_id"),
    Index("idx_cp_consenting_root", "consenting_root_id"),
    ForeignKeyConstraint(
        ["consenting_root_id", "organization_id"],
        [
            "governance_root_authority_records.root_id",
            "governance_root_authority_records.organization_id",
        ],
        name="fk_consent_root_tenant",
        ondelete="RESTRICT",
    ),
)

governance_revocation_epochs = Table(
    "governance_revocation_epochs",
    metadata,
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("scope", String(64), primary_key=True),
    Column("epoch", Integer, nullable=False, server_default="0"),
    Column("updated_at", String(32), nullable=False),
)

governance_execution_nonces = Table(
    "governance_execution_nonces",
    metadata,
    Column("nonce", String(64), primary_key=True),
    Column("authorization_id", String(36), nullable=False),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("consumed_at", String(32), nullable=False),
    Index("idx_execution_nonces_consumed_at", "consumed_at"),
)

governance_crypto_keys = Table(
    "governance_crypto_keys",
    metadata,
    Column("key_id", String(300), primary_key=True),
    Column("purpose", String(32), nullable=False),
    Column(
        "tenant_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False
    ),
    Column("environment", String(32), nullable=False),
    Column("version", Integer, nullable=False),
    Column("wrapped_dek", Text, nullable=False),  # base64, never plaintext DEK material
    Column("status", String(16), nullable=False),  # active | retired | revoked
    Column("created_at", String(32), nullable=False),
    Index(
        "idx_crypto_keys_lookup",
        "purpose",
        "tenant_id",
        "environment",
        "status",
        "version",
    ),
)

governance_neural_consent = Table(
    "governance_neural_consent",
    metadata,
    Column("consent_id", String(64), primary_key=True),
    Column("subject_id", String(200), nullable=False),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("category", String(32), nullable=False),
    Column("status", String(16), nullable=False),
    Column("version", Integer, nullable=False),
    Column("granted_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_neural_consent_subject_category", "subject_id", "category"),
)

governance_neural_vault_index = Table(
    "governance_neural_vault_index",
    metadata,
    Column("entry_id", String(64), primary_key=True),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("subject_id", String(200), nullable=False),
    Column("session_id", String(200), nullable=False),
    Column("data_class", String(32), nullable=False),
    Column("device_reference", String(200), nullable=True),
    Column("captured_at", String(32), nullable=False),
    Column("retention_expires_at", String(32), nullable=True),
    Column("deleted_at", String(32), nullable=True),
    Column("encrypted_sync_copy", Text, nullable=True),
    Index("idx_neural_vault_subject", "subject_id"),
    Index("idx_neural_vault_subject_session", "subject_id", "session_id"),
)

# --- Phase 3 Global Trust Fabric & Principal Intelligence ---

trust_fabric_principals = Table(
    "trust_fabric_principals",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("principal_type", String(32), nullable=False),
    Column("display_name", String(255), nullable=False),
    Column("lifecycle_state", String(32), nullable=False, default="PENDING_VERIFICATION"),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Column("metadata_json", Text, nullable=True),
    Index("idx_tf_prin_org", "org_id"),
    Index("idx_tf_prin_state", "lifecycle_state"),
    Index("idx_tf_prin_type", "principal_type"),
    UniqueConstraint("id", "org_id", name="uq_tf_principals_id_org"),
)

trust_fabric_identifiers = Table(
    "trust_fabric_identifiers",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("identifier_type", String(32), nullable=False),
    Column("raw_value", String(512), nullable=False),
    Column("normalized_value", String(512), nullable=False),
    Column("is_primary", Integer, nullable=False, default=0),
    Column("verification_state", String(32), nullable=False, default="UNVERIFIED"),
    Column("verified_at", String(32), nullable=True),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("source_id", String(64), nullable=True),
    Column("created_at", String(32), nullable=False),
    Index("idx_tf_ident_norm", "normalized_value", "identifier_type"),
    Index("idx_tf_ident_prin", "principal_id"),
    Index("idx_tf_ident_org", "org_id"),
    Index(
        "idx_tf_ident_active_uniq",
        "org_id",
        "identifier_type",
        "normalized_value",
        unique=True,
        postgresql_where=text("revoked_at IS NULL"),
        sqlite_where=text("revoked_at IS NULL"),
    ),
)

trust_fabric_sources = Table(
    "trust_fabric_sources",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), nullable=True),
    Column("name", String(200), nullable=False),
    Column("source_tier", String(10), nullable=False),
    Column("provider_type", String(64), nullable=False),
    Column("endpoint_or_uri", String(512), nullable=True),
    Column("is_active", Integer, nullable=False, default=1),
    Column("created_at", String(32), nullable=False),
    Index("idx_tf_src_tier", "source_tier"),
    Index("idx_tf_src_org", "org_id"),
)

trust_fabric_assertions = Table(
    "trust_fabric_assertions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("field_name", String(100), nullable=False),
    Column("field_value", Text, nullable=False),
    Column("source_id", String(64), nullable=False),
    Column("source_tier", String(10), nullable=False),
    Column("verification_method", String(64), nullable=False),
    Column("assurance_level", String(20), nullable=False),
    Column("disclosure_class", String(32), nullable=False),
    Column("verified_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("last_checked_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Column("evidence_digest", String(64), nullable=False),
    Index("idx_tf_asst_prin_field", "principal_id", "field_name"),
    Index("idx_tf_asst_org", "org_id"),
)

trust_fabric_relationships = Table(
    "trust_fabric_relationships",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "subject_principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "target_principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("relationship_type", String(32), nullable=False),
    Column("role_title", String(100), nullable=True),
    Column("verification_state", String(32), nullable=False, default="UNVERIFIED"),
    Column("valid_from", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("source_id", String(64), nullable=False),
    Index("idx_tf_rel_subject", "subject_principal_id"),
    Index("idx_tf_rel_target", "target_principal_id"),
    Index("idx_tf_rel_org", "org_id"),
)

trust_fabric_authority_edges = Table(
    "trust_fabric_authority_edges",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "grantor_principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "grantee_principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action_type", String(100), nullable=False),
    Column("resource_pattern", String(255), nullable=False, default="*"),
    Column("ceiling_limit_usd", Float, nullable=True),
    Column("currency", String(3), nullable=False, default="USD"),
    Column("delegation_depth", Integer, nullable=False, default=0),
    Column("valid_from", String(32), nullable=False),
    Column("expires_at", String(32), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Column("revoked_by", String(64), nullable=True),
    Column("canonical_digest", String(64), nullable=False),
    Index("idx_tf_auth_grantee", "grantee_principal_id"),
    Index("idx_tf_auth_action", "action_type"),
    Index("idx_tf_auth_org", "org_id"),
    ForeignKeyConstraint(
        ["grantor_principal_id", "org_id"],
        ["trust_fabric_principals.id", "trust_fabric_principals.org_id"],
        name="fk_tf_auth_grantor_tenant",
        ondelete="RESTRICT",
    ),
    ForeignKeyConstraint(
        ["grantee_principal_id", "org_id"],
        ["trust_fabric_principals.id", "trust_fabric_principals.org_id"],
        name="fk_tf_auth_grantee_tenant",
        ondelete="CASCADE",
    ),
)

trust_fabric_trust_roots = Table(
    "trust_fabric_trust_roots",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column(
        "root_principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("root_public_key", String(512), nullable=False),
    Column("key_algorithm", String(32), nullable=False, default="Ed25519"),
    Column("established_at", String(32), nullable=False),
    Column("status", String(32), nullable=False, default="ACTIVE"),
    Column("canonical_digest", String(64), nullable=False),
    Index("idx_tf_root_org", "org_id"),
)

trust_fabric_bootstrap_records = Table(
    "trust_fabric_bootstrap_records",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    ),
    Column("token_hash", String(64), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Column("claimed_by_principal_id", String(64), nullable=True),
    Column("nonce", String(64), nullable=False, unique=True),
    Column("created_at", String(32), nullable=False),
    Index("idx_tf_boot_org", "org_id"),
    Index("idx_tf_boot_nonce", "nonce"),
)

trust_fabric_passports = Table(
    "trust_fabric_passports",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("version", String(20), nullable=False, default="3.0"),
    Column("passport_type", String(32), nullable=False),
    Column("claims_json", Text, nullable=False),
    Column("assurance_vector_json", Text, nullable=False),
    Column("generated_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("verification_hash", String(64), nullable=False),
    Column("signature", Text, nullable=True),
    Column("signing_key_id", String(64), nullable=True),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_tf_pass_prin", "principal_id"),
    Index("idx_tf_pass_org", "org_id"),
)

trust_fabric_conflicts = Table(
    "trust_fabric_conflicts",
    metadata,
    Column("id", String(64), primary_key=True),
    Column(
        "principal_id",
        String(64),
        ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("field_or_claim", String(100), nullable=False),
    Column("assertion_id_a", String(64), nullable=False),
    Column("assertion_id_b", String(64), nullable=False),
    Column("conflict_type", String(32), nullable=False),
    Column("detected_at", String(32), nullable=False),
    Column("status", String(32), nullable=False, default="UNRESOLVED"),
    Column("resolution_reason", Text, nullable=True),
    Column("resolved_at", String(32), nullable=True),
    Index("idx_tf_conf_prin", "principal_id"),
    Index("idx_tf_conf_org", "org_id"),
)

trust_fabric_challenges = Table(
    "trust_fabric_challenges",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("principal_id", String(64), nullable=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("challenge_type", String(32), nullable=False),
    Column("target_identifier", String(512), nullable=False),
    Column("nonce", String(64), nullable=False, unique=True),
    Column("expected_response_hash", String(64), nullable=False),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("issued_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("completed_at", String(32), nullable=True),
    Index("idx_tf_chal_nonce", "nonce"),
    Index("idx_tf_chal_org", "org_id"),
)

trust_fabric_federated_assertions = Table(
    "trust_fabric_federated_assertions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("issuer_org_id", String(36), nullable=False),
    Column("audience_org_id", String(36), nullable=False),
    Column("subject_principal_id", String(64), nullable=False),
    Column("claim_type", String(64), nullable=False),
    Column("claim_payload_json", Text, nullable=False),
    Column("nonce", String(64), nullable=False, unique=True),
    Column("signature", Text, nullable=False),
    Column("key_id", String(64), nullable=False),
    Column("issued_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_tf_fed_nonce", "nonce"),
    Index("idx_tf_fed_audience", "audience_org_id"),
)

# ── Phase 4: Enterprise IAM & Privileged Control Plane ────────────────────────

iam_step_up_nonces = Table(
    "iam_step_up_nonces",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("session_id", String(128), nullable=True),
    Column("nonce_hash", String(64), nullable=False, unique=True),
    Column("action", String(64), nullable=False),
    Column("target_resource_id", String(128), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("consumed_at", String(32), nullable=True),
    Index("idx_iam_nonce_hash", "nonce_hash"),
    Index("idx_iam_nonce_org_prin", "org_id", "principal_id"),
)

iam_sessions = Table(
    "iam_sessions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("token_hash", String(64), nullable=False, unique=True),
    Column("session_type", String(32), nullable=False, default="INTERACTIVE"),
    Column("status", String(32), nullable=False, default="ACTIVE"),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("last_seen_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_iam_sess_token", "token_hash"),
    Index("idx_iam_sess_org_prin", "org_id", "principal_id"),
)

iam_api_key_lineage = Table(
    "iam_api_key_lineage",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("name", String(200), nullable=False),
    Column("fingerprint", String(64), nullable=False, unique=True),
    Column("parent_key_id", String(64), nullable=True),
    Column("status", String(32), nullable=False, default="ACTIVE"),
    Column("scopes_json", Text, nullable=False, default="[]"),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_iam_key_fprint", "fingerprint"),
    Index("idx_iam_key_org", "org_id"),
)

iam_scim_users = Table(
    "iam_scim_users",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("external_id", String(255), nullable=True),
    Column("user_name", String(255), nullable=False),
    Column("email", String(255), nullable=False),
    Column("active", Integer, nullable=False, default=1),
    Column("attributes_json", Text, nullable=False, default="{}"),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_iam_scim_usr_org", "org_id"),
    Index("idx_iam_scim_usr_ext", "org_id", "external_id"),
    Index("idx_iam_scim_usr_name", "org_id", "user_name"),
)

iam_scim_groups = Table(
    "iam_scim_groups",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("display_name", String(255), nullable=False),
    Column("members_json", Text, nullable=False, default="[]"),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    Index("idx_iam_scim_grp_org", "org_id"),
)

iam_jit_grants = Table(
    "iam_jit_grants",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("target_role", String(32), nullable=False),
    Column("allowed_actions_json", Text, nullable=False),
    Column("justification", Text, nullable=False),
    Column("status", String(32), nullable=False, default="REQUESTED"),
    Column("requested_at", String(32), nullable=False),
    Column("approved_at", String(32), nullable=True),
    Column("approver_principal_id", String(64), nullable=True),
    Column("expires_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    Index("idx_iam_jit_org_prin", "org_id", "principal_id"),
)

iam_four_eyes_requests = Table(
    "iam_four_eyes_requests",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("requester_principal_id", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("target_resource_id", String(128), nullable=True),
    Column("parameters_json", Text, nullable=False),
    Column("request_digest", String(64), nullable=False),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("approver_principal_id", String(64), nullable=True),
    Column("approval_time", String(32), nullable=True),
    Column("rejection_reason", Text, nullable=True),
    Column("executed_at", String(32), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Index("idx_iam_fe_org", "org_id"),
    Index("idx_iam_fe_req", "requester_principal_id"),
)

iam_break_glass_sessions = Table(
    "iam_break_glass_sessions",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("incident_id", String(64), nullable=False),
    Column("capabilities_json", Text, nullable=False),
    Column("justification", Text, nullable=False),
    Column("status", String(32), nullable=False, default="ACTIVE"),
    Column("started_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("terminated_at", String(32), nullable=True),
    Index("idx_iam_bg_org", "org_id"),
    Index("idx_iam_bg_inc", "incident_id"),
)

iam_recovery_policies = Table(
    "iam_recovery_policies",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("threshold", Integer, nullable=False),
    Column("guardians_json", Text, nullable=False),
    Column("created_at", String(32), nullable=False),
    Column("active", Integer, nullable=False, default=1),
    Index("idx_iam_rec_pol_org", "org_id"),
)

iam_recovery_challenges = Table(
    "iam_recovery_challenges",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("new_root_principal_id", String(64), nullable=False),
    Column("new_root_public_key", String(255), nullable=False),
    Column("challenge_message", String(64), nullable=False, unique=True),
    Column("status", String(32), nullable=False, default="PENDING"),
    Column("signatures_json", Text, nullable=False, default="{}"),
    Column("created_at", String(32), nullable=False),
    Column("expires_at", String(32), nullable=False),
    Column("completed_at", String(32), nullable=True),
    Index("idx_iam_chal_msg", "challenge_message"),
    Index("idx_iam_chal_org", "org_id"),
)

iam_privileged_audit_log = Table(
    "iam_privileged_audit_log",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("principal_id", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("risk_tier", String(32), nullable=False),
    Column("allowed", Integer, nullable=False),
    Column("target_resource_id", String(128), nullable=True),
    Column("recorded_at", String(32), nullable=False),
    Column("prev_hash", String(64), nullable=False),
    Column("entry_hash", String(64), nullable=False),
    Column("details_json", Text, nullable=False, default="{}"),
    Index("idx_iam_audit_org", "org_id"),
    Index("idx_iam_audit_ts", "recorded_at"),
)

# Phase 5: Policy Lifecycle, Data Governance & Tenant Erasure
governance_policy_revisions = Table(
    "governance_policy_revisions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("revision_num", Integer, nullable=False),
    Column("rules_json", Text, nullable=False),
    Column("content_digest", String(64), nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("created_by", String(200), nullable=False),
    Column("change_reason", Text, nullable=False),
    Column("approval_id", String(36), nullable=True),
    UniqueConstraint("org_id", "revision_num", name="uq_pol_rev_org_num"),
    Index("idx_pol_rev_org_num", "org_id", "revision_num"),
    Index("idx_pol_rev_digest", "org_id", "content_digest"),
)

governance_policy_activations = Table(
    "governance_policy_activations",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("revision_id", String(36), ForeignKey("governance_policy_revisions.id", ondelete="RESTRICT"), nullable=False),
    Column("content_digest", String(64), nullable=False),
    Column("activated_at", String(64), nullable=False),
    Column("activated_by", String(200), nullable=False),
    Column("governance_epoch", Integer, nullable=False),
    Column("previous_activation_id", String(36), nullable=True),
    Column("is_active", Boolean, nullable=False, default=True),
    Index("idx_pol_act_org_active", "org_id", "is_active"),
)

data_retention_policies = Table(
    "data_retention_policies",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("data_category", String(50), nullable=False),
    Column("retention_period_seconds", Integer, nullable=False),
    Column("created_at", String(64), nullable=False),
    Column("updated_at", String(64), nullable=False),
    UniqueConstraint("org_id", "data_category", name="uq_retention_org_cat"),
    Index("idx_retention_org", "org_id"),
)

data_lifecycle_requests = Table(
    "data_lifecycle_requests",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("request_type", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("requested_at", String(64), nullable=False),
    Column("completed_at", String(64), nullable=True),
    Column("requested_by", String(200), nullable=False),
    Column("details_json", Text, nullable=False, default="{}"),
    Column("verification_status", String(32), nullable=True),
    Index("idx_lifecycle_org_status", "org_id", "status"),
)

data_holds = Table(
    "data_holds",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
    Column("data_category", String(50), nullable=False),
    Column("hold_reason", Text, nullable=False),
    Column("active", Boolean, nullable=False, default=True),
    Column("created_at", String(64), nullable=False),
    Column("created_by", String(200), nullable=False),
    Column("released_at", String(64), nullable=True),
    Column("released_by", String(200), nullable=True),
    Index("idx_holds_org_cat_active", "org_id", "data_category", "active"),
)

tenant_tombstones = Table(
    "tenant_tombstones",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=False, unique=True),
    Column("original_name", String(255), nullable=False),
    Column("generation_id", String(64), nullable=False),
    Column("tombstoned_at", String(64), nullable=False),
    Column("tombstoned_by", String(200), nullable=False),
    Column("authority_hash", String(64), nullable=False),
    Column("evidence_digest", String(64), nullable=False),
    Column("details_json", Text, nullable=False, default="{}"),
    Index("idx_tombstone_org", "org_id"),
    Index("idx_tombstone_gen", "generation_id"),
)

restore_reconciliation_records = Table(
    "restore_reconciliation_records",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("restored_at", String(64), nullable=False),
    Column("status", String(32), nullable=False),
    Column("tombstones_detected", Integer, nullable=False, default=0),
    Column("tenants_quarantined", Integer, nullable=False, default=0),
    Column("details_json", Text, nullable=False, default="{}"),
    Column("reconciled_by", String(200), nullable=False),
    Index("idx_restore_rec_status", "status"),
)

runtime_execution_requests = Table(
    "runtime_execution_requests",
    metadata,
    Column("request_id", String(64), primary_key=True),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("workspace_id", String(64), nullable=True),
    Column("principal_id", String(64), nullable=False),
    Column("agent_id", String(64), nullable=False),
    Column("identity_id", String(64), nullable=False),
    Column("intent", Text, nullable=False),
    Column("action_type", String(128), nullable=False),
    Column("target", String(256), nullable=False),
    Column("action_digest", String(64), nullable=False),
    Column("target_fingerprint", String(64), nullable=True),
    Column("canonical_action_payload", Text, nullable=False),
    Column("approved_arguments", JSON, nullable=False),
    Column("observed_governance_epoch", Integer, nullable=False),
    Column("idempotency_key", String(128), nullable=False),
    Column(
        "approval_id",
        String(36),
        ForeignKey("governance_approvals.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("server_id", String(128), nullable=True),
    Column("lifecycle", String(16), nullable=False, server_default="RECORDED"),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Index(
        "idx_exec_req_org_idempotency",
        "organization_id",
        "idempotency_key",
        unique=True,
    ),
    Index("idx_exec_req_action_digest", "organization_id", "action_digest"),
    Index("idx_exec_req_org_created", "organization_id", "created_at"),
)

governance_execution_authorizations = Table(
    "governance_execution_authorizations",
    metadata,
    Column("authorization_id", String(64), primary_key=True),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("principal_id", String(64), nullable=False),
    Column("agent_id", String(64), nullable=False),
    Column(
        "request_id",
        String(64),
        ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("action_digest", String(64), nullable=False),
    Column("target_fingerprint", String(64), nullable=True),
    Column("issuer_epoch", Integer, nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("oneshot_authority_id", String(64), nullable=False, unique=True),
    Column(
        "approval_id",
        String(36),
        ForeignKey("governance_approvals.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("status", String(16), nullable=False, server_default="ISSUED"),
    Column("issued_at", DateTime(timezone=True), nullable=False),
    Column("consumed_at", DateTime(timezone=True), nullable=True),
    Index("idx_exec_auth_request", "request_id", unique=True),
    Index("idx_exec_auth_org_status", "organization_id", "status"),
)

runtime_execution_attempts = Table(
    "runtime_execution_attempts",
    metadata,
    Column("attempt_id", String(64), primary_key=True),
    Column(
        "request_id",
        String(64),
        ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "authorization_id",
        String(64),
        ForeignKey("governance_execution_authorizations.authorization_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("attempt_number", Integer, nullable=False, default=1),
    Column("worker_id", String(64), nullable=True),
    Column("lease_id", String(64), nullable=True),
    Column("lease_generation", BigInteger, nullable=True),
    Column("state", String(32), nullable=False, server_default="PENDING"),
    Column("effect_id", String(64), nullable=False, unique=True),
    Column("effect_state", String(32), nullable=False, server_default="NO_EFFECT"),
    Column("evidence_status", String(32), nullable=False, server_default="PENDING"),
    Column("backend_start_token_hash", String(64), nullable=True),
    Column("pre_effect_decision", String(32), nullable=True),
    Column("reconciliation_state", String(32), nullable=True),
    Column("admitted_at", DateTime(timezone=True), nullable=True),
    Column("backend_started_at", DateTime(timezone=True), nullable=True),
    Column("effect_claimed_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("failure_code", String(64), nullable=True),
    Column("failure_reason", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("idx_attempt_exec_number", "request_id", "attempt_number", unique=True),
    Index("idx_attempt_auth_id", "authorization_id"),
)

runtime_execution_fences = Table(
    "runtime_execution_fences",
    metadata,
    Column(
        "request_id",
        String(64),
        ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("current_generation", BigInteger, nullable=False, server_default="0"),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

runtime_worker_leases = Table(
    "runtime_worker_leases",
    metadata,
    Column("lease_id", String(64), primary_key=True),
    Column(
        "request_id",
        String(64),
        ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "attempt_id",
        String(64),
        ForeignKey("runtime_execution_attempts.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("worker_id", String(64), nullable=False),
    Column("lease_generation", BigInteger, nullable=False),
    Column("status", String(32), nullable=False, server_default="ACTIVE"),
    Column("acquired_at", DateTime(timezone=True), nullable=False),
    Column("heartbeat_at", DateTime(timezone=True), nullable=False),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("released_at", DateTime(timezone=True), nullable=True),
    Index(
        "idx_runtime_worker_leases_generation",
        "request_id",
        "lease_generation",
        unique=True,
    ),
)

runtime_execution_dispatch_outbox = Table(
    "runtime_execution_dispatch_outbox",
    metadata,
    Column("outbox_id", String(64), primary_key=True),
    Column(
        "request_id",
        String(64),
        ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "attempt_id",
        String(64),
        ForeignKey("runtime_execution_attempts.attempt_id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column(
        "organization_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False, server_default="PENDING"),
    Column("publisher_id", String(64), nullable=True),
    Column("claimed_at", DateTime(timezone=True), nullable=True),
    Column("published_at", DateTime(timezone=True), nullable=True),
    Column("acknowledged_at", DateTime(timezone=True), nullable=True),
    Column("queue_ticket_id", String(64), nullable=True),
    Column("attempt_count", Integer, nullable=False, default=0),
    Column("last_error", Text, nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Index("idx_outbox_status_created", "status", "created_at"),
)

# ── Enterprise SaaS Layer 1 (administrative identity; not execution authority)

enterprise_environments = Table(
    "enterprise_environments",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("type", String(16), nullable=False),
    Column("name", String(100), nullable=False),
    Column("status", String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"),
    Column("created_at", String(32), nullable=False),
    Column("metadata_json", Text, nullable=False, default="{}", server_default="{}"),
    CheckConstraint(
        "type IN ('DEVELOPMENT','STAGING','PRODUCTION')",
        name="chk_enterprise_environment_type",
    ),
    CheckConstraint(
        "status IN ('ACTIVE','DISABLED','DELETED')",
        name="chk_enterprise_environment_status",
    ),
    UniqueConstraint("org_id", "name", name="uq_enterprise_environment_org_name"),
    Index("idx_enterprise_env_org", "org_id"),
)

enterprise_service_accounts = Table(
    "enterprise_service_accounts",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("display_name", String(200), nullable=False),
    Column("status", String(20), nullable=False, default="ACTIVE", server_default="ACTIVE"),
    Column("role", String(20), nullable=False),
    Column(
        "created_by_user_id",
        String(36),
        ForeignKey("web_users.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    Column("created_at", String(32), nullable=False),
    Column("revoked_at", String(32), nullable=True),
    CheckConstraint(
        "status IN ('ACTIVE','DISABLED','REVOKED')",
        name="chk_enterprise_sa_status",
    ),
    CheckConstraint(
        "role <> 'OWNER'",
        name="chk_enterprise_sa_not_owner",
    ),
    Index("idx_enterprise_sa_org", "org_id"),
)

enterprise_service_account_environments = Table(
    "enterprise_service_account_environments",
    metadata,
    Column(
        "service_account_id",
        String(36),
        ForeignKey("enterprise_service_accounts.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "environment_id",
        String(36),
        ForeignKey("enterprise_environments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    ),
)

enterprise_security_audit = Table(
    "enterprise_security_audit",
    metadata,
    Column("event_id", String(36), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("environment_id", String(36), nullable=True),
    Column("actor_type", String(32), nullable=False),
    Column("actor_id", String(64), nullable=False),
    Column("action", String(64), nullable=False),
    Column("target_type", String(64), nullable=False),
    Column("target_id", String(64), nullable=True),
    Column("result", String(24), nullable=False),
    Column("timestamp", String(32), nullable=False),
    Column("request_id", String(64), nullable=True),
    Column("metadata_json", Text, nullable=False, default="{}", server_default="{}"),
    Index("idx_enterprise_audit_org_ts", "org_id", "timestamp"),
    Index("idx_enterprise_audit_action", "action"),
)

identity_verifications = Table(
    "identity_verifications",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "user_id",
        String(36),
        ForeignKey("web_users.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("status", String(32), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED"),
    Column("provider", String(64), nullable=False),
    Column("provider_reference_id", String(128), nullable=True),
    Column("legal_name_encrypted", EncryptedString(), nullable=True),
    Column("country", String(2), nullable=True),
    Column("assurance_level", String(32), nullable=True),
    Column("review_status", String(32), nullable=True),
    Column("verified_at", String(32), nullable=True),
    Column("expires_at", String(32), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    CheckConstraint(
        "status IN ('UNVERIFIED','BASIC_VERIFIED','IDENTITY_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')",
        name="chk_identity_verification_status",
    ),
    Index("idx_identity_verifications_user", "user_id"),
    Index("idx_identity_verifications_provider_ref", "provider", "provider_reference_id"),
)

organization_verifications = Table(
    "organization_verifications",
    metadata,
    Column("id", String(36), primary_key=True),
    Column(
        "org_id",
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    ),
    Column("status", String(32), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED"),
    Column("legal_name", String(300), nullable=True),
    Column("domain", String(255), nullable=True),
    Column("registration_reference", String(128), nullable=True),
    Column(
        "accountable_owner_user_id",
        String(36),
        ForeignKey("web_users.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    Column("provider", String(64), nullable=True),
    Column("provider_reference_id", String(128), nullable=True),
    Column("verified_at", String(32), nullable=True),
    Column("created_at", String(32), nullable=False),
    Column("updated_at", String(32), nullable=False),
    CheckConstraint(
        "status IN ('UNVERIFIED','DOMAIN_VERIFIED','ORGANIZATION_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')",
        name="chk_org_verification_status",
    ),
)

identity_provider_events = Table(
    "identity_provider_events",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("provider", String(64), nullable=False),
    Column("event_id", String(128), nullable=False),
    Column("user_id", String(36), nullable=True),
    Column("org_id", String(36), nullable=True),
    Column("payload_hash", String(64), nullable=False),
    Column("received_at", String(32), nullable=False),
    UniqueConstraint("provider", "event_id", name="uq_identity_provider_event"),
)

api_key_issuance_decisions = Table(
    "api_key_issuance_decisions",
    metadata,
    Column("id", String(36), primary_key=True),
    Column("org_id", String(36), nullable=True),
    Column("principal_user_id", String(36), nullable=True),
    Column("environment_id", String(36), nullable=True),
    Column("allowed", Integer, nullable=False),
    Column("reason_code", String(64), nullable=False),
    Column("requested_scopes", Text, nullable=False, default="[]", server_default="[]"),
    Column("created_at", String(32), nullable=False),
    Index("idx_api_key_issuance_org", "org_id"),
)


class DatabaseEngine:
    """Async database engine wrapping SQLAlchemy — SQLite or PostgreSQL.

    What "no automated failover" still means, stated plainly: actually
    promoting a replica to primary (Patroni, RDS/Cloud SQL Multi-AZ,
    Postgres streaming replication) is infrastructure the deployer owns —
    no amount of application code can substitute for it. What this class
    *does* do is tolerate the transient connection failures that happen
    during that window — a container restarting into a DNS name that
    hasn't repointed yet, a managed database finishing a failover a few
    seconds after the app tries to connect — by retrying with backoff
    instead of crashing hard on the first attempt. That's a real, scoped
    improvement, not a claim of full HA.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def raw(self) -> AsyncEngine:
        return self._engine

    async def init(
        self,
        *,
        max_attempts: int = 5,
        base_delay_seconds: float = 1.0,
        auto_create_tables: bool = True,
    ) -> None:
        """Initialize database connection, optionally verifying schema.

        If auto_create_tables is True (development/testing), creates all tables if they don't exist.
        If auto_create_tables is False (production), executes a lightweight connectivity check (`SELECT 1`)
        without running metadata.create_all, respecting Alembic migration ownership.

        Retries transient connection failures (OperationalError/DBAPIError —
        covers "connection refused", "server closed the connection
        unexpectedly", DNS not yet repointed after a failover) with capped
        exponential backoff before giving up. SQLite's local file is never
        actually unavailable this way, so this loop is a same-attempt no-op
        there; it matters for Postgres against a managed/replicated backend.
        """
        attempt = 0
        while True:
            try:
                async with self._engine.begin() as conn:
                    if auto_create_tables:
                        if "sqlite" in str(self._engine.url):
                            await conn.execute(text("PRAGMA journal_mode=WAL"))
                            await conn.execute(text("PRAGMA synchronous=NORMAL"))
                        await conn.run_sync(metadata.create_all)
                    else:
                        await conn.execute(text("SELECT 1"))
                return
            except (OperationalError, DBAPIError):
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = base_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "db_connect_retry",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "delay_seconds": delay,
                    },
                )
                await asyncio.sleep(delay)

    async def connect(self) -> AsyncConnection:
        return await self._engine.connect()

    async def ping(self, timeout_seconds: float = 2.0) -> bool:
        """Execute a bounded connectivity probe. Never raises; never leaks errors."""
        from sqlalchemy import text

        try:
            async with asyncio.timeout(timeout_seconds):
                async with self._engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def close(self) -> None:
        await self._engine.dispose()


def create_engine(db_url: str) -> DatabaseEngine:
    """
    Build the right async engine from a URL string.

    - ``":memory:"`` or SQLite path → ``sqlite+aiosqlite``
    - ``"postgresql://..."``         → ``postgresql+asyncpg``
    """
    if db_url.startswith("postgresql"):
        url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
            # Transaction-mode connection poolers (PgBouncer, Supabase's
            # Supavisor) multiplex many client connections over few backend
            # ones — a prepared statement created on one backend connection
            # can vanish or collide by the time asyncpg's statement cache
            # tries to reuse it on a different one, surfacing as random
            # "prepared statement already exists / does not exist" errors
            # under concurrent load. Disabling asyncpg's statement cache
            # avoids the whole class of bugs; the overhead is negligible
            # for this workload and it's harmless against a direct
            # (non-pooled) connection too.
            connect_args={"statement_cache_size": 0},
        )
    elif db_url == ":memory:":
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            # An in-memory SQLite database only exists for the lifetime of
            # the single connection that created it, so every checkout from
            # this engine must reuse that same connection -- otherwise a
            # write on one pooled connection and a same-transaction-adjacent
            # read on another silently hit two different, unrelated empty
            # databases.
            #
            # StaticPool alone isn't enough: it hands out the same
            # connection object to every concurrent checkout without
            # blocking, it doesn't queue them -- and Starlette's
            # BaseHTTPMiddleware runs the downstream app via a separate
            # task, so even one sequential-looking `await client.post(...)`
            # can have two coroutines touching the connection at overlapping
            # points. That combination (shared but not exclusive) is what
            # produced real, intermittent CI failures: a request's own
            # query and something else both mid-flight on the identical
            # aiosqlite connection at once, corrupting whichever read lost
            # the race -- reliably reproducible on GitHub's runner, never
            # locally, because it depends on scheduling timing this fast
            # local machine rarely hits.
            #
            # SQLAlchemy auto-selects StaticPool for any ":memory:" URL
            # regardless of what's passed here, so it has to be overridden
            # explicitly. AsyncAdaptedQueuePool with pool_size=1,
            # max_overflow=0 gives both properties actually needed: only one
            # connection is ever created (satisfying the ":memory:" sharing
            # requirement), and -- unlike StaticPool, which hands the same
            # connection to every concurrent checkout without blocking -- a
            # second concurrent checkout attempt genuinely queues and waits
            # for checkin instead of racing the first on the same
            # connection.
            poolclass=AsyncAdaptedQueuePool,
            pool_size=1,
            max_overflow=0,
            echo=False,
        )
    elif db_url.startswith("sqlite"):
        url = db_url if "aiosqlite" in db_url else db_url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        engine = create_async_engine(
            url,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    else:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_url}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    return DatabaseEngine(engine)
