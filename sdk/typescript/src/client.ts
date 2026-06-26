/**
 * Async HTTP client for the ResponsibleAI Governance Platform.
 *
 * Uses the Fetch API (Node 18+ / browser native).
 *
 * @example
 * const client = new RAIClient({ apiKey: "rai-xxx", baseUrl: "https://rai.example.com" });
 * const score = await client.evaluate({ model_name: "gpt-4o", provider: "openai", fairness: 0.85 });
 * console.log(score.grade);
 */

import type {
  ComplianceReport,
  CostRecord,
  EvalCompareResult,
  EvaluateRequest,
  GuardrailScan,
  HallucinationAnalysis,
  HealthStatus,
  RecordUsageRequest,
  TrustScore,
} from "./models.js";

const API_VERSION = "v1";

export interface RAIClientOptions {
  apiKey?: string;
  baseUrl?: string;
  timeout?: number;
}

export class RAIClient {
  private readonly baseUrl: string;
  private readonly apiKey: string;
  private readonly timeout: number;

  constructor(options: RAIClientOptions = {}) {
    this.baseUrl = (options.baseUrl ?? "http://localhost:8765").replace(/\/$/, "");
    this.apiKey = options.apiKey ?? "";
    this.timeout = options.timeout ?? 30_000;
  }

  private url(path: string): string {
    return `${this.baseUrl}/api/${API_VERSION}/${path.replace(/^\//, "")}`;
  }

  private headers(): Record<string, string> {
    const h: Record<string, string> = { "Content-Type": "application/json" };
    if (this.apiKey) h["Authorization"] = `Bearer ${this.apiKey}`;
    return h;
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const res = await fetch(this.url(path), {
        method: "POST",
        headers: this.headers(),
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`RAIClient POST ${path} failed [${res.status}]: ${text}`);
      }
      return res.json() as Promise<T>;
    } finally {
      clearTimeout(timer);
    }
  }

  private async get<T>(path: string, params?: Record<string, string | number>): Promise<T> {
    let fullPath = this.url(path);
    if (params && Object.keys(params).length > 0) {
      const qs = new URLSearchParams(
        Object.entries(params).map(([k, v]) => [k, String(v)])
      );
      fullPath += `?${qs.toString()}`;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeout);
    try {
      const res = await fetch(fullPath, { headers: this.headers(), signal: controller.signal });
      if (!res.ok) {
        const text = await res.text().catch(() => "");
        throw new Error(`RAIClient GET ${path} failed [${res.status}]: ${text}`);
      }
      return res.json() as Promise<T>;
    } finally {
      clearTimeout(timer);
    }
  }

  // ── Trust Scoring ───────────────────────────────────────────────────────────

  async evaluate(req: EvaluateRequest): Promise<TrustScore> {
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

  // ── Guardrails ──────────────────────────────────────────────────────────────

  async scan(text: string): Promise<GuardrailScan> {
    return this.post<GuardrailScan>("guardrails/scan", { text });
  }

  // ── Hallucination ───────────────────────────────────────────────────────────

  async analyzeHallucination(text: string, candidates?: string[]): Promise<HallucinationAnalysis> {
    return this.post<HallucinationAnalysis>("hallucination/analyze", { text, candidates });
  }

  // ── Compliance ──────────────────────────────────────────────────────────────

  async complianceCheck(
    modelName: string,
    provider: string,
    useCase = "general",
    frameworks?: string[]
  ): Promise<ComplianceReport> {
    return this.post<ComplianceReport>("compliance/check", {
      model_name: modelName,
      provider,
      use_case: useCase,
      ...(frameworks ? { frameworks } : {}),
    });
  }

  // ── Cost ────────────────────────────────────────────────────────────────────

  async recordUsage(req: RecordUsageRequest): Promise<CostRecord> {
    return this.post<CostRecord>("cost/record", {
      team: "default",
      application: "default",
      ...req,
    });
  }

  async costSummary(days = 30): Promise<Record<string, unknown>> {
    return this.get<Record<string, unknown>>("cost/summary", { days });
  }

  // ── Model Evaluation ────────────────────────────────────────────────────────

  async compareModels(
    modelA: string,
    modelB: string,
    prompts: Array<Record<string, string>>,
    responsesA: Array<Record<string, string>>,
    responsesB: Array<Record<string, string>>,
    providerA = "unknown",
    providerB = "unknown"
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

  // ── Health ──────────────────────────────────────────────────────────────────

  async health(): Promise<HealthStatus> {
    return this.get<HealthStatus>("health");
  }
}
