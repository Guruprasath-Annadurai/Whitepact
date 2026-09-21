/** WhitePact Sovereign TypeScript SDK — V1 backend-aligned subset. */

export type CapabilityAvailability = "AVAILABLE" | "UNAVAILABLE" | "EXPERIMENTAL";

export type MissionDisposition =
  | "ALLOW"
  | "DENY"
  | "APPROVAL_REQUIRED"
  | "UNKNOWN"
  | "UNREACHABLE";

export type GauntletStatus = "PASS" | "FAIL" | "ERROR" | "UNAVAILABLE";

export interface SovereignStatus {
  sovereign_version: string;
  protocol_version: string;
  doctrine?: string;
}

export interface FeatureDescriptor {
  name: string;
  availability: CapabilityAvailability;
  version?: string;
}

export interface SovereignCapabilities {
  sovereign_version: string;
  protocol_version: string;
  features: FeatureDescriptor[];
}

export interface SovereignClientOptions {
  baseUrl: string;
  fetchImpl?: typeof fetch;
}

export class SovereignClient {
  constructor(private readonly options: SovereignClientOptions) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const f = this.options.fetchImpl ?? fetch;
    const res = await f(`${this.options.baseUrl}${path}`, init);
    if (!res.ok) {
      throw new Error(`Sovereign HTTP ${res.status}: ${path}`);
    }
    return (await res.json()) as T;
  }

  async status(): Promise<SovereignStatus> {
    return this.request<SovereignStatus>("/api/sovereign/status");
  }

  async capabilities(): Promise<SovereignCapabilities> {
    return this.request<SovereignCapabilities>("/api/sovereign/capabilities");
  }

  async blastRadius(body: {
    organization_id: string;
    actor_identity_id: string;
    hypothetical_extra_capabilities?: string[];
  }): Promise<Record<string, unknown>> {
    return this.request("/api/sovereign/simulate/blast-radius", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async mission(body: {
    organization_id: string;
    agent_id: string;
    steps: string[];
  }): Promise<Record<string, unknown>> {
    return this.request("/api/sovereign/simulate/mission", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async gauntlet(body: {
    organization_id: string;
    probe_ids?: string[];
  }): Promise<Record<string, unknown>> {
    return this.request("/api/sovereign/gauntlet", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }
}
