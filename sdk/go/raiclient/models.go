// Package raiclient provides a Go client for the ResponsibleAI Governance Platform.
package raiclient

// TrustScore holds the result of a trust score evaluation.
type TrustScore struct {
	Overall    float64            `json:"overall"`
	Grade      string             `json:"grade"`
	Dimensions map[string]float64 `json:"dimensions"`
	ModelName  string             `json:"model_name"`
	Provider   string             `json:"provider"`
	PassportID *string            `json:"passport_id,omitempty"`
}

// PIIFinding describes a single PII match found in scanned text.
type PIIFinding struct {
	Category string `json:"category"`
	Value    string `json:"value"`
	Start    int    `json:"start"`
	End      int    `json:"end"`
}

// GuardrailScan holds the result of a guardrail text scan.
type GuardrailScan struct {
	IsBlocked     bool         `json:"is_blocked"`
	PIIFindings   []PIIFinding `json:"pii_findings"`
	ToxicityScore float64      `json:"toxicity_score"`
	RedactedText  string       `json:"redacted_text"`
}

// HallucinationAnalysis holds hallucination risk assessment.
type HallucinationAnalysis struct {
	HallucinationRisk float64 `json:"hallucination_risk"`
	RiskLevel         string  `json:"risk_level"`
	HedgingScore      float64 `json:"hedging_score"`
	ConsistencyScore  float64 `json:"consistency_score"`
}

// ComplianceReport holds the result of a compliance check.
type ComplianceReport struct {
	OverallStatus string                   `json:"overall_status"`
	Score         float64                  `json:"score"`
	Frameworks    []map[string]interface{} `json:"frameworks"`
}

// CostRecord holds per-request cost tracking data.
type CostRecord struct {
	RequestID    string  `json:"request_id"`
	Provider     string  `json:"provider"`
	Model        string  `json:"model"`
	InputCostUSD float64 `json:"input_cost_usd"`
	OutputCostUSD float64 `json:"output_cost_usd"`
	TotalCostUSD float64 `json:"total_cost_usd"`
}

// EvalCompareResult holds the A/B model comparison result.
type EvalCompareResult struct {
	Winner           *string `json:"winner"`
	ScoreA           float64 `json:"score_a"`
	ScoreB           float64 `json:"score_b"`
	ModelA           string  `json:"model_a"`
	ModelB           string  `json:"model_b"`
	PromptsEvaluated int     `json:"prompts_evaluated"`
}

// HealthStatus holds the platform health check response.
type HealthStatus struct {
	Status        string                 `json:"status"`
	Version       string                 `json:"version"`
	UptimeSeconds float64                `json:"uptime_seconds"`
	Timestamp     string                 `json:"timestamp"`
	Checks        map[string]interface{} `json:"checks"`
	Modules       []string               `json:"modules"`
}

// EvaluateRequest is the request body for the evaluate endpoint.
type EvaluateRequest struct {
	ModelName   string  `json:"model_name"`
	Provider    string  `json:"provider"`
	Fairness    float64 `json:"fairness"`
	Privacy     float64 `json:"privacy"`
	Security    float64 `json:"security"`
	Robustness  float64 `json:"robustness"`
	Compliance  float64 `json:"compliance"`
	Authenticity float64 `json:"authenticity"`
	UseCase     string  `json:"use_case"`
	RecordDrift bool    `json:"record_drift"`
}

// RecordUsageRequest is the request body for the cost/record endpoint.
type RecordUsageRequest struct {
	Provider     string `json:"provider"`
	Model        string `json:"model"`
	InputTokens  int    `json:"input_tokens"`
	OutputTokens int    `json:"output_tokens"`
	Team         string `json:"team,omitempty"`
	Application  string `json:"application,omitempty"`
}
