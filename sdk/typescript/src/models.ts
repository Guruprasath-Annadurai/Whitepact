/** Response models for the ResponsibleAI Governance Platform SDK. */

export interface TrustScore {
  overall: number;
  grade: string;
  dimensions: {
    fairness: number;
    privacy: number;
    security: number;
    robustness: number;
    compliance: number;
    authenticity: number;
  };
  model_name: string;
  provider: string;
  passport_id: string | null;
}

export interface PIIFinding {
  category: string;
  value: string;
  start: number;
  end: number;
}

export interface GuardrailScan {
  is_blocked: boolean;
  pii_findings: PIIFinding[];
  toxicity_score: number;
  redacted_text: string;
}

export interface HallucinationAnalysis {
  hallucination_risk: number;
  risk_level: "low" | "medium" | "high" | "critical";
  hedging_score: number;
  consistency_score: number;
}

export interface ComplianceReport {
  overall_status: string;
  score: number;
  frameworks: Array<Record<string, unknown>>;
}

export interface CostRecord {
  request_id: string;
  provider: string;
  model: string;
  input_cost_usd: number;
  output_cost_usd: number;
  total_cost_usd: number;
}

export interface EvalCompareResult {
  winner: string | null;
  score_a: number;
  score_b: number;
  model_a: string;
  model_b: string;
  prompts_evaluated: number;
}

export interface HealthStatus {
  status: "healthy" | "degraded";
  version: string;
  uptime_seconds: number;
  timestamp: string;
  checks: Record<string, unknown>;
  modules: string[];
}

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
}
