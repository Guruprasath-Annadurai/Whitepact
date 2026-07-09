/** Response models for the ResponsibleAI Governance Platform SDK. */

// ── Trust ─────────────────────────────────────────────────────────────────────

export interface TrustDimensions {
  fairness: number;
  privacy: number;
  security: number;
  robustness: number;
  compliance: number;
  authenticity: number;
}

export interface TrustScore {
  overall: number;
  grade: "A" | "B" | "C" | "D" | "F";
  risk_level: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  passed: boolean;
  dimensions: TrustDimensions;
  model_name: string;
  provider: string;
  passport_id: string | null;
}

export interface TrustHistoryEntry {
  timestamp: string;
  overall: number;
  grade: string;
  model_name: string;
  provider: string;
}

export interface TrustTrend {
  model_name: string;
  provider: string;
  direction: "improving" | "degrading" | "stable";
  delta: number;
  data_points: number;
}

// ── Guardrails ────────────────────────────────────────────────────────────────

export interface PIIFinding {
  category: string;
  value?: string;
  match?: string;
  start: number;
  end: number;
}

export interface ToxicityFinding {
  category: string;
  match: string;
}

export interface GuardrailScan {
  is_blocked: boolean;
  has_pii: boolean;
  has_toxicity: boolean;
  pii_findings: PIIFinding[];
  toxicity_findings: ToxicityFinding[];
  block_reasons: string[];
  redacted_text: string | null;
  toxicity_score?: number;
}

// ── Hallucination ─────────────────────────────────────────────────────────────

export interface HallucinationAnalysis {
  hallucination_risk: number;
  risk_level: "low" | "medium" | "high" | "critical";
  hedging_score: number;
  consistency_score: number;
  unsupported_claims: string[];
}

// ── Compliance ────────────────────────────────────────────────────────────────

export type ComplianceFramework = "NIST_AI_RMF" | "EU_AI_ACT" | "ISO_42001";

export interface ComplianceFinding {
  control_id: string;
  description: string;
  status: "PASS" | "FAIL" | "PARTIAL";
  score: number;
  remediation?: string;
}

export interface ComplianceReport {
  overall_status: "COMPLIANT" | "PARTIALLY_COMPLIANT" | "NON_COMPLIANT";
  score: number;
  framework: string;
  findings: ComplianceFinding[];
  frameworks?: Array<Record<string, unknown>>;
}

// ── Cost ──────────────────────────────────────────────────────────────────────

export interface CostRecord {
  request_id: string;
  provider: string;
  model: string;
  team: string;
  application: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
  timestamp: string;
}

export interface CostSummary {
  total_cost_usd: number;
  total_tokens: number;
  request_count: number;
  model_breakdown: Record<string, number>;
  team_breakdown: Record<string, number>;
  daily_costs?: Array<{ date: string; cost_usd: number }>;
}

export interface BudgetStatus {
  status: "OK" | "WARNING" | "CRITICAL" | "EXCEEDED";
  total_spent_usd: number;
  monthly_limit_usd: number;
  percentage_used: number;
  is_exceeded: boolean;
  alert_triggered: boolean;
  projection: {
    daily_rate_usd: number;
    projected_month_end_usd: number;
    projected_overage_usd: number;
    days_remaining: number;
    remaining_budget_usd: number;
  };
  top_teams_by_spend: Array<{ team: string; spent_usd: number }>;
  top_models_by_spend: Array<{ model: string; spent_usd: number }>;
  recommendation: string;
}

// ── Model Eval ────────────────────────────────────────────────────────────────

export interface EvalCompareResult {
  winner: string | null;
  winner_provider: string;
  score_gap: number;
  model_a: Record<string, unknown>;
  model_b: Record<string, unknown>;
  delta: Record<string, number>;
  recommendation: string;
}

export interface RoutingDecision {
  complexity: string;
  recommended_model: string;
  alternative_model: string;
  estimated_cost_per_1k_tokens_usd: number;
  estimated_savings_vs_gpt4o_usd: number;
  reasoning: string;
  provider_comparison?: Array<Record<string, unknown>>;
}

export interface BenchmarkResult {
  model: string;
  provider: string;
  suite: string;
  accuracy: number;
  bias_rate: number;
  total_samples: number;
  passed_samples: number;
  sample_results?: Array<Record<string, unknown>>;
}

