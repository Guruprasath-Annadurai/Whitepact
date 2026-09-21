import {
  retryClass,
  SAFE_GET_MAX_ATTEMPTS,
  type RetryClass,
} from "./retry.js";
import type {
  AuthorityCompareRequest,
  BlastRadiusRequest,
  CapsuleBodyRequest,
  CapsuleCreateRequest,
  EvidenceCorrelateRequest,
  ExplainRequest,
  FeatureDescriptor,
  FlightRecorderRequest,
  GauntletRequest,
  MissionRequest,
  OrgRequest,
  PolicyRulesRequest,
  PolicySimulateRequest,
  PolicyTestRequest,
  ShadowRequest,
  CapabilityAvailability,
  SovereignCapabilities,
  SovereignHttpResult,
  SovereignStatus,
  TimeMachineRequest,
  TraceRequest,
} from "./types.js";

export type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

export class SovereignClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetchImpl: FetchFn = fetch,
  ) {}

  getRetryClass(operation: string): RetryClass {
    return retryClass(operation);
  }

  private async get<T>(
    path: string,
    operation: string,
  ): Promise<SovereignHttpResult<T>> {
    const klass = retryClass(operation);
    const attempts =
      klass === "SAFE_TO_RETRY" ? SAFE_GET_MAX_ATTEMPTS : 1;
    let lastError: unknown;
    for (let i = 0; i < attempts; i++) {
      try {
        const res = await this.fetchImpl(`${this.baseUrl}${path}`);
        if (res.status === 501) {
          return { ok: false, status: res.status, disposition: "UNAVAILABLE" };
        }
        if (!res.ok) {
          return { ok: false, status: res.status, disposition: "ERROR" };
        }
        return { ok: true, data: (await res.json()) as T };
      } catch (err) {
        lastError = err;
        if (klass !== "SAFE_TO_RETRY" || i === attempts - 1) {
          return { ok: false, status: 0, disposition: "ERROR" };
        }
      }
    }
    return { ok: false, status: 0, disposition: "ERROR" };
  }

  private async post<T>(
    path: string,
    body: unknown,
    operation: string,
  ): Promise<SovereignHttpResult<T>> {
    if (retryClass(operation) === "NEVER_BLINDLY_RETRY") {
      return this.postOnce<T>(path, body);
    }
    return this.postOnce<T>(path, body);
  }

  private async postOnce<T>(
    path: string,
    body: unknown,
  ): Promise<SovereignHttpResult<T>> {
    try {
      const res = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.status === 501) {
        return { ok: false, status: res.status, disposition: "UNAVAILABLE" };
      }
      if (!res.ok) {
        return { ok: false, status: res.status, disposition: "ERROR" };
      }
      return { ok: true, data: (await res.json()) as T };
    } catch {
      return { ok: false, status: 0, disposition: "ERROR" };
    }
  }

  async status(): Promise<SovereignHttpResult<SovereignStatus>> {
    return this.get("/api/sovereign/status", "status");
  }

  async capabilities(): Promise<SovereignHttpResult<SovereignCapabilities>> {
    return this.get("/api/sovereign/capabilities", "capabilities");
  }

  async xray(body: OrgRequest): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/xray", body, "xray");
  }

  async explain(
    body: ExplainRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/explain", body, "explain");
  }

  async trace(body: TraceRequest): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/trace", body, "trace");
  }

  async authorityEffective(
    body: OrgRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/authority/effective", body, "effective");
  }

  async authorityCompare(
    body: AuthorityCompareRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/authority/compare", body, "compare");
  }

  async authorityDrift(
    body: AuthorityCompareRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/authority/drift", body, "drift");
  }

  async blastRadius(
    body: BlastRadiusRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/simulate/blast-radius", body, "simulate_blast_radius");
  }

  async mission(
    body: MissionRequest,
  ): Promise<SovereignHttpResult<{ steps: Array<{ disposition: string }> }>> {
    return this.post("/api/sovereign/simulate/mission", body, "simulate_mission");
  }

  async shadow(body: ShadowRequest): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/shadow", body, "shadow");
  }

  async policyLint(
    body: PolicyRulesRequest,
  ): Promise<SovereignHttpResult<{ errors: string[] }>> {
    return this.post("/api/sovereign/policy/lint", body, "policy_lint");
  }

  /** Structural rule validation — same backend route as policyLint. */
  async policyValidate(
    body: PolicyRulesRequest,
  ): Promise<SovereignHttpResult<{ errors: string[] }>> {
    return this.policyLint(body);
  }

  async policyTest(
    body: PolicyTestRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/policy/test", body, "policy_test");
  }

  async policyDiff(
    body: PolicyRulesRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/policy/diff", body, "policy_diff");
  }

  async policySimulate(
    body: PolicySimulateRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/policy/simulate", body, "policy_simulate");
  }

  async gauntlet(
    body: GauntletRequest,
  ): Promise<SovereignHttpResult<{ cases: Array<{ status: string }> }>> {
    return this.post("/api/sovereign/gauntlet", body, "gauntlet");
  }

  async flightRecorder(
    body: FlightRecorderRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/flight-recorder", body, "flight_recorder");
  }

  async timeMachine(
    body: TimeMachineRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/time-machine", body, "time_machine");
  }

  async evidenceCorrelate(
    body: EvidenceCorrelateRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/evidence/correlate", body, "evidence_correlate");
  }

  async capsuleCreate(
    body: CapsuleCreateRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/capsules", body, "capsule_create");
  }

  async capsuleValidate(
    body: CapsuleBodyRequest,
  ): Promise<SovereignHttpResult<{ valid: boolean }>> {
    return this.post("/api/sovereign/capsules/validate", body, "capsule_validate");
  }

  /** Inspect capsule integrity via validate (no separate GET route in V1). */
  async capsuleInspect(
    body: CapsuleBodyRequest,
  ): Promise<SovereignHttpResult<{ valid: boolean }>> {
    return this.capsuleValidate(body);
  }

  async capsuleReproduce(
    body: CapsuleBodyRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/capsules/reproduce", body, "capsule_reproduce");
  }

  async authorityBom(
    body: OrgRequest,
  ): Promise<SovereignHttpResult<Record<string, unknown>>> {
    return this.post("/api/sovereign/authority-bom", body, "authority_bom");
  }

  /** Returns negotiated feature if capabilities call succeeds. */
  async featureAvailability(
    featureName: string,
  ): Promise<SovereignHttpResult<CapabilityAvailability | "UNKNOWN">> {
    const caps = await this.capabilities();
    if (!caps.ok) {
      return caps;
    }
    const feat = caps.data.features.find((f: FeatureDescriptor) => f.name === featureName);
    if (!feat) {
      return { ok: true, data: "UNKNOWN" };
    }
    return { ok: true, data: feat.availability };
  }
}

export type { CapabilityAvailability } from "./types.js";
