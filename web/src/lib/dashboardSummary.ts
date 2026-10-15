// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export type DashboardSummary = {
  decisions: number;
  agents: number;
  pending_approvals: number;
  blocked_actions: number;
  recent_governance: Array<{ id: string; agent: string; action: string; policy: string; risk: string; decision: string; timestamp: string }>;
  services: Record<string, string>;
};

function record(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// Validate the existing display contract; labels are backend reports, not permits.
export function parseDashboardSummary(value: unknown): DashboardSummary {
  if (!record(value)
    || !["decisions", "agents", "pending_approvals", "blocked_actions"].every((key) => Number.isSafeInteger(value[key]) && Number(value[key]) >= 0)
    || !Array.isArray(value.recent_governance)
    || !value.recent_governance.every((event: unknown) => record(event) && ["id", "agent", "action", "policy", "risk", "decision", "timestamp"].every((key) => typeof event[key] === "string"))
    || !record(value.services)
    || !Object.values(value.services).every((status) => typeof status === "string")) {
    throw new Error("Governance summary could not be confirmed. Retry the read when the service is available.");
  }
  return value as DashboardSummary;
}
