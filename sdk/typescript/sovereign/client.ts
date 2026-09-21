import type { CapabilityAvailability, GauntletStatus, MissionDisposition, SovereignHttpResult } from "./types.js";

export interface SovereignStatus {
  sovereign_version: string;
  protocol_version: string;
}

export interface FeatureDescriptor {
  name: string;
  availability: CapabilityAvailability;
}

export interface SovereignCapabilities {
  protocol_version: string;
  features: FeatureDescriptor[];
}

export type FetchFn = (url: string, init?: RequestInit) => Promise<Response>;

export class SovereignClient {
  constructor(
    private readonly baseUrl: string,
    private readonly fetchImpl: FetchFn = fetch,
  ) {}

  private async post<T>(path: string, body: unknown): Promise<SovereignHttpResult<T>> {
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
  }

  async status(): Promise<SovereignHttpResult<SovereignStatus>> {
    const res = await this.fetchImpl(`${this.baseUrl}/api/sovereign/status`);
    if (!res.ok) return { ok: false, status: res.status, disposition: "ERROR" };
    return { ok: true, data: (await res.json()) as SovereignStatus };
  }

  async capabilities(): Promise<SovereignHttpResult<SovereignCapabilities>> {
    const res = await this.fetchImpl(`${this.baseUrl}/api/sovereign/capabilities`);
    if (!res.ok) return { ok: false, status: res.status, disposition: "ERROR" };
    return { ok: true, data: (await res.json()) as SovereignCapabilities };
  }

  async blastRadius(body: {
    organization_id: string;
    actor_identity_id: string;
  }): Promise<SovereignHttpResult<{ reachable_capabilities: string[] }>> {
    return this.post("/api/sovereign/simulate/blast-radius", body);
  }

  async mission(body: {
    organization_id: string;
    agent_id: string;
    steps: string[];
  }): Promise<SovereignHttpResult<{ steps: Array<{ disposition: MissionDisposition }> }>> {
    return this.post("/api/sovereign/simulate/mission", body);
  }

  async gauntlet(body: {
    organization_id: string;
    probe_ids?: string[];
  }): Promise<SovereignHttpResult<{ cases: Array<{ status: GauntletStatus }> }>> {
    return this.post("/api/sovereign/gauntlet", body);
  }
}
