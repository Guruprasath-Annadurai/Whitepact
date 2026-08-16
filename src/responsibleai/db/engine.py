"""Async SQLAlchemy engine factory — SQLite for dev/test, PostgreSQL for production."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
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
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("request_id",    String(64),  nullable=False, unique=True),
    Column("org_id",        String(36),  nullable=True),
    Column("provider",      String(50),  nullable=False),
    Column("model",         String(100), nullable=False),
    Column("team",          String(100), nullable=False, default="default"),
    Column("application",   String(100), nullable=False, default="default"),
    Column("input_tokens",  Integer,     nullable=False),
    Column("output_tokens", Integer,     nullable=False),
    Column("cached_tokens", Integer,     nullable=False, default=0),
    Column("input_cost",    Float,       nullable=False, default=0.0),
    Column("output_cost",   Float,       nullable=False, default=0.0),
    Column("total_cost",    Float,       nullable=False, default=0.0),
    Column("prompt_hash",   String(64),  nullable=True),
    Column("metadata",      Text,        nullable=True),
    Column("recorded_at",   String(32),  nullable=False),
    Index("idx_tu_org",        "org_id"),
    Index("idx_tu_provider",   "provider"),
    Index("idx_tu_model",      "model"),
    Index("idx_tu_team",       "team"),
    Index("idx_tu_recorded",   "recorded_at"),
)

trust_scores = Table(
    "trust_scores",
    metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
    Column("org_id",       String(36),  nullable=True),
    Column("model_name",   String(100), nullable=False),
    Column("provider",     String(100), nullable=False),
    Column("overall",      Float,       nullable=False),
    Column("grade",        String(2),   nullable=False),
    Column("risk_level",   String(20),  nullable=False),
    Column("fairness",     Float,       nullable=False),
    Column("privacy",      Float,       nullable=False),
    Column("security",     Float,       nullable=False),
    Column("robustness",   Float,       nullable=False),
    Column("compliance",   Float,       nullable=False),
    Column("authenticity", Float,       nullable=False),
    Column("metadata",     Text,        nullable=True),
    Column("recorded_at",  String(32),  nullable=False),
    Index("idx_ts_org",      "org_id"),
    Index("idx_ts_model",    "model_name"),
    Index("idx_ts_provider", "provider"),
    Index("idx_ts_recorded", "recorded_at"),
)

organizations = Table(
    "organizations",
    metadata,
    Column("id",                      String(36),  primary_key=True),
    Column("name",                    String(200), nullable=False),
    Column("slug",                    String(100), nullable=False, unique=True),
    Column("monthly_budget_usd",      Float,       nullable=False, default=10_000.0),
    Column("created_at",              String(32),  nullable=False),
    Column("plan",                    String(20),  nullable=False, default="FREE"),
    Column("stripe_customer_id",      String(64),  nullable=True),
    Column("stripe_subscription_id",  String(64),  nullable=True),
    Column("plan_renews_at",          String(32),  nullable=True),
    Column("sso_required",            Integer,     nullable=False, default=0),
    Column("mfa_required",            Integer,     nullable=False, default=0),
    Index("idx_org_slug", "slug"),
    Index("idx_org_stripe_customer", "stripe_customer_id"),
)

mcp_tool_calls = Table(
    "mcp_tool_calls",
    metadata,
    Column("id",        String(36),  primary_key=True),
    Column("org_id",    String(36),  nullable=True),
    Column("tool_name", String(64),  nullable=False),
    Column("tier",      String(20),  nullable=False),
    Column("timestamp", String(32),  nullable=False),
    Column("allowed",   Integer,     nullable=False, default=1),
    Index("idx_mcp_calls_org", "org_id"),
    Index("idx_mcp_calls_ts",  "timestamp"),
)

org_api_keys = Table(
    "org_api_keys",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("org_id",       String(36),  nullable=False),
    Column("key_hash",     String(64),  nullable=False, unique=True),
    Column("name",         String(200), nullable=False),
    Column("role",         String(20),  nullable=False, default="ANALYST"),
    Column("created_at",   String(32),  nullable=False),
    Column("last_used_at", String(32),  nullable=True),
    Column("revoked",      Integer,     nullable=False, default=0),
    # TOTP MFA (RFC 6238) — see auth/mfa.py. mfa_secret is opt-in encrypted
    # (EncryptedString, see db/encryption.py); mfa_backup_codes is a JSON list
    # of SHA-256 hashes, each single-use. enrolled=0 until the first
    # verify() call succeeds, so a secret that was issued but never
    # confirmed can't silently gate login.
    Column("mfa_secret",       EncryptedString(), nullable=True),
    Column("mfa_enrolled",     Integer,     nullable=False, default=0),
    Column("mfa_backup_codes", Text,        nullable=True),
    Index("idx_oak_org",  "org_id"),
    Index("idx_oak_hash", "key_hash"),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id",          String(36),  primary_key=True),
    Column("timestamp",   String(32),  nullable=False),
    Column("org_id",      String(36),  nullable=True),
    Column("key_id",      String(36),  nullable=True),
    Column("endpoint",    String(256), nullable=False),
    Column("method",      String(10),  nullable=False),
    Column("status_code", Integer,     nullable=True),
    # EncryptedString: opt-in via RAI_FIELD_ENCRYPTION_KEY (see db/encryption.py).
    # Stored as Text (not a fixed-width String) to fit Fernet ciphertext,
    # which is longer than a raw IP address — see migration 0005.
    Column("ip_address",  EncryptedString(),  nullable=True),
    Column("request_id",  String(64),  nullable=True),
    Column("duration_ms", Float,       nullable=True),
    Column("user_agent",  String(512), nullable=True),
    Column("entry_hash",  String(64),  nullable=True),
    Column("prev_hash",   String(64),  nullable=True),
    Index("idx_al_timestamp", "timestamp"),
    Index("idx_al_org",       "org_id"),
    Index("idx_al_endpoint",  "endpoint"),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id",          String(36),   primary_key=True),
    Column("run_type",    String(20),   nullable=False),   # "comparison" | "benchmark" | "dataset_scan"
    Column("model",       String(100),  nullable=False),
    Column("provider",    String(100),  nullable=False, default=""),
    Column("suite",       String(50),   nullable=True),
    Column("org_id",      String(36),   nullable=True),
    Column("created_at",  String(32),   nullable=False),
    Column("payload",     Text,         nullable=False),   # JSON-serialised result dict
    Index("idx_er_model",      "model"),
    Index("idx_er_run_type",   "run_type"),
    Index("idx_er_created_at", "created_at"),
    Index("idx_er_org",        "org_id"),
)

eval_baselines = Table(
    "eval_baselines",
    metadata,
    Column("id",         String(36),  primary_key=True),
    Column("model",      String(100), nullable=False),
    Column("suite",      String(50),  nullable=False),
    Column("metric",     String(100), nullable=False),
    Column("score",      Float,       nullable=False),
    Column("org_id",     String(36),  nullable=True),
    Column("updated_at", String(32),  nullable=False),
    Index("idx_eb_model",  "model"),
    Index("idx_eb_suite",  "suite"),
    Index("idx_eb_org",    "org_id"),
)

webhook_configs = Table(
    "webhook_configs",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("org_id",       String(36),  nullable=True),  # null = legacy/dev flat-key registration
    Column("url",          String(2048), nullable=False),
    Column("provider",     String(20),  nullable=False, default="generic"),
    Column("events",       Text,        nullable=False),   # JSON list of WebhookEvent values
    Column("secret",       EncryptedString(), nullable=True),  # HMAC signing secret — opt-in encrypted
    Column("description",  String(500), nullable=True),
    Column("enabled",      Integer,     nullable=False, default=1),
    Column("max_retries",  Integer,     nullable=False, default=3),
    Column("created_at",   String(32),  nullable=False),
    Index("idx_wc_org",     "org_id"),
    Index("idx_wc_enabled", "enabled"),
)

webhook_deliveries = Table(
    "webhook_deliveries",
    metadata,
    Column("id",            String(36),  primary_key=True),
    Column("webhook_id",    String(36),  nullable=False),
    Column("event",         String(64),  nullable=False),
    Column("payload",       Text,        nullable=False),   # JSON
    Column("status",        String(20),  nullable=False, default="pending"),
    Column("attempts",      Integer,     nullable=False, default=0),
    Column("max_retries",   Integer,     nullable=False, default=3),
    Column("status_code",   Integer,     nullable=True),
    Column("last_error",    Text,        nullable=True),
    Column("created_at",    String(32),  nullable=False),
    Column("next_retry_at", String(32),  nullable=True),
    Column("delivered_at",  String(32),  nullable=True),
    Index("idx_wd_webhook",  "webhook_id"),
    Index("idx_wd_status",   "status"),
    Index("idx_wd_retry",    "next_retry_at"),
)

incidents = Table(
    "incidents",
    metadata,
    Column("id",                    String(36),  primary_key=True),
    Column("created_at",            String(32),  nullable=False),
    Column("org_id",                String(36),  nullable=True),
    # "manual" (POST /api/incidents) | "alertmanager" (POST /api/alerts/webhook) | "mcp_tool" (informational only, never persisted from there directly)
    Column("source",                String(20),  nullable=False, default="manual"),
    Column("incident_type",         String(50),  nullable=False),
    Column("severity",              String(20),  nullable=False),
    Column("siem_event_type",       String(50),  nullable=False),
    Column("model_name",            String(100), nullable=True),
    Column("provider",              String(100), nullable=True),
    Column("description",           Text,        nullable=False),
    Column("evidence_hash",         String(16),  nullable=False),
    Column("evidence_keys",         Text,        nullable=True),   # JSON list
    Column("mitigated",             Integer,     nullable=False, default=0),
    Column("status",                String(20),  nullable=False, default="OPEN"),
    Column("sla_resolution_hours",  Integer,     nullable=False, default=24),
    Column("raw_payload",           Text,        nullable=True),   # JSON — original alert payload, for source=alertmanager
    Index("idx_inc_org",       "org_id"),
    Index("idx_inc_created",   "created_at"),
    Index("idx_inc_severity",  "severity"),
    Index("idx_inc_status",    "status"),
)

leaderboard_models = Table(
    "leaderboard_models",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("model",        String(100), nullable=False),
    Column("provider",     String(50),  nullable=False),
    Column("display_name", String(150), nullable=True),
    Column("adapter",      String(20),  nullable=False, default="mock"),  # "openai"|"anthropic"|"google"|"mock"
    Column("active",       Integer,     nullable=False, default=1),
    Column("added_at",     String(32),  nullable=False),
    Index("idx_lbm_active",         "active"),
    Index("idx_lbm_model_provider", "model", "provider", unique=True),
)

leaderboard_runs = Table(
    "leaderboard_runs",
    metadata,
    Column("id",                     String(36),  primary_key=True),
    Column("model",                  String(100), nullable=False),
    Column("provider",               String(50),  nullable=False),
    Column("created_at",             String(32),  nullable=False),
    Column("methodology_version",    String(20),  nullable=False),
    Column("overall_score",          Float,       nullable=False),
    Column("grade",                  String(2),   nullable=False),
    Column("risk_level",             String(20),  nullable=False),
    Column("fairness",               Float,       nullable=False),
    Column("privacy",                Float,       nullable=False),
    Column("security",               Float,       nullable=False),
    Column("robustness",             Float,       nullable=False),
    Column("compliance",             Float,       nullable=False),
    Column("authenticity",           Float,       nullable=False),
    Column("dimensions_live",        Text,        nullable=False),  # JSON: {dim: bool}
    Column("truthfulqa_accuracy",    Float,       nullable=False),
    Column("bbq_bias_rate",          Float,       nullable=False),
    Column("hellaswag_accuracy",     Float,       nullable=False),
    Column("security_score",         Float,       nullable=False),
    Column("privacy_pii_leak_rate",  Float,       nullable=False),
    Column("avg_hallucination_risk", Float,       nullable=False),
    Column("sample_size",            Integer,     nullable=False),
    Column("findings",               Text,        nullable=False),  # JSON list — the paid diagnostic
    Index("idx_lbr_model_provider", "model", "provider"),
    Index("idx_lbr_created",        "created_at"),
)

trust_passports = Table(
    "trust_passports",
    metadata,
    Column("id",                      String(36),  primary_key=True),  # passport_id
    Column("org_id",                  String(36),  nullable=True),     # null for public self-assessments
    Column("source",                  String(20),  nullable=False),    # "evaluate" | "self_assessment"
    Column("spec_version",            String(20),  nullable=False),
    Column("model_name",              String(100), nullable=False),
    Column("provider",                String(100), nullable=False),
    Column("overall_score",           Float,       nullable=False),
    Column("grade",                   String(2),   nullable=False),
    Column("risk_level",              String(20),  nullable=False),
    Column("fairness",                Float,       nullable=False),
    Column("privacy",                 Float,       nullable=False),
    Column("security",                Float,       nullable=False),
    Column("robustness",              Float,       nullable=False),
    Column("compliance",              Float,       nullable=False),
    Column("authenticity",            Float,       nullable=False),
    Column("bias_summary",            Text,        nullable=True),   # JSON
    Column("hallucination_summary",   Text,        nullable=True),   # JSON
    Column("security_summary",        Text,        nullable=True),   # JSON
    Column("compliance_summary",      Text,        nullable=True),   # JSON
    Column("privacy_summary",         Text,        nullable=True),   # JSON
    Column("generated_at",            String(32),  nullable=False),
    Column("verification_hash",       String(64),  nullable=False),
    Column("certified",               Integer,     nullable=False, default=0),
    Column("certified_at",            String(32),  nullable=True),
    Column("certified_by",            String(200), nullable=True),
    Index("idx_tp_org",       "org_id"),
    Index("idx_tp_model",     "model_name", "provider"),
    Index("idx_tp_certified", "certified"),
    Index("idx_tp_generated", "generated_at"),
)

public_incident_reports = Table(
    "public_incident_reports",
    metadata,
    Column("id",                String(36),  primary_key=True),  # internal ID, always present
    Column("public_id",         String(20),  nullable=True, unique=True),  # "RAI-YYYY-NNNN", set on publish
    Column("status",            String(20),  nullable=False, default="PENDING_REVIEW"),
    Column("title",             String(300), nullable=False),
    Column("description",       Text,        nullable=False),
    Column("incident_type",     String(50),  nullable=False),
    Column("severity",          String(20),  nullable=False),
    Column("affected_model",    String(100), nullable=False),
    Column("affected_provider", String(100), nullable=False),
    Column("affected_version",  String(100), nullable=True),
    Column("reporter_name",     EncryptedString(), nullable=True),  # null = anonymous; PII — opt-in encrypted
    Column("reporter_contact",  EncryptedString(), nullable=True),  # PII — opt-in encrypted, never public
    Column("evidence",          Text,        nullable=True),  # JSON: {urls: [...], reproduction_steps: "..."}
    Column("tags",              Text,        nullable=True),  # JSON list
    Column("submitted_at",      String(32),  nullable=False),
    Column("reviewed_at",       String(32),  nullable=True),
    Column("reviewed_by",       String(200), nullable=True),
    Column("rejection_reason",  Text,        nullable=True),
    Column("published_at",      String(32),  nullable=True),
    Column("entry_hash",        String(64),  nullable=True),
    Column("prev_hash",         String(64),  nullable=True),
    Index("idx_pir_status",       "status"),
    Index("idx_pir_model",        "affected_model", "affected_provider"),
    Index("idx_pir_severity",     "severity"),
    Index("idx_pir_submitted",    "submitted_at"),
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
    Column("id",                      String(36),  primary_key=True),  # evidence_id
    Column("org_id",                  String(36),  nullable=True),
    Column("action_id",               String(36),  nullable=False),
    Column("agent_id",                String(36),  nullable=False),
    Column("identity_id",             String(200), nullable=False),
    Column("action_type",             String(50),  nullable=False),
    Column("target",                  String(200), nullable=False),
    Column("argument_keys",           Text,        nullable=True),  # JSON list of field names, never values
    Column("authority_delegated_by",  String(200), nullable=False),
    # JSON list -- AuthorityContext.delegation_chain, empty for every
    # action that never set one (see governance/models.py's docstring).
    Column("delegation_chain",        Text,        nullable=True),
    Column("risk_tier",               String(20),  nullable=True),
    # NULL when no Policy reached evaluation for this action at all --
    # see governance/policy.py's Policy.version docstring.
    Column("policy_version",          Integer,     nullable=True),
    Column("decision",                String(30),  nullable=False),
    Column("reason_codes",            Text,        nullable=False),  # JSON list
    Column("framework",               String(50),  nullable=True),
    Column("provider",                String(50),  nullable=True),
    Column("model",                   String(100), nullable=True),
    Column("evaluated_at",            String(32),  nullable=False),
    Column("recorded_at",             String(32),  nullable=False),
    Column("entry_hash",              String(64),  nullable=False),
    Column("prev_hash",               String(64),  nullable=True),
    Index("idx_gev_org",       "org_id"),
    Index("idx_gev_action",    "action_id"),
    Index("idx_gev_decision",  "decision"),
    Index("idx_gev_recorded",  "recorded_at"),
)

# Phase 11 — persisted GovernanceDecision.REQUIRE_APPROVAL requests,
# resolvable by a human/delegated authority. evidence_id links back to
# the governance_evidence row for the same action_id, when one was
# recorded for it (optional -- evidence recording and approval
# creation are independent operations, see db/approval_repository.py).
governance_approvals = Table(
    "governance_approvals",
    metadata,
    Column("id",                 String(36),  primary_key=True),  # approval_id
    Column("org_id",             String(36),  nullable=True),
    Column("action_id",          String(36),  nullable=False),
    Column("evidence_id",        String(36),  nullable=True),
    Column("action_type",        String(50),  nullable=False),
    Column("target",             String(200), nullable=False),
    # SHA-256 over action_type/target/arguments — what "this approval
    # matches this exact action" actually means. See
    # governance/approval.py's compute_action_digest()/matches_action().
    Column("action_digest",      String(64),  nullable=False, server_default=""),
    # The original action's arguments, JSON-serialized -- encrypted at
    # rest (EncryptedString, opt-in via RAI_FIELD_ENCRYPTION_KEY, see
    # db/encryption.py) since this is exactly the raw/PII-bearing
    # payload every other part of the governance pipeline deliberately
    # avoids persisting unencrypted. NULL for approvals created before
    # this column existed -- those can never be resumed (see
    # governance/approval.py's build_resume_action()), only
    # resolved/viewed, which was already all they supported.
    Column("arguments",          EncryptedString(), nullable=True),
    Column("reason_codes",       Text,        nullable=False),  # JSON list
    Column("risk_tier",          String(20),  nullable=True),
    Column("status",             String(20),  nullable=False, default="PENDING"),
    Column("requested_by",       String(200), nullable=True),
    Column("requested_at",       String(32),  nullable=False),
    # NULL = no expiry enforced (only true for rows persisted before
    # this column existed; every new approval always gets one — see
    # governance/approval.py's DEFAULT_APPROVAL_TTL_HOURS).
    Column("expires_at",         String(32),  nullable=True),
    # How many distinct APPROVED votes are needed before this approval
    # transitions out of PENDING -- see governance/approval.py's
    # required_approvals docstring for the risk-tier-based default and
    # db/approval_repository.py's resolve()/cast_vote() for the quorum
    # logic. 1 (the default) preserves the exact single-approver
    # behavior every approval had before this column existed.
    Column("required_approvals", Integer,     nullable=False, server_default="1"),
    Column("resolved_by",        String(200), nullable=True),
    Column("resolved_at",        String(32),  nullable=True),
    Column("resolution_notes",   Text,        nullable=True),
    Index("idx_gap_org",         "org_id"),
    Index("idx_gap_status",      "status"),
    Index("idx_gap_requested",   "requested_at"),
    Index("idx_gap_action",      "action_id"),
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
    Column("id",                  String(36),  primary_key=True),
    Column("approval_id",         String(36),  nullable=False),
    Column("resolver_identity_id", String(200), nullable=False),
    Column("outcome",             String(20),  nullable=False),  # APPROVED | DENIED
    Column("notes",               Text,        nullable=True),
    Column("resolved_at",         String(32),  nullable=False),
    Index("idx_gapv_approval",    "approval_id"),
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
    Column("id",            String(36),  primary_key=True),
    Column("org_id",        String(36),  nullable=False),
    Column("rule_id",       String(100), nullable=False),
    Column("reason_code",   String(100), nullable=False),
    Column("effect",        String(30),  nullable=False),
    Column("risk_tiers",    Text,        nullable=True),  # JSON list or null
    Column("action_types",  Text,        nullable=True),  # JSON list or null
    Column("targets",       Text,        nullable=True),  # JSON list or null
    Column("position",      Integer,     nullable=False),
    Column("created_at",    String(32),  nullable=False),
    Column("updated_at",    String(32),  nullable=False),
    Index("idx_gpol_org",      "org_id"),
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
    Column("org_id",     String(36), primary_key=True),
    Column("version",    Integer,    nullable=False, default=0),
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
governance_workflow_rules = Table(
    "governance_workflow_rules",
    metadata,
    Column("id",             String(36),  primary_key=True),
    Column("org_id",         String(36),  nullable=False),
    Column("rule_id",        String(100), nullable=False),
    Column("action_types",   Text,        nullable=False),  # JSON ordered list
    Column("window_minutes", Integer,     nullable=False),
    Column("created_at",     String(32),  nullable=False),
    Index("idx_gwr_org", "org_id"),
)

org_authority_ceilings = Table(
    "org_authority_ceilings",
    metadata,
    Column("org_id",               String(36), primary_key=True),
    Column("max_value_usd",        Float,      nullable=True),
    Column("allowed_targets",      Text,       nullable=True),  # JSON list or null
    Column("denied_targets",       Text,       nullable=True),  # JSON list or null
    Column("max_delegation_depth", Integer,    nullable=True),
    Column("allowed_action_types", Text,       nullable=True),  # JSON list or null; null = unrestricted
    Column("require_approval_for", Text,       nullable=True),  # JSON list or null
    Column("updated_at",           String(32), nullable=False),
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
    Column("id",         String(36),   primary_key=True),  # server_id
    Column("org_id",     String(36),   nullable=False),
    Column("name",       String(200),  nullable=False),
    Column("url",        String(2048), nullable=False),
    Column("enabled",    Integer,      nullable=False, server_default="1"),
    # Bearer credential for the upstream server itself -- opt-in
    # encrypted (EncryptedString, RAI_FIELD_ENCRYPTION_KEY), same
    # protection as every other credential column in this schema.
    Column("auth_token", EncryptedString(), nullable=True),
    Column("added_by",   String(200),  nullable=True),
    Column("created_at", String(32),   nullable=False),
    Index("idx_ums_org", "org_id"),
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

    async def init(self, *, max_attempts: int = 5, base_delay_seconds: float = 1.0) -> None:
        """Create all tables if they don't exist.

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
                    if "sqlite" in str(self._engine.url):
                        await conn.execute(text("PRAGMA journal_mode=WAL"))
                        await conn.execute(text("PRAGMA synchronous=NORMAL"))
                    await conn.run_sync(metadata.create_all)
                return
            except (OperationalError, DBAPIError):
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = base_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "db_connect_retry",
                    extra={"attempt": attempt, "max_attempts": max_attempts, "delay_seconds": delay},
                )
                await asyncio.sleep(delay)

    async def connect(self) -> AsyncConnection:
        return await self._engine.connect()

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
    else:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_url}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    return DatabaseEngine(engine)