// ── Bias ──────────────────────────────────────────────────────────────────────

export interface BiasProbeResult {
  bias_score: number;
  confidence_interval: [number, number];
  length_asymmetry: number;
  toxicity_divergence: number;
  vocabulary_divergence: number;
  passed: boolean;
  threshold: number;
  responses_evaluated: number;
}

export interface BiasEvaluation {
  model_name: string;
  provider: string;
  overall_bias_score: number;
  overall_passed: boolean;
  threshold: number;
  probe_results: Record<string, BiasProbeResult>;
  probes_evaluated: number;
  probes_failed: number;
  intersectional_amplification: boolean;
  interpretation: "MINIMAL" | "LOW" | "MODERATE" | "HIGH" | "SEVERE";
}

// ── Drift ─────────────────────────────────────────────────────────────────────

export interface DriftCheck {
  model_name: string;
  provider: string;
  overall_delta: number;
  severity: "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  alert_triggered: boolean;
  alert_threshold: number;
  direction: "improving" | "degrading" | "stable";
  dimension_drift: Record<string, number>;
  worst_dimensions: Array<{ dimension: string; delta: number }>;
  recommendation: string;
}

// ── AI Passport ───────────────────────────────────────────────────────────────

export interface AIPassport {
  passport_id: string;
  model_name: string;
  provider: string;
  generated_at: string;
  verification_hash: string;
  trust_score: TrustScore;
  bias_summary: Record<string, unknown>;
  hallucination_summary: Record<string, unknown>;
  security_summary: Record<string, unknown>;
  compliance_summary: Record<string, unknown>;
  privacy_summary: Record<string, unknown>;
  use_case: string;
  mcp_generated: boolean;
  verify_instructions: string;
}

// ── Incident ──────────────────────────────────────────────────────────────────

export type IncidentType =
  | "pii_leak"
  | "jailbreak_attempt"
  | "bias_trigger"
  | "hallucination"
  | "policy_violation"
  | "cost_overrun"
  | "drift_alert"
  | "other";

export type IncidentSeverity = "low" | "medium" | "high" | "critical";

export interface IncidentRecord {
  incident_id: string;
  created_at: string;
  incident_type: IncidentType;
  severity: IncidentSeverity;
  siem_event_type: string;
  model_name: string;
  provider: string;
  description: string;
  mitigated: boolean;
  evidence_hash: string;
  status: "OPEN" | "MITIGATED";
  sla_resolution_hours: number;
  next_steps: string;
  siem_payload: Record<string, unknown>;
}

// ── EU AI Act ─────────────────────────────────────────────────────────────────

export type EUAIActRiskTier = "UNACCEPTABLE" | "HIGH" | "LIMITED" | "MINIMAL";

export interface EUAIActClassification {
  risk_tier: EUAIActRiskTier;
  deployment_sector: string;
  system_description: string;
  applicable_articles: string[];
  conformity_assessment: string;
  required_actions: string[];
  enforcement_date: string;
  penalties: Record<string, string>;
  input_flags: Record<string, boolean | number>;
}

// ── ISO 42001 ─────────────────────────────────────────────────────────────────

export interface ISO42001GapAnalysis {
  org_name: string;
  standard: string;
  maturity_percentage: number;
  clauses_met: number;
  clauses_total: number;
  gap_count: number;
  certification_ready: boolean;
  estimated_remediation_months: number;
  met_clauses: Array<{ id: string; name: string }>;
  gap_findings: Array<{ clause_id: string; clause_name: string; status: string; remediation: string }>;
  priority_actions: string[];
  certification_path: string;
}

// ── Executive Summary ─────────────────────────────────────────────────────────

export type RAGStatus = "GREEN" | "AMBER" | "RED";

export interface ExecutiveSummary {
  org_name: string;
  report_period: string;
  generated_at: string;
  overall_posture: "STRONG" | "ADEQUATE" | "AT RISK";
  executive_headline: string;
  rag_dashboard: Record<string, { status: RAGStatus; value: string }>;
  key_metrics: Record<string, number | string | string[]>;
  top_risks: string[];
  recommended_board_actions: string[];
}

// ── Org Status ────────────────────────────────────────────────────────────────

