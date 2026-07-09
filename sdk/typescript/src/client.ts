/**
 * Enterprise async HTTP client for the ResponsibleAI Governance Platform.
 *
 * Features: exponential-backoff retry, per-request timeouts, org-aware auth,
 * full coverage of all REST endpoints.
 *
 * @example
 * const client = new RAIClient({ apiKey: "rai-xxx", baseUrl: "https://rai.example.com" });
 * const score = await client.evaluate({ model_name: "gpt-4o", provider: "openai" });
 * console.log(score.grade); // "B"
 */

import type {
  AIPassport,
  APIKey,
  BiasEvalRequest,
  BiasEvaluation,
  BenchmarkResult,
  BudgetStatus,
  ComplianceCheckRequest,
  ComplianceFramework,
  ComplianceReport,
  CostRecord,
  CostSummary,
  DriftCheck,
  EUAIActClassification,
  EvalCompareResult,
  EvaluateRequest,
  ExecutiveSummary,
  GuardrailScan,
  HallucinationAnalysis,
  HealthStatus,
  ISO42001GapAnalysis,
  IncidentCreateRequest,
  IncidentRecord,
  OrgContext,
  OrgStatus,
  PassportRequest,
  PIIReport,
  PolicyCheckResult,
  RecordUsageRequest,
  RoutingDecision,
  TrustHistoryEntry,
  TrustScore,
  TrustTrend,
  WebhookStatus,
} from "./models.js";

const _RETRY_STATUS = new Set([429, 502, 503, 504]);
const _API_VERSION = "v1";

export interface RAIClientOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
  maxRetries?: number;
  retryBaseMs?: number;
}

export class RAIError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly path: string,
  ) {
    super(message);
    this.name = "RAIError";
  }
}

