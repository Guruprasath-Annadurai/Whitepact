// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type {
  CapabilityAvailability,
  SovereignCapabilities,
  SovereignStatus,
} from "../../../../sdk/typescript/sovereign/types";
import { ApiError, api } from "../../lib/api";

export type SovereignFeatureName = SovereignCapabilities["features"][number]["name"];
export type BrowserCapabilityState = CapabilityAvailability | "UNKNOWN" | "AUTH_CONTRACT_REQUIRED";

export type SovereignNegotiation = {
  status: SovereignStatus;
  capabilities: SovereignCapabilities;
};

export type SovereignNegotiationError =
  | { kind: "UNAUTHENTICATED"; status: 401 }
  | { kind: "FORBIDDEN"; status: 403 }
  | { kind: "NOT_FOUND"; status: 404 }
  | { kind: "NETWORK"; status: 0 }
  | { kind: "BACKEND"; status: number };

const SAFE_WEB_CAPABILITIES = new Set<SovereignFeatureName>(["status"]);

export function browserCapabilityState(
  capabilities: SovereignCapabilities | null,
  name: SovereignFeatureName,
): BrowserCapabilityState {
  const negotiated = capabilities?.features.find((feature) => feature.name === name)?.availability;
  if (!negotiated) return "UNKNOWN";
  if (negotiated === "UNAVAILABLE") return "UNAVAILABLE";
  if (!SAFE_WEB_CAPABILITIES.has(name)) return "AUTH_CONTRACT_REQUIRED";
  return negotiated;
}

export function sovereignFixturesAllowed(isDevelopment: boolean): boolean {
  return isDevelopment;
}

export class SovereignWebApi {
  async negotiate(): Promise<SovereignNegotiation> {
    const [status, capabilities] = await Promise.all([
      api<SovereignStatus>("/api/web/sovereign/status"),
      api<SovereignCapabilities>("/api/web/sovereign/capabilities"),
    ]);
    return { status, capabilities };
  }

  classify(error: unknown): SovereignNegotiationError {
    if (!(error instanceof ApiError)) return { kind: "NETWORK", status: 0 };
    if (error.status === 401) return { kind: "UNAUTHENTICATED", status: 401 };
    if (error.status === 403) return { kind: "FORBIDDEN", status: 403 };
    if (error.status === 404) return { kind: "NOT_FOUND", status: 404 };
    return { kind: "BACKEND", status: error.status };
  }
}

export const sovereignWebApi = new SovereignWebApi();