export interface OrgStatus {
  org_name: string;
  snapshot_time: string;
  health_status: "HEALTHY" | "DEGRADED" | "AT_RISK";
  models: {
    total: number;
    grade_distribution: Record<string, number>;
    passing: number;
    failing: number;
    models: Record<string, string>;
  };
  compliance: {
    active_frameworks: string[];
    framework_count: number;
  };
  operations: {
    open_incidents: number;
    drift_alerts: number;
    budget_pct_used: number;
    budget_status: string;
  };
  mcp_capabilities: {
    tools_available: number;
    version: string;
  };
}

// ── Webhook Status ────────────────────────────────────────────────────────────

export interface WebhookStatus {
  health_status: "HEALTHY" | "DEGRADED" | "UNHEALTHY";
  health_grade: "A" | "B" | "C" | "D" | "F";
  delivery_stats: {
    total: number;
    successful: number;
    failed: number;
    success_rate_pct: number;
    avg_latency_ms: number;
  };
  dead_letter_queue: {
    count: number;
    status: "EMPTY" | "WARNING" | "CRITICAL";
    action_required: boolean;
  };
  endpoint_count: number;
  problematic_endpoints: Array<Record<string, unknown>>;
  recommendations: string[];
}

// ── PII Report ────────────────────────────────────────────────────────────────

export interface PIIReport {
  context: string;
  documents_scanned: number;
  documents_with_pii: number;
  pct_documents_with_pii: number;
  total_pii_findings: number;
  privacy_risk_level: "NONE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  category_breakdown: Record<string, number>;
  gdpr_relevant_categories: string[];
  applicable_gdpr_articles: string[];
  remediation: Record<string, string>;
  document_results: Array<Record<string, unknown>>;
}

// ── Policy Check ──────────────────────────────────────────────────────────────

export interface PolicyViolation {
  rule: string;
  value: unknown;
  message: string;
  remediation: string;
}

export interface PolicyCheckResult {
  passed: boolean;
  violations: PolicyViolation[];
  violation_count: number;
  passed_rules: string[];
  text_length: number;
}

// ── Health ────────────────────────────────────────────────────────────────────

export interface HealthStatus {
  status: "healthy" | "degraded";
  version: string;
  uptime_seconds: number;
  timestamp: string;
  checks: Record<string, unknown>;
  modules: string[] | Record<string, string>;
}

// ── Org / API Key Management ──────────────────────────────────────────────────

export interface APIKey {
  key_id: string;
  name: string;
  role: "OWNER" | "ADMIN" | "ANALYST" | "VIEWER";
  created_at: string;
  last_used?: string;
}

export interface OrgContext {
  org_id: string;
  org_name: string;
  role: string;
  key_id: string;
  is_legacy: boolean;
}

// ── Request types ─────────────────────────────────────────────────────────────

export interface EvaluateRequest {
  model_name: string;
  provider: string;
  fairness?: number;
  privacy?: number;
  security?: number;
  robustness?: number;
  compliance?: number;
  authenticity?: number;
  use_case?: string;
  record_drift?: boolean;
}

export interface RecordUsageRequest {
  provider: string;
  model: string;
  input_tokens: number;
  output_tokens: number;
  team?: string;
  application?: string;
  prompt?: string;
}

export interface ScanRequest {
  text: string;
  redact?: boolean;
}

export interface ComplianceCheckRequest {
  model_name: string;
  provider: string;
  use_case?: string;
  frameworks?: ComplianceFramework[];
}

export interface BiasEvalRequest {
  model_name: string;
  provider: string;
  probe_responses: Partial<Record<
    "gender" | "racial" | "age" | "religious" | "occupational" | "cultural",
    string[]
  >>;
  threshold?: number;
}

export interface IncidentCreateRequest {
  incident_type: IncidentType;
  severity: IncidentSeverity;
  model_name?: string;
  provider?: string;
  description: string;
  evidence?: Record<string, unknown>;
  mitigated?: boolean;
}

export interface PassportRequest {
  model_name: string;
  provider: string;
  trust_dimensions: Partial<TrustDimensions>;
  use_case?: string;
  bias_summary?: Record<string, unknown>;
  security_summary?: Record<string, unknown>;
  compliance_summary?: Record<string, unknown>;
  privacy_summary?: Record<string, unknown>;
  hallucination_summary?: Record<string, unknown>;
}