export class RAIClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeout: number;
  private readonly maxRetries: number;
  private readonly retryBaseMs: number;

  constructor(options: RAIClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey ?? "";
    this.timeout = options.timeout ?? 30_000;
    this.maxRetries = options.maxRetries ?? 3;
    this.retryBaseMs = options.retryBaseMs ?? 500;
  }

  private url(path: string): string {
    return `${this.baseUrl}/api/${_API_VERSION}/${path.replace(/^\//, "")}`;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) h["Authorization"] = `Bearer ${this.apiKey}`;
    return h;
  }

  private sleep(ms: number): Promise<void> {
    return new Promise((r) => setTimeout(r, ms));
  }

  private jitter(base: number): number {
    return base + Math.random() * base * 0.5;
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    body?: unknown,
    params?: Record<string, string | number | boolean>,
  ): Promise<T> {
    let fullUrl = this.url(path);
    if (params && Object.keys(params).length > 0) {
      const qs = new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)]),
      );
      fullUrl += `?${qs.toString()}`;
    }

    let lastError: Error | null = null;

    for (let attempt = 0; attempt < this.maxRetries; attempt++) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), this.timeout);

      try {
        const res = await fetch(fullUrl, {
          method,
          headers: this.headers(),
          body: body !== undefined ? JSON.stringify(body) : undefined,
          signal: controller.signal,
        });

        if (_RETRY_STATUS.has(res.status) && attempt < this.maxRetries - 1) {
          const retryAfter = res.headers.get("Retry-After");
          const waitMs = retryAfter
            ? parseInt(retryAfter, 10) * 1000
            : this.jitter(this.retryBaseMs * 2 ** attempt);
          await this.sleep(waitMs);
          continue;
        }

        if (!res.ok) {
          const text = await res.text().catch(() => "");
          throw new RAIError(
            `${method} ${path} failed [${res.status}]: ${text}`,
            res.status,
            path,
          );
        }

        return res.json() as Promise<T>;
      } catch (err) {
        if (err instanceof RAIError) throw err;
        lastError = err as Error;
        if (attempt < this.maxRetries - 1) {
          await this.sleep(this.jitter(this.retryBaseMs * 2 ** attempt));
        }
      } finally {
        clearTimeout(timer);
      }
    }

    throw lastError ?? new RAIError("Max retries exceeded", 0, path);
  }

  private post<T>(path: string, body: unknown): Promise<T> {
    return this.request<T>("POST", path, body);
  }

  private get<T>(path: string, params?: Record<string, string | number | boolean>): Promise<T> {
    return this.request<T>("GET", path, undefined, params);
  }

  // ── Health ──────────────────────────────────────────────────────────────────

  health(): Promise<HealthStatus> {
    return this.get<HealthStatus>("health");
  }

  // ── Trust Scoring ───────────────────────────────────────────────────────────

  evaluate(req: EvaluateRequest): Promise<TrustScore> {
    return this.post<TrustScore>("evaluate", {
      fairness: 0.75,
      privacy: 0.80,
      security: 0.70,
      robustness: 0.75,
      compliance: 0.80,
      authenticity: 0.85,
      use_case: "general",
      record_drift: true,
      ...req,
    });
  }

  trustHistory(
    modelName: string,
    provider: string,
    days = 30,
  ): Promise<TrustHistoryEntry[]> {
    return this.get<TrustHistoryEntry[]>("trust/history", {
      model_name: modelName,
      provider,
      days,
    });
  }

  trustTrend(modelName: string, provider: string): Promise<TrustTrend> {
    return this.get<TrustTrend>("trust/trend", {
      model_name: modelName,
      provider,
    });
  }

  listModels(): Promise<Array<{ model_name: string; provider: string; latest_grade: string }>> {
    return this.get("trust/models");
  }

  // ── Guardrails ──────────────────────────────────────────────────────────────

  scan(text: string, redact = true): Promise<GuardrailScan> {
    return this.post<GuardrailScan>("guardrails/scan", { text, redact });
  }

  // ── Hallucination ───────────────────────────────────────────────────────────

  analyzeHallucination(
    text: string,
    candidates?: string[],
  ): Promise<HallucinationAnalysis> {
    return this.post<HallucinationAnalysis>("hallucination/analyze", {
      text,
      candidates,
    });
  }

  // ── Compliance ──────────────────────────────────────────────────────────────

  complianceCheck(req: ComplianceCheckRequest): Promise<ComplianceReport> {
    return this.post<ComplianceReport>("compliance/check", req);
  }

  euAiActClassify(params: {
    system_description: string;
    deployment_sector: string;
    affects_natural_persons?: boolean;
    is_fully_automated?: boolean;
    processes_biometric_data?: boolean;
    used_for_emotion_recognition?: boolean;
    real_time_remote_biometric?: boolean;
    social_scoring_purpose?: boolean;
    trust_score_overall?: number;
  }): Promise<EUAIActClassification> {
    return this.post<EUAIActClassification>("compliance/eu-ai-act", params);
  }

  iso42001Gap(params: {
    org_name?: string;
    has_ai_policy?: boolean;
    has_risk_assessment?: boolean;
    has_impact_assessment?: boolean;
    has_data_governance?: boolean;
    has_training_programme?: boolean;
    has_audit_trail?: boolean;
    has_incident_process?: boolean;
    has_supplier_controls?: boolean;
    has_monitoring_metrics?: boolean;
    has_continual_improvement?: boolean;
    trust_score_overall?: number;
    compliance_maturity?: number;
  }): Promise<ISO42001GapAnalysis> {
    return this.post<ISO42001GapAnalysis>("compliance/iso42001-gap", params);
  }

  // ── Cost ────────────────────────────────────────────────────────────────────

  recordUsage(req: RecordUsageRequest): Promise<CostRecord> {
    return this.post<CostRecord>("cost/record", {
      team: "default",
      application: "default",
      ...req,
    });
  }

  costSummary(days = 30): Promise<CostSummary> {
    return this.get<CostSummary>("cost/summary", { days });
  }

  budgetStatus(orgId?: string): Promise<BudgetStatus> {
    return this.get<BudgetStatus>("billing/usage", orgId ? { org_id: orgId } : {});
  }

  modelRoute(
    taskDescription: string,
    qualityRequirement: "maximum" | "balanced" | "cheapest" = "balanced",
  ): Promise<RoutingDecision> {
    return this.post<RoutingDecision>("cost/route", {
      task_description: taskDescription,
      quality_requirement: qualityRequirement,
    });
  }

  // ── Model Evaluation ────────────────────────────────────────────────────────

  compareModels(
    modelA: string,
    modelB: string,
    prompts: Array<Record<string, string>>,
    responsesA: Array<Record<string, string>>,
    responsesB: Array<Record<string, string>>,
    providerA = "unknown",
    providerB = "unknown",
  ): Promise<EvalCompareResult> {
    return this.post<EvalCompareResult>("eval/compare", {
      model_a: modelA,
      model_b: modelB,
      provider_a: providerA,
      provider_b: providerB,
      prompts,
      responses_a: responsesA,
      responses_b: responsesB,
    });
  }

  runBenchmark(
    modelName: string,
    provider: string,
    suite: "truthfulqa" | "bbq" | "hellaswag",
    responses: Record<string, string>,
  ): Promise<BenchmarkResult> {
    return this.post<BenchmarkResult>("eval/benchmark", {
      model_name: modelName,
      provider,
      suite,
      responses,
    });
  }

  // ── Bias ────────────────────────────────────────────────────────────────────

  biasEvaluate(req: BiasEvalRequest): Promise<BiasEvaluation> {
    return this.post<BiasEvaluation>("bias/evaluate", req);
  }

  // ── Drift ───────────────────────────────────────────────────────────────────

  driftCheck(
    modelName: string,
    provider: string,
    baselineScore: Partial<Record<string, number>>,
    currentScore: Partial<Record<string, number>>,
    alertThreshold = 5.0,
  ): Promise<DriftCheck> {
    return this.post<DriftCheck>("drift/check", {
      model_name: modelName,
      provider,
      baseline_score: baselineScore,
      current_score: currentScore,
      alert_threshold: alertThreshold,
    });
  }

  driftAlerts(days = 7): Promise<DriftCheck[]> {
    return this.get<DriftCheck[]>("drift/alerts", { days });
  }

  // ── AI Passport ──────────────────────────────────────────────────────────────

  generatePassport(req: PassportRequest): Promise<AIPassport> {
    return this.post<AIPassport>("passport/generate", req);
  }

  verifyPassport(
    passportId: string,
    verificationHash: string,
  ): Promise<{ valid: boolean; passport_id: string; message: string }> {
    return this.post("passport/verify", {
      passport_id: passportId,
      verification_hash: verificationHash,
    });
  }

  // ── PII ──────────────────────────────────────────────────────────────────────

  piiReport(
    texts: string[],
    context = "general",
    redact = false,
  ): Promise<PIIReport> {
    return this.post<PIIReport>("privacy/pii-report", { texts, context, redact });
  }

  // ── Policy ───────────────────────────────────────────────────────────────────

  policyCheck(
    text: string,
    policy: {
      blocked_topics?: string[];
      required_disclaimers?: string[];
      max_length_chars?: number;
      blocked_keywords?: string[];
      require_pii_clean?: boolean;
    },
  ): Promise<PolicyCheckResult> {
    return this.post<PolicyCheckResult>("policy/check", { text, policy });
  }

  // ── Incidents ─────────────────────────────────────────────────────────────────

  logIncident(req: IncidentCreateRequest): Promise<IncidentRecord> {
    return this.post<IncidentRecord>("incidents", req);
  }

  listIncidents(params?: {
    status?: "OPEN" | "MITIGATED";
    severity?: string;
    days?: number;
  }): Promise<IncidentRecord[]> {
    return this.get<IncidentRecord[]>("incidents", params ?? {});
  }

  // ── Executive / Org ───────────────────────────────────────────────────────────

  executiveSummary(period = "current"): Promise<ExecutiveSummary> {
    return this.get<ExecutiveSummary>("org/executive-summary", { period });
  }

  orgStatus(): Promise<OrgStatus> {
    return this.get<OrgStatus>("org/status");
  }

  // ── Webhooks ──────────────────────────────────────────────────────────────────

  webhookStatus(): Promise<WebhookStatus> {
    return this.get<WebhookStatus>("webhooks/status");
  }

  listWebhooks(): Promise<Array<Record<string, unknown>>> {
    return this.get("webhooks");
  }

  createWebhook(config: {
    url: string;
    events: string[];
    secret?: string;
  }): Promise<Record<string, unknown>> {
    return this.post("webhooks", config);
  }

  deleteWebhook(webhookId: string): Promise<void> {
    return this.request("POST", `webhooks/${webhookId}/disable`, {});
  }

  // ── API Key / Org Management ──────────────────────────────────────────────────

  listApiKeys(): Promise<APIKey[]> {
    return this.get<APIKey[]>("org/keys");
  }

  createApiKey(name: string, role: APIKey["role"]): Promise<{ key: string } & APIKey> {
    return this.post("org/keys", { name, role });
  }

  revokeApiKey(keyId: string): Promise<void> {
    return this.post(`org/keys/${keyId}/revoke`, {});
  }

  whoAmI(): Promise<OrgContext> {
    return this.get<OrgContext>("org/whoami");
  }
}
