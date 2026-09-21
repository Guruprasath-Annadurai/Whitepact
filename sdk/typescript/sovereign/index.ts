/** WhitePact Sovereign TypeScript contract (partial V1 parity). */

export type CapabilityAvailability = "AVAILABLE" | "UNAVAILABLE" | "EXPERIMENTAL";

export type MissionDisposition =
  | "ALLOW"
  | "DENY"
  | "APPROVAL_REQUIRED"
  | "UNKNOWN"
  | "UNREACHABLE";

export interface SovereignStatus {
  sovereign_version: string;
  protocol_version: string;
}

export interface SovereignClientOptions {
  baseUrl: string;
}

export class SovereignClient {
  constructor(private readonly options: SovereignClientOptions) {}

  async status(): Promise<SovereignStatus> {
    const res = await fetch(`${this.options.baseUrl}/api/sovereign/status`);
    if (!res.ok) {
      throw new Error(`status failed: ${res.status}`);
    }
    return (await res.json()) as SovereignStatus;
  }
}
