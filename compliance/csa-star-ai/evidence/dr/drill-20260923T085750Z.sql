PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE token_usage (
	id INTEGER NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36), 
	provider VARCHAR(50) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	team VARCHAR(100) NOT NULL, 
	application VARCHAR(100) NOT NULL, 
	input_tokens INTEGER NOT NULL, 
	output_tokens INTEGER NOT NULL, 
	cached_tokens INTEGER NOT NULL, 
	input_cost FLOAT NOT NULL, 
	output_cost FLOAT NOT NULL, 
	total_cost FLOAT NOT NULL, 
	prompt_hash VARCHAR(64), 
	metadata TEXT, 
	recorded_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (request_id)
);
CREATE TABLE trust_scores (
	id INTEGER NOT NULL, 
	org_id VARCHAR(36), 
	model_name VARCHAR(100) NOT NULL, 
	provider VARCHAR(100) NOT NULL, 
	overall FLOAT NOT NULL, 
	grade VARCHAR(2) NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	fairness FLOAT NOT NULL, 
	privacy FLOAT NOT NULL, 
	security FLOAT NOT NULL, 
	robustness FLOAT NOT NULL, 
	compliance FLOAT NOT NULL, 
	authenticity FLOAT NOT NULL, 
	metadata TEXT, 
	recorded_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE organizations (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	slug VARCHAR(100) NOT NULL, 
	monthly_budget_usd FLOAT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	"plan" VARCHAR(20) NOT NULL, 
	stripe_customer_id VARCHAR(64), 
	stripe_subscription_id VARCHAR(64), 
	plan_renews_at VARCHAR(32), 
	subscription_status VARCHAR(32) NOT NULL, 
	governance_status VARCHAR(16) DEFAULT 'ACTIVE' NOT NULL, 
	sso_required INTEGER NOT NULL, 
	mfa_required INTEGER NOT NULL, 
	provisioner_key_id VARCHAR(64), 
	paddle_customer_id VARCHAR(64), 
	paddle_subscription_id VARCHAR(64), 
	entitlement_version INTEGER NOT NULL, 
	entitlement_updated_at VARCHAR(32), 
	paddle_last_occurred_at VARCHAR(36), 
	workspace_kind VARCHAR(20) DEFAULT 'ORGANIZATION' NOT NULL, 
	owner_user_id VARCHAR(36), 
	settings_json TEXT DEFAULT '{}' NOT NULL, 
	deactivated_at VARCHAR(32), 
	PRIMARY KEY (id), 
	UNIQUE (slug)
);
CREATE TABLE mcp_tool_calls (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	tool_name VARCHAR(64) NOT NULL, 
	tier VARCHAR(20) NOT NULL, 
	timestamp VARCHAR(32) NOT NULL, 
	allowed INTEGER NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE org_api_keys (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	key_hash VARCHAR(64) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	last_used_at VARCHAR(32), 
	revoked INTEGER NOT NULL, 
	mfa_secret TEXT, 
	mfa_enrolled INTEGER NOT NULL, 
	mfa_backup_codes TEXT, 
	created_by_user_id VARCHAR(36), 
	accountable_human_user_id VARCHAR(36), 
	service_account_id VARCHAR(36), 
	environment_id VARCHAR(36), 
	holder_kind VARCHAR(32) DEFAULT 'human_key' NOT NULL, 
	overlap_expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	UNIQUE (key_hash)
);
CREATE TABLE web_users (
	id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	full_name VARCHAR(200) NOT NULL, 
	password_hash TEXT NOT NULL, 
	email_verified_at VARCHAR(32), 
	disabled INTEGER NOT NULL, 
	verification_status VARCHAR(32) DEFAULT 'UNVERIFIED' NOT NULL, 
	phone_verified_at VARCHAR(32), 
	abuse_hold INTEGER DEFAULT '0' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (email)
);
CREATE TABLE oauth_flow_states (
	state_hash VARCHAR(64) NOT NULL, 
	provider VARCHAR(64) NOT NULL, 
	tenant_id VARCHAR(36), 
	session_id VARCHAR(64), 
	nonce VARCHAR(64) NOT NULL, 
	pkce_verifier VARCHAR(128), 
	redirect_uri VARCHAR(512) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (state_hash)
);
CREATE TABLE paddle_webhook_events (
	event_id VARCHAR(100) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	occurred_at VARCHAR(36), 
	entity_id VARCHAR(100), 
	org_id VARCHAR(36), 
	payload_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	received_at VARCHAR(32) NOT NULL, 
	processed_at VARCHAR(32), 
	last_error TEXT, 
	PRIMARY KEY (event_id)
);
CREATE TABLE audit_log (
	id VARCHAR(36) NOT NULL, 
	timestamp VARCHAR(32) NOT NULL, 
	org_id VARCHAR(36), 
	key_id VARCHAR(64), 
	endpoint VARCHAR(256) NOT NULL, 
	method VARCHAR(10) NOT NULL, 
	status_code INTEGER, 
	ip_address TEXT, 
	request_id VARCHAR(64), 
	duration_ms FLOAT, 
	user_agent VARCHAR(512), 
	entry_hash VARCHAR(64), 
	prev_hash VARCHAR(64), 
	PRIMARY KEY (id)
);
CREATE TABLE eval_runs (
	id VARCHAR(36) NOT NULL, 
	run_type VARCHAR(20) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	provider VARCHAR(100) NOT NULL, 
	suite VARCHAR(50), 
	org_id VARCHAR(36), 
	created_at VARCHAR(32) NOT NULL, 
	payload TEXT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE eval_baselines (
	id VARCHAR(36) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	suite VARCHAR(50) NOT NULL, 
	metric VARCHAR(100) NOT NULL, 
	score FLOAT NOT NULL, 
	org_id VARCHAR(36), 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE webhook_configs (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	url VARCHAR(2048) NOT NULL, 
	provider VARCHAR(20) NOT NULL, 
	events TEXT NOT NULL, 
	secret TEXT, 
	description VARCHAR(500), 
	enabled INTEGER NOT NULL, 
	max_retries INTEGER NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE webhook_deliveries (
	id VARCHAR(36) NOT NULL, 
	webhook_id VARCHAR(36) NOT NULL, 
	event VARCHAR(64) NOT NULL, 
	payload TEXT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	attempts INTEGER NOT NULL, 
	max_retries INTEGER NOT NULL, 
	status_code INTEGER, 
	last_error TEXT, 
	created_at VARCHAR(32) NOT NULL, 
	next_retry_at VARCHAR(32), 
	delivered_at VARCHAR(32), 
	PRIMARY KEY (id)
);
CREATE TABLE incidents (
	id VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	org_id VARCHAR(36), 
	source VARCHAR(20) NOT NULL, 
	incident_type VARCHAR(50) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	siem_event_type VARCHAR(50) NOT NULL, 
	model_name VARCHAR(100), 
	provider VARCHAR(100), 
	description TEXT NOT NULL, 
	evidence_hash VARCHAR(16) NOT NULL, 
	evidence_keys TEXT, 
	mitigated INTEGER NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	sla_resolution_hours INTEGER NOT NULL, 
	raw_payload TEXT, 
	PRIMARY KEY (id)
);
CREATE TABLE leaderboard_models (
	id VARCHAR(36) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	display_name VARCHAR(150), 
	adapter VARCHAR(20) NOT NULL, 
	active INTEGER NOT NULL, 
	added_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE leaderboard_runs (
	id VARCHAR(36) NOT NULL, 
	model VARCHAR(100) NOT NULL, 
	provider VARCHAR(50) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	methodology_version VARCHAR(20) NOT NULL, 
	overall_score FLOAT NOT NULL, 
	grade VARCHAR(2) NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	fairness FLOAT NOT NULL, 
	privacy FLOAT NOT NULL, 
	security FLOAT NOT NULL, 
	robustness FLOAT NOT NULL, 
	compliance FLOAT NOT NULL, 
	authenticity FLOAT NOT NULL, 
	dimensions_live TEXT NOT NULL, 
	truthfulqa_accuracy FLOAT NOT NULL, 
	bbq_bias_rate FLOAT NOT NULL, 
	hellaswag_accuracy FLOAT NOT NULL, 
	security_score FLOAT NOT NULL, 
	privacy_pii_leak_rate FLOAT NOT NULL, 
	avg_hallucination_risk FLOAT NOT NULL, 
	sample_size INTEGER NOT NULL, 
	findings TEXT NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE trust_passports (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	source VARCHAR(20) NOT NULL, 
	spec_version VARCHAR(20) NOT NULL, 
	model_name VARCHAR(100) NOT NULL, 
	provider VARCHAR(100) NOT NULL, 
	overall_score FLOAT NOT NULL, 
	grade VARCHAR(2) NOT NULL, 
	risk_level VARCHAR(20) NOT NULL, 
	fairness FLOAT NOT NULL, 
	privacy FLOAT NOT NULL, 
	security FLOAT NOT NULL, 
	robustness FLOAT NOT NULL, 
	compliance FLOAT NOT NULL, 
	authenticity FLOAT NOT NULL, 
	bias_summary TEXT, 
	hallucination_summary TEXT, 
	security_summary TEXT, 
	compliance_summary TEXT, 
	privacy_summary TEXT, 
	generated_at VARCHAR(32) NOT NULL, 
	verification_hash VARCHAR(64) NOT NULL, 
	certified INTEGER NOT NULL, 
	certified_at VARCHAR(32), 
	certified_by VARCHAR(200), 
	PRIMARY KEY (id)
);
CREATE TABLE public_incident_reports (
	id VARCHAR(36) NOT NULL, 
	public_id VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	title VARCHAR(300) NOT NULL, 
	description TEXT NOT NULL, 
	incident_type VARCHAR(50) NOT NULL, 
	severity VARCHAR(20) NOT NULL, 
	affected_model VARCHAR(100) NOT NULL, 
	affected_provider VARCHAR(100) NOT NULL, 
	affected_version VARCHAR(100), 
	reporter_name TEXT, 
	reporter_contact TEXT, 
	evidence TEXT, 
	tags TEXT, 
	submitted_at VARCHAR(32) NOT NULL, 
	reviewed_at VARCHAR(32), 
	reviewed_by VARCHAR(200), 
	rejection_reason TEXT, 
	published_at VARCHAR(32), 
	entry_hash VARCHAR(64), 
	prev_hash VARCHAR(64), 
	PRIMARY KEY (id), 
	UNIQUE (public_id)
);
CREATE TABLE governance_approvals (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	action_id VARCHAR(36) NOT NULL, 
	evidence_id VARCHAR(36), 
	action_type VARCHAR(50) NOT NULL, 
	target VARCHAR(200) NOT NULL, 
	action_digest VARCHAR(64) DEFAULT '' NOT NULL, 
	arguments TEXT, 
	reason_codes TEXT NOT NULL, 
	risk_tier VARCHAR(20), 
	status VARCHAR(20) NOT NULL, 
	requested_by VARCHAR(200), 
	requested_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	required_approvals INTEGER DEFAULT '1' NOT NULL, 
	resolved_by VARCHAR(200), 
	resolved_at VARCHAR(32), 
	resolution_notes TEXT, 
	purpose TEXT, 
	authentication_method VARCHAR(20), 
	revocation_epoch INTEGER, 
	authority_version VARCHAR(64), 
	policy_version INTEGER, 
	target_fingerprint VARCHAR(64), 
	PRIMARY KEY (id)
);
CREATE TABLE governance_approval_votes (
	id VARCHAR(36) NOT NULL, 
	approval_id VARCHAR(36) NOT NULL, 
	resolver_identity_id VARCHAR(200) NOT NULL, 
	outcome VARCHAR(20) NOT NULL, 
	notes TEXT, 
	resolved_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gapv_approval_resolver UNIQUE (approval_id, resolver_identity_id)
);
CREATE TABLE governance_policies (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	rule_id VARCHAR(100) NOT NULL, 
	reason_code VARCHAR(100) NOT NULL, 
	effect VARCHAR(30) NOT NULL, 
	risk_tiers TEXT, 
	action_types TEXT, 
	targets TEXT, 
	position INTEGER NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE governance_policy_versions (
	org_id VARCHAR(36) NOT NULL, 
	version INTEGER NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (org_id)
);
CREATE TABLE governance_delegations (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	from_identity_id VARCHAR(200), 
	to_identity_id VARCHAR(200) NOT NULL, 
	granted_action_types TEXT NOT NULL, 
	constraints TEXT, 
	require_approval_for TEXT, 
	purpose TEXT NOT NULL, 
	granted_by VARCHAR(200) NOT NULL, 
	granted_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	revoked_by VARCHAR(200), 
	revoke_reason TEXT, 
	PRIMARY KEY (id)
);
CREATE TABLE governance_workflow_rules (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	rule_id VARCHAR(100) NOT NULL, 
	action_types TEXT NOT NULL, 
	window_minutes INTEGER NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE org_authority_ceilings (
	org_id VARCHAR(36) NOT NULL, 
	max_value_usd FLOAT, 
	allowed_targets TEXT, 
	denied_targets TEXT, 
	max_delegation_depth INTEGER, 
	allowed_action_types TEXT, 
	require_approval_for TEXT, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (org_id)
);
CREATE TABLE org_autonomy_budgets (
	org_id VARCHAR(36) NOT NULL, 
	max_autonomous_actions INTEGER NOT NULL, 
	window_minutes INTEGER NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (org_id)
);
CREATE TABLE upstream_mcp_servers (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	url VARCHAR(2048) NOT NULL, 
	enabled INTEGER DEFAULT '1' NOT NULL, 
	auth_token TEXT, 
	added_by VARCHAR(200), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE tool_trust_scores (
	server_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	score INTEGER NOT NULL, 
	tier VARCHAR(20) NOT NULL, 
	has_been_scanned INTEGER DEFAULT '0' NOT NULL, 
	incident_count INTEGER DEFAULT '0' NOT NULL, 
	scan_report_id VARCHAR(36), 
	scan_summary TEXT, 
	last_scanned_at VARCHAR(32), 
	admin_override_tier VARCHAR(20), 
	admin_override_by VARCHAR(200), 
	admin_override_reason TEXT, 
	admin_override_at VARCHAR(32), 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (server_id)
);
CREATE TABLE credential_issuances (
	credential_id VARCHAR(36) NOT NULL, 
	authorization_id VARCHAR(36) NOT NULL, 
	action_id VARCHAR(36) NOT NULL, 
	server_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	agent_id VARCHAR(200), 
	had_credential INTEGER NOT NULL, 
	issued_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (credential_id)
);
CREATE TABLE governance_outcomes (
	id VARCHAR(36) NOT NULL, 
	evidence_id VARCHAR(36) NOT NULL, 
	action_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	status VARCHAR(16) NOT NULL, 
	result_summary TEXT, 
	observed_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE verified_principals (
	id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(255) NOT NULL, 
	org_id VARCHAR(36), 
	issuer VARCHAR(255) NOT NULL, 
	credential_type VARCHAR(128) NOT NULL, 
	holder_kind VARCHAR(32) NOT NULL, 
	claim_keys TEXT NOT NULL, 
	verified_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE governance_intent_contracts (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(200) NOT NULL, 
	goal TEXT NOT NULL, 
	max_value_usd FLOAT, 
	allowed_targets TEXT, 
	denied_targets TEXT, 
	allowed_action_types TEXT, 
	declared_at VARCHAR(32) NOT NULL, 
	valid_from VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	PRIMARY KEY (id)
);
CREATE TABLE governance_authority_passports (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(200) NOT NULL, 
	source VARCHAR(32) NOT NULL, 
	source_id VARCHAR(200) NOT NULL, 
	granted_action_types TEXT NOT NULL, 
	max_value_usd FLOAT, 
	allowed_targets TEXT, 
	denied_targets TEXT, 
	require_approval_for TEXT, 
	max_delegation_depth INTEGER, 
	issued_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	revoked_by VARCHAR(200), 
	revoke_reason TEXT, 
	PRIMARY KEY (id)
);
CREATE TABLE oauth_clients (
	client_id VARCHAR(80) NOT NULL, 
	client_name VARCHAR(200) NOT NULL, 
	redirect_uris TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	revoked INTEGER NOT NULL, 
	PRIMARY KEY (client_id)
);
CREATE TABLE oauth_authorization_requests (
	request_hash VARCHAR(64) NOT NULL, 
	client_id VARCHAR(80) NOT NULL, 
	redirect_uri VARCHAR(512) NOT NULL, 
	state VARCHAR(512) NOT NULL, 
	code_challenge VARCHAR(128) NOT NULL, 
	scopes TEXT NOT NULL, 
	resource VARCHAR(512) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	used INTEGER NOT NULL, 
	PRIMARY KEY (request_hash)
);
CREATE TABLE oauth_authorization_codes (
	code_hash VARCHAR(64) NOT NULL, 
	client_id VARCHAR(80) NOT NULL, 
	redirect_uri VARCHAR(512) NOT NULL, 
	code_challenge VARCHAR(128) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(80) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	scopes TEXT NOT NULL, 
	resource VARCHAR(512) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	used INTEGER NOT NULL, 
	PRIMARY KEY (code_hash)
);
CREATE TABLE oauth_credentials (
	token_hash VARCHAR(64) NOT NULL, 
	token_type VARCHAR(16) NOT NULL, 
	family_id VARCHAR(80) NOT NULL, 
	client_id VARCHAR(80) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(80) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	scopes TEXT NOT NULL, 
	resource VARCHAR(512) NOT NULL, 
	issued_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	revoked INTEGER NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (token_hash)
);
CREATE TABLE oauth_auth_events (
	id VARCHAR(36) NOT NULL, 
	event_type VARCHAR(64) NOT NULL, 
	outcome VARCHAR(16) NOT NULL, 
	org_id VARCHAR(36), 
	subject_id VARCHAR(80), 
	client_id VARCHAR(80), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE trust_fabric_sources (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36), 
	name VARCHAR(200) NOT NULL, 
	source_tier VARCHAR(10) NOT NULL, 
	provider_type VARCHAR(64) NOT NULL, 
	endpoint_or_uri VARCHAR(512), 
	is_active INTEGER NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE trust_fabric_federated_assertions (
	id VARCHAR(64) NOT NULL, 
	issuer_org_id VARCHAR(36) NOT NULL, 
	audience_org_id VARCHAR(36) NOT NULL, 
	subject_principal_id VARCHAR(64) NOT NULL, 
	claim_type VARCHAR(64) NOT NULL, 
	claim_payload_json TEXT NOT NULL, 
	nonce VARCHAR(64) NOT NULL, 
	signature TEXT NOT NULL, 
	key_id VARCHAR(64) NOT NULL, 
	issued_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	UNIQUE (nonce)
);
CREATE TABLE tenant_tombstones (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	original_name VARCHAR(255) NOT NULL, 
	generation_id VARCHAR(64) NOT NULL, 
	tombstoned_at VARCHAR(64) NOT NULL, 
	tombstoned_by VARCHAR(200) NOT NULL, 
	authority_hash VARCHAR(64) NOT NULL, 
	evidence_digest VARCHAR(64) NOT NULL, 
	details_json TEXT NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (org_id)
);
CREATE TABLE restore_reconciliation_records (
	id VARCHAR(36) NOT NULL, 
	restored_at VARCHAR(64) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	tombstones_detected INTEGER NOT NULL, 
	tenants_quarantined INTEGER NOT NULL, 
	details_json TEXT NOT NULL, 
	reconciled_by VARCHAR(200) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE identity_provider_events (
	id VARCHAR(36) NOT NULL, 
	provider VARCHAR(64) NOT NULL, 
	event_id VARCHAR(128) NOT NULL, 
	user_id VARCHAR(36), 
	org_id VARCHAR(36), 
	payload_hash VARCHAR(64) NOT NULL, 
	received_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_identity_provider_event UNIQUE (provider, event_id)
);
CREATE TABLE api_key_issuance_decisions (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	principal_user_id VARCHAR(36), 
	environment_id VARCHAR(36), 
	allowed INTEGER NOT NULL, 
	reason_code VARCHAR(64) NOT NULL, 
	requested_scopes TEXT DEFAULT '[]' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE webauthn_challenges (
	challenge_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(36), 
	session_id VARCHAR(64), 
	org_id VARCHAR(36), 
	ceremony VARCHAR(32) NOT NULL, 
	rp_id VARCHAR(255) NOT NULL, 
	origin VARCHAR(512) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (challenge_hash), 
	CONSTRAINT chk_webauthn_ceremony CHECK (ceremony IN ('register','authenticate'))
);
CREATE TABLE auth_replay_records (
	id VARCHAR(36) NOT NULL, 
	kind VARCHAR(32) NOT NULL, 
	replay_key VARCHAR(128) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_auth_replay_kind_key UNIQUE (kind, replay_key)
);
CREATE TABLE identity_security_notifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36), 
	org_id VARCHAR(36), 
	event_type VARCHAR(64) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	payload_json TEXT DEFAULT '{}' NOT NULL, 
	PRIMARY KEY (id)
);
CREATE TABLE identity_oauth_transactions (
	state_hash VARCHAR(64) NOT NULL, 
	provider VARCHAR(32) NOT NULL, 
	nonce VARCHAR(64) NOT NULL, 
	pkce_verifier VARCHAR(128) NOT NULL, 
	redirect_uri VARCHAR(512) NOT NULL, 
	intended_org_id VARCHAR(36), 
	session_id VARCHAR(64), 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	code_hash VARCHAR(64), 
	PRIMARY KEY (state_hash), 
	CONSTRAINT chk_identity_oauth_status CHECK (status IN ('PENDING','CONSUMED','EXPIRED'))
);
CREATE TABLE identity_rate_counters (
	bucket_key VARCHAR(256) NOT NULL, 
	window_start VARCHAR(32) NOT NULL, 
	count INTEGER DEFAULT '0' NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (bucket_key)
);
CREATE TABLE dashboard_saml_transactions (
	request_id_hash VARCHAR(64) NOT NULL, 
	idp_entity_id VARCHAR(512) NOT NULL, 
	acs_url VARCHAR(512) NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (request_id_hash), 
	CONSTRAINT chk_dashboard_saml_status CHECK (status IN ('PENDING','CONSUMED','EXPIRED'))
);
CREATE TABLE test_consequential_counters (
	organization_id VARCHAR(36) NOT NULL, 
	counter INTEGER DEFAULT '0' NOT NULL, 
	downstream_call_count INTEGER DEFAULT '0' NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (organization_id)
);
CREATE TABLE sovereign_shadow_observations (
	shadow_observation_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	environment VARCHAR(64), 
	agent_id VARCHAR(128), 
	action_type VARCHAR(128), 
	target_redacted VARCHAR(256), 
	policy_version INTEGER, 
	shadow_disposition VARCHAR(64) NOT NULL, 
	reason_codes_json TEXT DEFAULT '[]' NOT NULL, 
	protocol_version VARCHAR(32) NOT NULL, 
	schema_version VARCHAR(32) NOT NULL, 
	diagnostic_json TEXT DEFAULT '{}' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (shadow_observation_id)
);
CREATE TABLE web_memberships (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
	invited_by_user_id VARCHAR(36), 
	accepted_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	updated_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_web_membership_user_org UNIQUE (user_id, org_id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE web_sessions (
	token_hash VARCHAR(64) NOT NULL, 
	session_id VARCHAR(36), 
	user_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	csrf_hash VARCHAR(64) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	last_seen_at VARCHAR(32) NOT NULL, 
	revoked INTEGER NOT NULL, 
	assurance_level VARCHAR(32) DEFAULT 'PASSWORD' NOT NULL, 
	auth_methods_json TEXT DEFAULT '[]' NOT NULL, 
	auth_time VARCHAR(32), 
	phishing_resistant INTEGER DEFAULT '0' NOT NULL, 
	ip_label VARCHAR(64), 
	user_agent VARCHAR(512), 
	last_step_up_at VARCHAR(32), 
	inactivity_expires_at VARCHAR(32), 
	rotated_from VARCHAR(64), 
	PRIMARY KEY (token_hash), 
	UNIQUE (session_id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE web_verification_tokens (
	token_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	purpose VARCHAR(32) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (token_hash), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE web_identity_providers (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	issuer VARCHAR(512) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	email_at_link VARCHAR(254), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_web_identity_provider_subject UNIQUE (issuer, subject), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE web_invitations (
	id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	email VARCHAR(254) NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	invited_by_user_id VARCHAR(36) NOT NULL, 
	accepted_by_user_id VARCHAR(36), 
	status VARCHAR(24) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	UNIQUE (token_hash), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(invited_by_user_id) REFERENCES web_users (id) ON DELETE RESTRICT, 
	FOREIGN KEY(accepted_by_user_id) REFERENCES web_users (id) ON DELETE SET NULL
);
CREATE TABLE org_api_key_metadata (
	key_id VARCHAR(36) NOT NULL, 
	prefix VARCHAR(20) NOT NULL, 
	environment VARCHAR(16) NOT NULL, 
	scopes TEXT NOT NULL, 
	expires_at VARCHAR(32), 
	rotated_from_id VARCHAR(36), 
	PRIMARY KEY (key_id), 
	FOREIGN KEY(key_id) REFERENCES org_api_keys (id) ON DELETE CASCADE
);
CREATE TABLE stripe_webhook_events (
	event_id VARCHAR(255) NOT NULL, 
	event_type VARCHAR(100) NOT NULL, 
	org_id VARCHAR(36), 
	status VARCHAR(24) NOT NULL, 
	received_at VARCHAR(32) NOT NULL, 
	processed_at VARCHAR(32), 
	last_error TEXT, 
	PRIMARY KEY (event_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE SET NULL
);
CREATE TABLE governance_evidence (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	action_id VARCHAR(36) NOT NULL, 
	agent_id VARCHAR(36) NOT NULL, 
	identity_id VARCHAR(200) NOT NULL, 
	action_type VARCHAR(50) NOT NULL, 
	target VARCHAR(200) NOT NULL, 
	argument_keys TEXT, 
	authority_delegated_by VARCHAR(200) NOT NULL, 
	delegation_chain TEXT, 
	risk_tier VARCHAR(20), 
	policy_version INTEGER, 
	policy_digest VARCHAR(64), 
	authentication_method VARCHAR(20), 
	request_fingerprint VARCHAR(64), 
	arguments_fingerprint VARCHAR(64), 
	purpose TEXT, 
	authority_version VARCHAR(64), 
	consent_id VARCHAR(36), 
	consent_version VARCHAR(64), 
	consent_state VARCHAR(20), 
	governance_epoch INTEGER, 
	approval_id VARCHAR(36), 
	execution_authorization_id VARCHAR(36), 
	execution_nonce_reference VARCHAR(64), 
	execution_target VARCHAR(200), 
	integrity_version INTEGER NOT NULL, 
	integrity_status VARCHAR(32) NOT NULL, 
	chain_sequence INTEGER, 
	decision VARCHAR(30) NOT NULL, 
	reason_codes TEXT NOT NULL, 
	framework VARCHAR(50), 
	provider VARCHAR(50), 
	model VARCHAR(100), 
	evaluated_at VARCHAR(32) NOT NULL, 
	recorded_at VARCHAR(32) NOT NULL, 
	entry_hash VARCHAR(64) NOT NULL, 
	prev_hash VARCHAR(64), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_gev_org_sequence UNIQUE (org_id, chain_sequence), 
	CONSTRAINT fk_evidence_org FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_evidence_chain_heads (
	org_id VARCHAR(36) NOT NULL, 
	head_hash VARCHAR(64), 
	sequence INTEGER NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (org_id), 
	CONSTRAINT fk_evidence_head_org FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_root_authority_records (
	root_id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(255) NOT NULL, 
	root_type VARCHAR(32) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	issuer VARCHAR(255) NOT NULL, 
	verification_method VARCHAR(128) NOT NULL, 
	authority_source VARCHAR(36), 
	jurisdiction VARCHAR(64), 
	evidence_refs TEXT NOT NULL, 
	issued_at VARCHAR(32) NOT NULL, 
	not_before VARCHAR(32), 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	revoked_by VARCHAR(200), 
	revoke_reason TEXT, 
	canonical_digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (root_id), 
	CONSTRAINT uq_root_tenant UNIQUE (root_id, organization_id), 
	CONSTRAINT fk_root_parent_tenant FOREIGN KEY(authority_source, organization_id) REFERENCES governance_root_authority_records (root_id, organization_id) ON DELETE RESTRICT, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_revocation_epochs (
	organization_id VARCHAR(36) NOT NULL, 
	scope VARCHAR(64) NOT NULL, 
	epoch INTEGER DEFAULT '0' NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (organization_id, scope), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_execution_nonces (
	nonce VARCHAR(64) NOT NULL, 
	authorization_id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	consumed_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (nonce), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_crypto_keys (
	key_id VARCHAR(300) NOT NULL, 
	purpose VARCHAR(32) NOT NULL, 
	tenant_id VARCHAR(36) NOT NULL, 
	environment VARCHAR(32) NOT NULL, 
	version INTEGER NOT NULL, 
	wrapped_dek TEXT NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (key_id), 
	FOREIGN KEY(tenant_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_neural_consent (
	consent_id VARCHAR(64) NOT NULL, 
	subject_id VARCHAR(200) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	category VARCHAR(32) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	version INTEGER NOT NULL, 
	granted_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (consent_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_neural_vault_index (
	entry_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(200) NOT NULL, 
	session_id VARCHAR(200) NOT NULL, 
	data_class VARCHAR(32) NOT NULL, 
	device_reference VARCHAR(200), 
	captured_at VARCHAR(32) NOT NULL, 
	retention_expires_at VARCHAR(32), 
	deleted_at VARCHAR(32), 
	encrypted_sync_copy TEXT, 
	PRIMARY KEY (entry_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_principals (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_type VARCHAR(32) NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
	lifecycle_state VARCHAR(32) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	metadata_json TEXT, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_tf_principals_id_org UNIQUE (id, org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_bootstrap_records (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	claimed_by_principal_id VARCHAR(64), 
	nonce VARCHAR(64) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (nonce)
);
CREATE TABLE trust_fabric_challenges (
	id VARCHAR(64) NOT NULL, 
	principal_id VARCHAR(64), 
	org_id VARCHAR(36) NOT NULL, 
	challenge_type VARCHAR(32) NOT NULL, 
	target_identifier VARCHAR(512) NOT NULL, 
	nonce VARCHAR(64) NOT NULL, 
	expected_response_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	issued_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	completed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (nonce)
);
CREATE TABLE iam_step_up_nonces (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	session_id VARCHAR(128), 
	nonce_hash VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	target_resource_id VARCHAR(128), 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (nonce_hash)
);
CREATE TABLE iam_sessions (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	session_type VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	last_seen_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (token_hash)
);
CREATE TABLE iam_api_key_lineage (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	name VARCHAR(200) NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	parent_key_id VARCHAR(64), 
	status VARCHAR(32) NOT NULL, 
	scopes_json TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (fingerprint)
);
CREATE TABLE iam_scim_users (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	external_id VARCHAR(255), 
	user_name VARCHAR(255) NOT NULL, 
	email VARCHAR(255) NOT NULL, 
	active INTEGER NOT NULL, 
	attributes_json TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_scim_groups (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	display_name VARCHAR(255) NOT NULL, 
	members_json TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_jit_grants (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	target_role VARCHAR(32) NOT NULL, 
	allowed_actions_json TEXT NOT NULL, 
	justification TEXT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	requested_at VARCHAR(32) NOT NULL, 
	approved_at VARCHAR(32), 
	approver_principal_id VARCHAR(64), 
	expires_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_four_eyes_requests (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	requester_principal_id VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	target_resource_id VARCHAR(128), 
	parameters_json TEXT NOT NULL, 
	request_digest VARCHAR(64) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	approver_principal_id VARCHAR(64), 
	approval_time VARCHAR(32), 
	rejection_reason TEXT, 
	executed_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_break_glass_sessions (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	incident_id VARCHAR(64) NOT NULL, 
	capabilities_json TEXT NOT NULL, 
	justification TEXT NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	started_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	terminated_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_recovery_policies (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	threshold INTEGER NOT NULL, 
	guardians_json TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	active INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE iam_recovery_challenges (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	new_root_principal_id VARCHAR(64) NOT NULL, 
	new_root_public_key VARCHAR(255) NOT NULL, 
	challenge_message VARCHAR(64) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	signatures_json TEXT NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	completed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (challenge_message)
);
CREATE TABLE iam_privileged_audit_log (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	risk_tier VARCHAR(32) NOT NULL, 
	allowed INTEGER NOT NULL, 
	target_resource_id VARCHAR(128), 
	recorded_at VARCHAR(32) NOT NULL, 
	prev_hash VARCHAR(64) NOT NULL, 
	entry_hash VARCHAR(64) NOT NULL, 
	details_json TEXT NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_policy_revisions (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	revision_num INTEGER NOT NULL, 
	rules_json TEXT NOT NULL, 
	content_digest VARCHAR(64) NOT NULL, 
	created_at VARCHAR(64) NOT NULL, 
	created_by VARCHAR(200) NOT NULL, 
	change_reason TEXT NOT NULL, 
	approval_id VARCHAR(36), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_pol_rev_org_num UNIQUE (org_id, revision_num), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE data_retention_policies (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	data_category VARCHAR(50) NOT NULL, 
	retention_period_seconds INTEGER NOT NULL, 
	created_at VARCHAR(64) NOT NULL, 
	updated_at VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_retention_org_cat UNIQUE (org_id, data_category), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE data_lifecycle_requests (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	request_type VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	requested_at VARCHAR(64) NOT NULL, 
	completed_at VARCHAR(64), 
	requested_by VARCHAR(200) NOT NULL, 
	details_json TEXT NOT NULL, 
	verification_status VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE data_holds (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	data_category VARCHAR(50) NOT NULL, 
	hold_reason TEXT NOT NULL, 
	active BOOLEAN NOT NULL, 
	created_at VARCHAR(64) NOT NULL, 
	created_by VARCHAR(200) NOT NULL, 
	released_at VARCHAR(64), 
	released_by VARCHAR(200), 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE runtime_execution_requests (
	request_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	workspace_id VARCHAR(64), 
	principal_id VARCHAR(64) NOT NULL, 
	agent_id VARCHAR(64) NOT NULL, 
	identity_id VARCHAR(64) NOT NULL, 
	intent TEXT NOT NULL, 
	action_type VARCHAR(128) NOT NULL, 
	target VARCHAR(256) NOT NULL, 
	action_digest VARCHAR(64) NOT NULL, 
	target_fingerprint VARCHAR(64), 
	canonical_action_payload TEXT NOT NULL, 
	approved_arguments JSON NOT NULL, 
	observed_governance_epoch INTEGER NOT NULL, 
	idempotency_key VARCHAR(128) NOT NULL, 
	approval_id VARCHAR(36), 
	server_id VARCHAR(128), 
	lifecycle VARCHAR(16) DEFAULT 'RECORDED' NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (request_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	FOREIGN KEY(approval_id) REFERENCES governance_approvals (id) ON DELETE RESTRICT
);
CREATE TABLE enterprise_environments (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	type VARCHAR(16) NOT NULL, 
	name VARCHAR(100) NOT NULL, 
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_enterprise_environment_type CHECK (type IN ('DEVELOPMENT','STAGING','PRODUCTION')), 
	CONSTRAINT chk_enterprise_environment_status CHECK (status IN ('ACTIVE','DISABLED','DELETED')), 
	CONSTRAINT uq_enterprise_environment_org_name UNIQUE (org_id, name), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE enterprise_service_accounts (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	display_name VARCHAR(200) NOT NULL, 
	status VARCHAR(20) DEFAULT 'ACTIVE' NOT NULL, 
	role VARCHAR(20) NOT NULL, 
	created_by_user_id VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT chk_enterprise_sa_status CHECK (status IN ('ACTIVE','DISABLED','REVOKED')), 
	CONSTRAINT chk_enterprise_sa_not_owner CHECK (role <> 'OWNER'), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(created_by_user_id) REFERENCES web_users (id) ON DELETE RESTRICT
);
CREATE TABLE enterprise_security_audit (
	event_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36), 
	environment_id VARCHAR(36), 
	actor_type VARCHAR(32) NOT NULL, 
	actor_id VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	target_type VARCHAR(64) NOT NULL, 
	target_id VARCHAR(64), 
	result VARCHAR(24) NOT NULL, 
	timestamp VARCHAR(32) NOT NULL, 
	request_id VARCHAR(64), 
	metadata_json TEXT DEFAULT '{}' NOT NULL, 
	PRIMARY KEY (event_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE identity_verifications (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) DEFAULT 'UNVERIFIED' NOT NULL, 
	provider VARCHAR(64) NOT NULL, 
	provider_reference_id VARCHAR(128), 
	legal_name_encrypted TEXT, 
	country VARCHAR(2), 
	assurance_level VARCHAR(32), 
	review_status VARCHAR(32), 
	verified_at VARCHAR(32), 
	expires_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_identity_verification_status CHECK (status IN ('UNVERIFIED','BASIC_VERIFIED','IDENTITY_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE organization_verifications (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) DEFAULT 'UNVERIFIED' NOT NULL, 
	legal_name VARCHAR(300), 
	domain VARCHAR(255), 
	registration_reference VARCHAR(128), 
	accountable_owner_user_id VARCHAR(36), 
	provider VARCHAR(64), 
	provider_reference_id VARCHAR(128), 
	verified_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_org_verification_status CHECK (status IN ('UNVERIFIED','DOMAIN_VERIFIED','ORGANIZATION_VERIFIED','REVIEW_REQUIRED','REJECTED','SUSPENDED')), 
	UNIQUE (org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE, 
	FOREIGN KEY(accountable_owner_user_id) REFERENCES web_users (id) ON DELETE RESTRICT
);
CREATE TABLE passkey_credentials (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	credential_id VARCHAR(512) NOT NULL, 
	public_key TEXT NOT NULL, 
	sign_count INTEGER DEFAULT '0' NOT NULL, 
	rp_id VARCHAR(255) NOT NULL, 
	transports_json TEXT DEFAULT '[]' NOT NULL, 
	aaguid VARCHAR(64), 
	backup_eligible INTEGER, 
	backup_state INTEGER, 
	display_name VARCHAR(200) DEFAULT 'Passkey' NOT NULL, 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	last_used_at VARCHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_passkey_rp_credential UNIQUE (rp_id, credential_id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE human_totp_factors (
	user_id VARCHAR(36) NOT NULL, 
	secret_encrypted TEXT NOT NULL, 
	pending_secret_encrypted TEXT, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	last_timestep INTEGER, 
	failed_attempts INTEGER DEFAULT '0' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	confirmed_at VARCHAR(32), 
	PRIMARY KEY (user_id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE recovery_code_hashes (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	code_hash VARCHAR(64) NOT NULL, 
	generation INTEGER NOT NULL, 
	consumed_at VARCHAR(32), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_recovery_code_user_hash UNIQUE (user_id, code_hash), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE account_recovery_requests (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(32) DEFAULT 'RECOVERY_REQUESTED' NOT NULL, 
	privileged INTEGER DEFAULT '0' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	evidence_json TEXT DEFAULT '{}' NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE, 
	UNIQUE (token_hash)
);
CREATE TABLE provider_identities (
	id VARCHAR(36) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(64) NOT NULL, 
	subject VARCHAR(255) NOT NULL, 
	tenant_id VARCHAR(255), 
	hosted_domain VARCHAR(255), 
	account_kind VARCHAR(32) DEFAULT 'PERSONAL' NOT NULL, 
	email_at_link VARCHAR(254), 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_provider_identity_subject UNIQUE (provider, subject, tenant_id), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE organization_idp_bindings (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	provider VARCHAR(64) NOT NULL, 
	tenant_id VARCHAR(255), 
	issuer VARCHAR(512) NOT NULL, 
	verified_domain VARCHAR(255), 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	configured_by VARCHAR(36) NOT NULL, 
	verified_at VARCHAR(32), 
	policy_json TEXT DEFAULT '{}' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_org_idp_provider UNIQUE (org_id, provider), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE organization_sso_configs (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	protocol VARCHAR(16) NOT NULL, 
	issuer VARCHAR(512) NOT NULL, 
	client_id VARCHAR(255) NOT NULL, 
	client_secret_encrypted TEXT, 
	discovery_url VARCHAR(512), 
	jwks_url VARCHAR(512), 
	redirect_uri VARCHAR(512) NOT NULL, 
	enforcement VARCHAR(32) DEFAULT 'SSO_OPTIONAL' NOT NULL, 
	provisioning VARCHAR(32) DEFAULT 'INVITE_ONLY' NOT NULL, 
	idp_entity_id VARCHAR(512), 
	idp_sso_url VARCHAR(512), 
	idp_x509_cert TEXT, 
	created_by VARCHAR(36) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	updated_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT chk_sso_enforcement CHECK (enforcement IN ('SSO_OPTIONAL','SSO_REQUIRED')), 
	CONSTRAINT chk_sso_provisioning CHECK (provisioning IN ('INVITE_ONLY','JIT_OPT_IN')), 
	UNIQUE (org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE step_up_grants (
	id VARCHAR(36) NOT NULL, 
	grant_hash VARCHAR(64) NOT NULL, 
	user_id VARCHAR(36) NOT NULL, 
	session_id VARCHAR(64) NOT NULL, 
	action VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36), 
	assurance_required VARCHAR(32) NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	UNIQUE (grant_hash), 
	FOREIGN KEY(user_id) REFERENCES web_users (id) ON DELETE CASCADE
);
CREATE TABLE org_security_policies (
	org_id VARCHAR(36) NOT NULL, 
	phishing_resistant_required INTEGER DEFAULT '0' NOT NULL, 
	privileged_roles_json TEXT DEFAULT '["OWNER","SECURITY_ADMIN"]' NOT NULL, 
	sso_enforcement VARCHAR(32) DEFAULT 'SSO_OPTIONAL' NOT NULL, 
	dual_control_json TEXT DEFAULT '[]' NOT NULL, 
	break_glass_user_id VARCHAR(36), 
	updated_at VARCHAR(32) NOT NULL, 
	updated_by VARCHAR(36), 
	PRIMARY KEY (org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE company_domain_challenges (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	domain VARCHAR(255) NOT NULL, 
	method VARCHAR(32) NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	verified_at VARCHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT uq_company_domain_challenge UNIQUE (org_id, domain, method), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE identity_four_eyes_requests (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	requester_user_id VARCHAR(36) NOT NULL, 
	approver_user_id VARCHAR(36), 
	action VARCHAR(64) NOT NULL, 
	parameters_json TEXT NOT NULL, 
	action_digest VARCHAR(64) NOT NULL, 
	security_version VARCHAR(64), 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	created_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	approved_at VARCHAR(32), 
	consumed_at VARCHAR(32), 
	PRIMARY KEY (id), 
	CONSTRAINT chk_identity_four_eyes_status CHECK (status IN ('PENDING','APPROVED','DENIED','EXPIRED','CONSUMED','REVOKED')), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	FOREIGN KEY(requester_user_id) REFERENCES web_users (id) ON DELETE RESTRICT, 
	FOREIGN KEY(approver_user_id) REFERENCES web_users (id) ON DELETE RESTRICT
);
CREATE TABLE governance_consent_proofs (
	consent_id VARCHAR(36) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	subject_id VARCHAR(255) NOT NULL, 
	consenting_root_id VARCHAR(36) NOT NULL, 
	grantee_id VARCHAR(200) NOT NULL, 
	scope_description TEXT NOT NULL, 
	purpose TEXT NOT NULL, 
	consent_method VARCHAR(32) NOT NULL, 
	allowed_action_types TEXT DEFAULT '[]' NOT NULL, 
	allowed_targets TEXT DEFAULT '[]' NOT NULL, 
	evidence_refs TEXT NOT NULL, 
	consented_at VARCHAR(32) NOT NULL, 
	not_before VARCHAR(32), 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	revoked_by VARCHAR(200), 
	revoke_reason TEXT, 
	canonical_digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (consent_id), 
	CONSTRAINT fk_consent_root_tenant FOREIGN KEY(consenting_root_id, organization_id) REFERENCES governance_root_authority_records (root_id, organization_id) ON DELETE RESTRICT, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_identifiers (
	id VARCHAR(64) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	identifier_type VARCHAR(32) NOT NULL, 
	raw_value VARCHAR(512) NOT NULL, 
	normalized_value VARCHAR(512) NOT NULL, 
	is_primary INTEGER NOT NULL, 
	verification_state VARCHAR(32) NOT NULL, 
	verified_at VARCHAR(32), 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	source_id VARCHAR(64), 
	created_at VARCHAR(32) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_assertions (
	id VARCHAR(64) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	field_name VARCHAR(100) NOT NULL, 
	field_value TEXT NOT NULL, 
	source_id VARCHAR(64) NOT NULL, 
	source_tier VARCHAR(10) NOT NULL, 
	verification_method VARCHAR(64) NOT NULL, 
	assurance_level VARCHAR(20) NOT NULL, 
	disclosure_class VARCHAR(32) NOT NULL, 
	verified_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	last_checked_at VARCHAR(32) NOT NULL, 
	revoked_at VARCHAR(32), 
	evidence_digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_relationships (
	id VARCHAR(64) NOT NULL, 
	subject_principal_id VARCHAR(64) NOT NULL, 
	target_principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	relationship_type VARCHAR(32) NOT NULL, 
	role_title VARCHAR(100), 
	verification_state VARCHAR(32) NOT NULL, 
	valid_from VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	source_id VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(subject_principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(target_principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_authority_edges (
	id VARCHAR(64) NOT NULL, 
	grantor_principal_id VARCHAR(64) NOT NULL, 
	grantee_principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	action_type VARCHAR(100) NOT NULL, 
	resource_pattern VARCHAR(255) NOT NULL, 
	ceiling_limit_usd FLOAT, 
	currency VARCHAR(3) NOT NULL, 
	delegation_depth INTEGER NOT NULL, 
	valid_from VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32), 
	revoked_at VARCHAR(32), 
	revoked_by VARCHAR(64), 
	canonical_digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT fk_tf_auth_grantor_tenant FOREIGN KEY(grantor_principal_id, org_id) REFERENCES trust_fabric_principals (id, org_id) ON DELETE RESTRICT, 
	CONSTRAINT fk_tf_auth_grantee_tenant FOREIGN KEY(grantee_principal_id, org_id) REFERENCES trust_fabric_principals (id, org_id) ON DELETE CASCADE, 
	FOREIGN KEY(grantor_principal_id) REFERENCES trust_fabric_principals (id) ON DELETE RESTRICT, 
	FOREIGN KEY(grantee_principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_trust_roots (
	id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	root_principal_id VARCHAR(64) NOT NULL, 
	root_public_key VARCHAR(512) NOT NULL, 
	key_algorithm VARCHAR(32) NOT NULL, 
	established_at VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	canonical_digest VARCHAR(64) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (org_id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	FOREIGN KEY(root_principal_id) REFERENCES trust_fabric_principals (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_passports (
	id VARCHAR(64) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	version VARCHAR(20) NOT NULL, 
	passport_type VARCHAR(32) NOT NULL, 
	claims_json TEXT NOT NULL, 
	assurance_vector_json TEXT NOT NULL, 
	generated_at VARCHAR(32) NOT NULL, 
	expires_at VARCHAR(32) NOT NULL, 
	verification_hash VARCHAR(64) NOT NULL, 
	signature TEXT, 
	signing_key_id VARCHAR(64), 
	revoked_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE trust_fabric_conflicts (
	id VARCHAR(64) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	field_or_claim VARCHAR(100) NOT NULL, 
	assertion_id_a VARCHAR(64) NOT NULL, 
	assertion_id_b VARCHAR(64) NOT NULL, 
	conflict_type VARCHAR(32) NOT NULL, 
	detected_at VARCHAR(32) NOT NULL, 
	status VARCHAR(32) NOT NULL, 
	resolution_reason TEXT, 
	resolved_at VARCHAR(32), 
	PRIMARY KEY (id), 
	FOREIGN KEY(principal_id) REFERENCES trust_fabric_principals (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE governance_policy_activations (
	id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	revision_id VARCHAR(36) NOT NULL, 
	content_digest VARCHAR(64) NOT NULL, 
	activated_at VARCHAR(64) NOT NULL, 
	activated_by VARCHAR(200) NOT NULL, 
	governance_epoch INTEGER NOT NULL, 
	previous_activation_id VARCHAR(36), 
	is_active BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	FOREIGN KEY(revision_id) REFERENCES governance_policy_revisions (id) ON DELETE RESTRICT
);
CREATE TABLE governance_execution_authorizations (
	authorization_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	principal_id VARCHAR(64) NOT NULL, 
	agent_id VARCHAR(64) NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	action_digest VARCHAR(64) NOT NULL, 
	target_fingerprint VARCHAR(64), 
	issuer_epoch INTEGER NOT NULL, 
	expires_at DATETIME NOT NULL, 
	oneshot_authority_id VARCHAR(64) NOT NULL, 
	approval_id VARCHAR(36), 
	status VARCHAR(16) DEFAULT 'ISSUED' NOT NULL, 
	issued_at DATETIME NOT NULL, 
	consumed_at DATETIME, 
	PRIMARY KEY (authorization_id), 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	FOREIGN KEY(request_id) REFERENCES runtime_execution_requests (request_id) ON DELETE RESTRICT, 
	UNIQUE (oneshot_authority_id), 
	FOREIGN KEY(approval_id) REFERENCES governance_approvals (id) ON DELETE RESTRICT
);
CREATE TABLE runtime_execution_fences (
	request_id VARCHAR(64) NOT NULL, 
	current_generation BIGINT DEFAULT '0' NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (request_id), 
	FOREIGN KEY(request_id) REFERENCES runtime_execution_requests (request_id) ON DELETE RESTRICT
);
CREATE TABLE enterprise_service_account_environments (
	service_account_id VARCHAR(36) NOT NULL, 
	environment_id VARCHAR(36) NOT NULL, 
	org_id VARCHAR(36) NOT NULL, 
	PRIMARY KEY (service_account_id, environment_id), 
	FOREIGN KEY(service_account_id) REFERENCES enterprise_service_accounts (id) ON DELETE CASCADE, 
	FOREIGN KEY(environment_id) REFERENCES enterprise_environments (id) ON DELETE CASCADE, 
	FOREIGN KEY(org_id) REFERENCES organizations (id) ON DELETE CASCADE
);
CREATE TABLE runtime_execution_attempts (
	attempt_id VARCHAR(64) NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	authorization_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	attempt_number INTEGER NOT NULL, 
	worker_id VARCHAR(64), 
	lease_id VARCHAR(64), 
	lease_generation BIGINT, 
	state VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	effect_id VARCHAR(64) NOT NULL, 
	effect_state VARCHAR(32) DEFAULT 'NO_EFFECT' NOT NULL, 
	evidence_status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	backend_start_token_hash VARCHAR(64), 
	pre_effect_decision VARCHAR(32), 
	reconciliation_state VARCHAR(32), 
	admitted_at DATETIME, 
	backend_started_at DATETIME, 
	effect_claimed_at DATETIME, 
	completed_at DATETIME, 
	failure_code VARCHAR(64), 
	failure_reason TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (attempt_id), 
	FOREIGN KEY(request_id) REFERENCES runtime_execution_requests (request_id) ON DELETE RESTRICT, 
	FOREIGN KEY(authorization_id) REFERENCES governance_execution_authorizations (authorization_id) ON DELETE RESTRICT, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT, 
	UNIQUE (effect_id)
);
CREATE TABLE runtime_worker_leases (
	lease_id VARCHAR(64) NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	attempt_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	worker_id VARCHAR(64) NOT NULL, 
	lease_generation BIGINT NOT NULL, 
	status VARCHAR(32) DEFAULT 'ACTIVE' NOT NULL, 
	acquired_at DATETIME NOT NULL, 
	heartbeat_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	released_at DATETIME, 
	PRIMARY KEY (lease_id), 
	FOREIGN KEY(request_id) REFERENCES runtime_execution_requests (request_id) ON DELETE RESTRICT, 
	FOREIGN KEY(attempt_id) REFERENCES runtime_execution_attempts (attempt_id) ON DELETE RESTRICT, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE runtime_execution_dispatch_outbox (
	outbox_id VARCHAR(64) NOT NULL, 
	request_id VARCHAR(64) NOT NULL, 
	attempt_id VARCHAR(64) NOT NULL, 
	organization_id VARCHAR(36) NOT NULL, 
	status VARCHAR(32) DEFAULT 'PENDING' NOT NULL, 
	publisher_id VARCHAR(64), 
	claimed_at DATETIME, 
	published_at DATETIME, 
	acknowledged_at DATETIME, 
	queue_ticket_id VARCHAR(64), 
	attempt_count INTEGER NOT NULL, 
	last_error TEXT, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	PRIMARY KEY (outbox_id), 
	FOREIGN KEY(request_id) REFERENCES runtime_execution_requests (request_id) ON DELETE RESTRICT, 
	FOREIGN KEY(attempt_id) REFERENCES runtime_execution_attempts (attempt_id) ON DELETE RESTRICT, 
	FOREIGN KEY(organization_id) REFERENCES organizations (id) ON DELETE RESTRICT
);
CREATE TABLE dr_marker (id INTEGER PRIMARY KEY, note TEXT);
INSERT INTO dr_marker VALUES(1,'pre-backup');
CREATE INDEX idx_tu_provider ON token_usage (provider);
CREATE INDEX idx_tu_org ON token_usage (org_id);
CREATE INDEX idx_tu_model ON token_usage (model);
CREATE INDEX idx_tu_team ON token_usage (team);
CREATE INDEX idx_tu_recorded ON token_usage (recorded_at);
CREATE INDEX idx_ts_org ON trust_scores (org_id);
CREATE INDEX idx_ts_provider ON trust_scores (provider);
CREATE INDEX idx_ts_recorded ON trust_scores (recorded_at);
CREATE INDEX idx_ts_model ON trust_scores (model_name);
CREATE INDEX idx_org_stripe_customer ON organizations (stripe_customer_id);
CREATE INDEX idx_org_slug ON organizations (slug);
CREATE UNIQUE INDEX idx_org_paddle_customer ON organizations (paddle_customer_id);
CREATE UNIQUE INDEX idx_org_paddle_subscription ON organizations (paddle_subscription_id);
CREATE INDEX idx_mcp_calls_org ON mcp_tool_calls (org_id);
CREATE INDEX idx_mcp_calls_ts ON mcp_tool_calls (timestamp);
CREATE INDEX idx_oak_service_account ON org_api_keys (service_account_id);
CREATE INDEX idx_oak_org ON org_api_keys (org_id);
CREATE INDEX idx_oak_hash ON org_api_keys (key_hash);
CREATE INDEX idx_oak_environment ON org_api_keys (environment_id);
CREATE INDEX idx_web_users_email ON web_users (email);
CREATE INDEX idx_oauth_flow_states_expiry ON oauth_flow_states (expires_at);
CREATE INDEX idx_paddle_events_org ON paddle_webhook_events (org_id);
CREATE INDEX idx_al_timestamp ON audit_log (timestamp);
CREATE INDEX idx_al_endpoint ON audit_log (endpoint);
CREATE INDEX idx_al_org ON audit_log (org_id);
CREATE INDEX idx_er_org ON eval_runs (org_id);
CREATE INDEX idx_er_model ON eval_runs (model);
CREATE INDEX idx_er_run_type ON eval_runs (run_type);
CREATE INDEX idx_er_created_at ON eval_runs (created_at);
CREATE INDEX idx_eb_model ON eval_baselines (model);
CREATE INDEX idx_eb_org ON eval_baselines (org_id);
CREATE INDEX idx_eb_suite ON eval_baselines (suite);
CREATE INDEX idx_wc_enabled ON webhook_configs (enabled);
CREATE INDEX idx_wc_org ON webhook_configs (org_id);
CREATE INDEX idx_wd_status ON webhook_deliveries (status);
CREATE INDEX idx_wd_webhook ON webhook_deliveries (webhook_id);
CREATE INDEX idx_wd_retry ON webhook_deliveries (next_retry_at);
CREATE INDEX idx_inc_org ON incidents (org_id);
CREATE INDEX idx_inc_severity ON incidents (severity);
CREATE INDEX idx_inc_status ON incidents (status);
CREATE INDEX idx_inc_created ON incidents (created_at);
CREATE UNIQUE INDEX idx_lbm_model_provider ON leaderboard_models (model, provider);
CREATE INDEX idx_lbm_active ON leaderboard_models (active);
CREATE INDEX idx_lbr_model_provider ON leaderboard_runs (model, provider);
CREATE INDEX idx_lbr_created ON leaderboard_runs (created_at);
CREATE INDEX idx_tp_model ON trust_passports (model_name, provider);
CREATE INDEX idx_tp_org ON trust_passports (org_id);
CREATE INDEX idx_tp_certified ON trust_passports (certified);
CREATE INDEX idx_tp_generated ON trust_passports (generated_at);
CREATE INDEX idx_pir_published_at ON public_incident_reports (published_at);
CREATE INDEX idx_pir_status ON public_incident_reports (status);
CREATE INDEX idx_pir_model ON public_incident_reports (affected_model, affected_provider);
CREATE INDEX idx_pir_severity ON public_incident_reports (severity);
CREATE INDEX idx_pir_submitted ON public_incident_reports (submitted_at);
CREATE INDEX idx_gap_action ON governance_approvals (action_id);
CREATE INDEX idx_gap_status ON governance_approvals (status);
CREATE INDEX idx_gap_org ON governance_approvals (org_id);
CREATE INDEX idx_gap_requested ON governance_approvals (requested_at);
CREATE INDEX idx_gapv_approval ON governance_approval_votes (approval_id);
CREATE INDEX idx_gpol_position ON governance_policies (org_id, position);
CREATE INDEX idx_gpol_org ON governance_policies (org_id);
CREATE INDEX idx_gdel_from ON governance_delegations (org_id, from_identity_id);
CREATE INDEX idx_gdel_to ON governance_delegations (org_id, to_identity_id);
CREATE INDEX idx_gdel_org ON governance_delegations (org_id);
CREATE INDEX idx_gwr_org ON governance_workflow_rules (org_id);
CREATE INDEX idx_ums_org ON upstream_mcp_servers (org_id);
CREATE INDEX idx_tts_org ON tool_trust_scores (org_id);
CREATE INDEX idx_ci_server ON credential_issuances (server_id);
CREATE INDEX idx_ci_org ON credential_issuances (org_id);
CREATE INDEX idx_go_org ON governance_outcomes (org_id);
CREATE INDEX idx_go_evidence ON governance_outcomes (evidence_id);
CREATE INDEX idx_vp_org ON verified_principals (org_id);
CREATE INDEX idx_vp_principal ON verified_principals (principal_id);
CREATE INDEX idx_gic_agent ON governance_intent_contracts (org_id, agent_id);
CREATE INDEX idx_gic_org ON governance_intent_contracts (org_id);
CREATE INDEX idx_ap_org ON governance_authority_passports (org_id);
CREATE INDEX idx_ap_principal ON governance_authority_passports (org_id, principal_id);
CREATE INDEX idx_oar_client ON oauth_authorization_requests (client_id);
CREATE INDEX idx_oac_client ON oauth_authorization_codes (client_id);
CREATE INDEX idx_oc_family ON oauth_credentials (family_id);
CREATE INDEX idx_oc_subject ON oauth_credentials (subject_id);
CREATE INDEX idx_oc_org ON oauth_credentials (org_id);
CREATE INDEX idx_oae_org ON oauth_auth_events (org_id);
CREATE INDEX idx_oae_created ON oauth_auth_events (created_at);
CREATE INDEX idx_tf_src_org ON trust_fabric_sources (org_id);
CREATE INDEX idx_tf_src_tier ON trust_fabric_sources (source_tier);
CREATE INDEX idx_tf_fed_audience ON trust_fabric_federated_assertions (audience_org_id);
CREATE INDEX idx_tf_fed_nonce ON trust_fabric_federated_assertions (nonce);
CREATE INDEX idx_tombstone_gen ON tenant_tombstones (generation_id);
CREATE INDEX idx_tombstone_org ON tenant_tombstones (org_id);
CREATE INDEX idx_restore_rec_status ON restore_reconciliation_records (status);
CREATE INDEX idx_api_key_issuance_org ON api_key_issuance_decisions (org_id);
CREATE INDEX idx_webauthn_challenges_user ON webauthn_challenges (user_id);
CREATE INDEX idx_webauthn_challenges_expiry ON webauthn_challenges (expires_at);
CREATE INDEX idx_identity_security_notifications_user ON identity_security_notifications (user_id);
CREATE INDEX idx_identity_oauth_expiry ON identity_oauth_transactions (expires_at);
CREATE INDEX idx_dashboard_saml_expiry ON dashboard_saml_transactions (expires_at);
CREATE INDEX ix_sovereign_shadow_observations_org_id ON sovereign_shadow_observations (org_id);
CREATE INDEX idx_web_memberships_user ON web_memberships (user_id);
CREATE INDEX idx_web_memberships_org ON web_memberships (org_id);
CREATE INDEX idx_web_sessions_expires ON web_sessions (expires_at);
CREATE INDEX idx_web_sessions_user ON web_sessions (user_id);
CREATE INDEX idx_web_verification_expiry ON web_verification_tokens (expires_at);
CREATE INDEX idx_web_verification_user ON web_verification_tokens (user_id);
CREATE INDEX idx_web_identity_provider_user ON web_identity_providers (user_id);
CREATE INDEX idx_web_invitations_email ON web_invitations (email);
CREATE INDEX idx_web_invitations_org ON web_invitations (org_id);
CREATE INDEX idx_api_key_metadata_prefix ON org_api_key_metadata (prefix);
CREATE INDEX idx_stripe_events_org ON stripe_webhook_events (org_id);
CREATE INDEX idx_stripe_events_status ON stripe_webhook_events (status);
CREATE INDEX idx_gev_decision ON governance_evidence (decision);
CREATE INDEX idx_gev_recorded ON governance_evidence (recorded_at);
CREATE UNIQUE INDEX idx_gev_chain_genesis ON governance_evidence (org_id) WHERE prev_hash IS NULL;
CREATE UNIQUE INDEX idx_gev_chain_link ON governance_evidence (org_id, prev_hash) WHERE prev_hash IS NOT NULL;
CREATE INDEX idx_gev_org ON governance_evidence (org_id);
CREATE INDEX idx_gev_action ON governance_evidence (action_id);
CREATE INDEX idx_rar_org ON governance_root_authority_records (organization_id);
CREATE INDEX idx_rar_subject ON governance_root_authority_records (subject_id);
CREATE INDEX idx_rar_source ON governance_root_authority_records (authority_source);
CREATE INDEX idx_execution_nonces_consumed_at ON governance_execution_nonces (consumed_at);
CREATE INDEX idx_crypto_keys_lookup ON governance_crypto_keys (purpose, tenant_id, environment, status, version);
CREATE INDEX idx_neural_consent_subject_category ON governance_neural_consent (subject_id, category);
CREATE INDEX idx_neural_vault_subject ON governance_neural_vault_index (subject_id);
CREATE INDEX idx_neural_vault_subject_session ON governance_neural_vault_index (subject_id, session_id);
CREATE INDEX idx_tf_prin_state ON trust_fabric_principals (lifecycle_state);
CREATE INDEX idx_tf_prin_type ON trust_fabric_principals (principal_type);
CREATE INDEX idx_tf_prin_org ON trust_fabric_principals (org_id);
CREATE INDEX idx_tf_boot_nonce ON trust_fabric_bootstrap_records (nonce);
CREATE INDEX idx_tf_boot_org ON trust_fabric_bootstrap_records (org_id);
CREATE INDEX idx_tf_chal_nonce ON trust_fabric_challenges (nonce);
CREATE INDEX idx_tf_chal_org ON trust_fabric_challenges (org_id);
CREATE INDEX idx_iam_nonce_org_prin ON iam_step_up_nonces (org_id, principal_id);
CREATE INDEX idx_iam_nonce_hash ON iam_step_up_nonces (nonce_hash);
CREATE INDEX idx_iam_sess_org_prin ON iam_sessions (org_id, principal_id);
CREATE INDEX idx_iam_sess_token ON iam_sessions (token_hash);
CREATE INDEX idx_iam_key_org ON iam_api_key_lineage (org_id);
CREATE INDEX idx_iam_key_fprint ON iam_api_key_lineage (fingerprint);
CREATE INDEX idx_iam_scim_usr_org ON iam_scim_users (org_id);
CREATE INDEX idx_iam_scim_usr_name ON iam_scim_users (org_id, user_name);
CREATE INDEX idx_iam_scim_usr_ext ON iam_scim_users (org_id, external_id);
CREATE INDEX idx_iam_scim_grp_org ON iam_scim_groups (org_id);
CREATE INDEX idx_iam_jit_org_prin ON iam_jit_grants (org_id, principal_id);
CREATE INDEX idx_iam_fe_req ON iam_four_eyes_requests (requester_principal_id);
CREATE INDEX idx_iam_fe_org ON iam_four_eyes_requests (org_id);
CREATE INDEX idx_iam_bg_org ON iam_break_glass_sessions (org_id);
CREATE INDEX idx_iam_bg_inc ON iam_break_glass_sessions (incident_id);
CREATE INDEX idx_iam_rec_pol_org ON iam_recovery_policies (org_id);
CREATE INDEX idx_iam_chal_org ON iam_recovery_challenges (org_id);
CREATE INDEX idx_iam_chal_msg ON iam_recovery_challenges (challenge_message);
CREATE INDEX idx_iam_audit_ts ON iam_privileged_audit_log (recorded_at);
CREATE INDEX idx_iam_audit_org ON iam_privileged_audit_log (org_id);
CREATE INDEX idx_pol_rev_org_num ON governance_policy_revisions (org_id, revision_num);
CREATE INDEX idx_pol_rev_digest ON governance_policy_revisions (org_id, content_digest);
CREATE INDEX idx_retention_org ON data_retention_policies (org_id);
CREATE INDEX idx_lifecycle_org_status ON data_lifecycle_requests (org_id, status);
CREATE INDEX idx_holds_org_cat_active ON data_holds (org_id, data_category, active);
CREATE INDEX idx_exec_req_action_digest ON runtime_execution_requests (organization_id, action_digest);
CREATE INDEX idx_exec_req_org_created ON runtime_execution_requests (organization_id, created_at);
CREATE UNIQUE INDEX idx_exec_req_org_idempotency ON runtime_execution_requests (organization_id, idempotency_key);
CREATE INDEX idx_enterprise_env_org ON enterprise_environments (org_id);
CREATE INDEX idx_enterprise_sa_org ON enterprise_service_accounts (org_id);
CREATE INDEX idx_enterprise_audit_action ON enterprise_security_audit (action);
CREATE INDEX idx_enterprise_audit_org_ts ON enterprise_security_audit (org_id, timestamp);
CREATE INDEX idx_identity_verifications_user ON identity_verifications (user_id);
CREATE INDEX idx_identity_verifications_provider_ref ON identity_verifications (provider, provider_reference_id);
CREATE INDEX idx_passkey_user ON passkey_credentials (user_id);
CREATE INDEX idx_passkey_credential ON passkey_credentials (credential_id);
CREATE INDEX idx_recovery_codes_user ON recovery_code_hashes (user_id);
CREATE INDEX idx_account_recovery_user ON account_recovery_requests (user_id);
CREATE INDEX idx_provider_identities_user ON provider_identities (user_id);
CREATE INDEX idx_org_idp_tenant ON organization_idp_bindings (provider, tenant_id);
CREATE INDEX idx_step_up_grants_session ON step_up_grants (session_id);
CREATE INDEX idx_identity_four_eyes_requester ON identity_four_eyes_requests (requester_user_id);
CREATE INDEX idx_identity_four_eyes_org ON identity_four_eyes_requests (org_id);
CREATE INDEX idx_cp_grantee ON governance_consent_proofs (grantee_id);
CREATE INDEX idx_cp_consenting_root ON governance_consent_proofs (consenting_root_id);
CREATE INDEX idx_tf_ident_norm ON trust_fabric_identifiers (normalized_value, identifier_type);
CREATE INDEX idx_tf_ident_org ON trust_fabric_identifiers (org_id);
CREATE INDEX idx_tf_ident_prin ON trust_fabric_identifiers (principal_id);
CREATE UNIQUE INDEX idx_tf_ident_active_uniq ON trust_fabric_identifiers (org_id, identifier_type, normalized_value) WHERE revoked_at IS NULL;
CREATE INDEX idx_tf_asst_org ON trust_fabric_assertions (org_id);
CREATE INDEX idx_tf_asst_prin_field ON trust_fabric_assertions (principal_id, field_name);
CREATE INDEX idx_tf_rel_target ON trust_fabric_relationships (target_principal_id);
CREATE INDEX idx_tf_rel_subject ON trust_fabric_relationships (subject_principal_id);
CREATE INDEX idx_tf_rel_org ON trust_fabric_relationships (org_id);
CREATE INDEX idx_tf_auth_action ON trust_fabric_authority_edges (action_type);
CREATE INDEX idx_tf_auth_grantee ON trust_fabric_authority_edges (grantee_principal_id);
CREATE INDEX idx_tf_auth_org ON trust_fabric_authority_edges (org_id);
CREATE INDEX idx_tf_root_org ON trust_fabric_trust_roots (org_id);
CREATE INDEX idx_tf_pass_org ON trust_fabric_passports (org_id);
CREATE INDEX idx_tf_pass_prin ON trust_fabric_passports (principal_id);
CREATE INDEX idx_tf_conf_org ON trust_fabric_conflicts (org_id);
CREATE INDEX idx_tf_conf_prin ON trust_fabric_conflicts (principal_id);
CREATE INDEX idx_pol_act_org_active ON governance_policy_activations (org_id, is_active);
CREATE INDEX idx_exec_auth_org_status ON governance_execution_authorizations (organization_id, status);
CREATE UNIQUE INDEX idx_exec_auth_request ON governance_execution_authorizations (request_id);
CREATE UNIQUE INDEX idx_attempt_exec_number ON runtime_execution_attempts (request_id, attempt_number);
CREATE INDEX idx_attempt_auth_id ON runtime_execution_attempts (authorization_id);
CREATE UNIQUE INDEX idx_runtime_worker_leases_generation ON runtime_worker_leases (request_id, lease_generation);
CREATE INDEX idx_outbox_status_created ON runtime_execution_dispatch_outbox (status, created_at);
COMMIT;
