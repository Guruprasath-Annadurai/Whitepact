// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type {
  CapabilityAvailability,
  SovereignCapabilities,
  SovereignStatus,
} from "../../../../sdk/typescript/sovereign/types";
import { ApiError, api } from "../../lib/api";

export type SovereignFeatureName = SovereignCapabilities["features"][number]["name"];
export type BrowserCapabilityState = CapabilityAvailability | "UNKNOWN";
export type SovereignPayload = Record<string, unknown>;

export type SovereignNegotiation = {
  status: SovereignStatus;
  capabilities: SovereignCapabilities;
};

export type SovereignWebError =
  | { kind: "INVALID_REQUEST"; status: 400 }
  | { kind: "UNAUTHENTICATED"; status: 401 }
  | { kind: "CSRF_REJECTED"; status: 403 }
  | { kind: "NOT_FOUND"; status: 404 }
  | { kind: "ORGANIZATION_UNAVAILABLE"; status: 409 }
  | { kind: "FEATURE_UNAVAILABLE"; status: 501 }
  | { kind: "NETWORK"; status: 0 }
  | { kind: "BACKEND"; status: number };

export const sovereignOperations = {
  xray: { path: "/api/web/sovereign/xray", feature: "xray", zeroEffect: true },
  explain: { path: "/api/web/sovereign/explain", feature: "explain", zeroEffect: true },
  trace: { path: "/api/web/sovereign/trace", feature: "trace", zeroEffect: true },
  effective: { path: "/api/web/sovereign/authority/effective", feature: "authority_effective", zeroEffect: true },
  compare: { path: "/api/web/sovereign/authority/compare", feature: "authority_compare", zeroEffect: true },
  drift: { path: "/api/web/sovereign/authority/drift", feature: "authority_drift", zeroEffect: true },
  blastRadius: { path: "/api/web/sovereign/simulate/blast-radius", feature: "simulate_blast_radius", zeroEffect: true },
  mission: { path: "/api/web/sovereign/simulate/mission", feature: "simulate_mission", zeroEffect: true },
  shadow: { path: "/api/web/sovereign/shadow", feature: "shadow", zeroEffect: true },
  policyLint: { path: "/api/web/sovereign/policy/lint", feature: "policy_lab", zeroEffect: true },
  policyValidate: { path: "/api/web/sovereign/policy/lint", feature: "policy_lab", zeroEffect: true },
  policyTest: { path: "/api/web/sovereign/policy/test", feature: "policy_lab", zeroEffect: true },
  policyDiff: { path: "/api/web/sovereign/policy/diff", feature: "policy_lab", zeroEffect: true },
  policySimulate: { path: "/api/web/sovereign/policy/simulate", feature: "policy_lab", zeroEffect: true },
  gauntlet: { path: "/api/web/sovereign/gauntlet", feature: "gauntlet", zeroEffect: true },
  flightRecorder: { path: "/api/web/sovereign/flight-recorder", feature: "flight_recorder", zeroEffect: true },
  timeMachine: { path: "/api/web/sovereign/time-machine", feature: "time_machine", zeroEffect: true },
  evidence: { path: "/api/web/sovereign/evidence/correlate", feature: "evidence", zeroEffect: true },
  capsuleCreate: { path: "/api/web/sovereign/capsules", feature: "capsule", zeroEffect: true },
  capsuleValidate: { path: "/api/web/sovereign/capsules/validate", feature: "capsule", zeroEffect: true },
  capsuleReproduce: { path: "/api/web/sovereign/capsules/reproduce", feature: "capsule", zeroEffect: true },
  authorityBom: { path: "/api/web/sovereign/authority-bom", feature: "authority_bom", zeroEffect: true, experimental: true },
} as const;

export type SovereignOperation = keyof typeof sovereignOperations;

export function browserCapabilityState(
  capabilities: SovereignCapabilities | null,
  name: SovereignFeatureName,
): BrowserCapabilityState {
  const negotiated = capabilities?.features.find((feature) => feature.name === name)?.availability;
  return negotiated ?? "UNKNOWN";
}

export function sovereignFixturesAllowed(isDevelopment: boolean): boolean {
  return isDevelopment;
}

function assertNoBrowserTenantAuthority(value: SovereignPayload): void {
  for (const key of ["organization_id", "organizationId", "tenant_id", "tenantId"]) {
    if (key in value) throw new ApiError(400, "Organization context is derived from the authenticated session.");
  }
}

export class SovereignWebApi {
  async negotiate(): Promise<SovereignNegotiation> {
    const [status, capabilities] = await Promise.all([
      api<SovereignStatus>("/api/web/sovereign/status"),
      api<SovereignCapabilities>("/api/web/sovereign/capabilities"),
    ]);
    return { status, capabilities };
  }

  async execute<T extends SovereignPayload = SovereignPayload>(operation: SovereignOperation, payload: SovereignPayload): Promise<T> {
    assertNoBrowserTenantAuthority(payload);
    return api<T>(sovereignOperations[operation].path, { method: "POST", body: JSON.stringify(payload) });
  }

  classify(error: unknown): SovereignWebError {
    if (!(error instanceof ApiError)) return { kind: "NETWORK", status: 0 };
    if (error.status === 400) return { kind: "INVALID_REQUEST", status: 400 };
    if (error.status === 401) return { kind: "UNAUTHENTICATED", status: 401 };
    if (error.status === 403) return { kind: "CSRF_REJECTED", status: 403 };
    if (error.status === 404) return { kind: "NOT_FOUND", status: 404 };
    if (error.status === 409) return { kind: "ORGANIZATION_UNAVAILABLE", status: 409 };
    if (error.status === 501) return { kind: "FEATURE_UNAVAILABLE", status: 501 };
    return { kind: "BACKEND", status: error.status };
  }
}

export const sovereignWebApi = new SovereignWebApi();
