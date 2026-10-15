// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { api } from "./api";

type SessionContext = { organization: { id: string } };
type ObjectValue = Record<string, unknown>;

function object(value: unknown): value is ObjectValue {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function identifier(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value !== "." && value !== ".." && !/[\s\p{Cc}/\\?#%]/u.test(value) && !/[\uD800-\uDFFF]/u.test(value);
}

export interface ApplicationInfo {
  id: string;
  name: string;
  description: string;
  environment: string;
  lifecycleState: string;
  hasExecutionAuthority: boolean;
  agentCount: number;
}

export interface CapabilityInfo {
  id: string;
  agentId: string;
  applicationId: string | null;
  kind: string;
  actionType: string;
  allowedTargets: string[];
  status: string;
  requiresApproval: boolean;
  requiresPasskeyStepup: boolean;
  authorityEnforced: boolean;
}

export function customerApplicationReader(session: SessionContext) {
  const organizationId = session?.organization?.id;
  if (!identifier(organizationId)) throw new Error("Authenticated organization context is unavailable.");
  const base = `/api/enterprise/organizations/${encodeURIComponent(organizationId)}/authority`;

  return {
    async applications(signal?: AbortSignal): Promise<ApplicationInfo[]> {
      const value = await api<unknown>(`${base}/applications`, { signal });
      if (!object(value) || !Array.isArray(value.applications)) throw new Error("Application inventory could not be confirmed.");
      const ids = new Set<string>();
      return value.applications.map((app: unknown) => {
        if (!object(app) || app.organization_id !== organizationId || !identifier(app.application_id) || ids.has(app.application_id) || typeof app.name !== "string" || typeof app.lifecycle_state !== "string") {
          throw new Error("Application inventory could not be confirmed.");
        }
        ids.add(app.application_id);
        return {
          id: app.application_id,
          name: app.name,
          description: typeof app.description === "string" ? app.description : "",
          environment: typeof app.environment === "string" ? app.environment : "production",
          lifecycleState: app.lifecycle_state,
          hasExecutionAuthority: false,
          agentCount: typeof app.agent_count === "number" ? app.agent_count : 0,
        };
      });
    },

    async capabilities(signal?: AbortSignal, agentId?: string): Promise<CapabilityInfo[]> {
      const path = agentId ? `${base}/agents/${encodeURIComponent(agentId)}/capabilities` : `${base}/capabilities`;
      const value = await api<unknown>(path, { signal });
      if (!object(value) || !Array.isArray(value.capabilities)) throw new Error("Capabilities could not be confirmed.");
      return value.capabilities.map((cap: unknown) => {
        if (!object(cap) || cap.organization_id !== organizationId || !identifier(cap.capability_id)) {
          throw new Error("Capability could not be confirmed.");
        }
        return {
          id: cap.capability_id,
          agentId: String(cap.agent_id),
          applicationId: (cap as Record<string, unknown>).application_id as string | null ?? null,
          kind: String((cap as Record<string, unknown>).kind ?? ""),
          actionType: String((cap as Record<string, unknown>).action_type ?? ""),
          allowedTargets: Array.isArray((cap as Record<string, unknown>).allowed_targets) ? ((cap as Record<string, unknown>).allowed_targets as string[]) : [],
          status: String((cap as Record<string, unknown>).status ?? ""),
          requiresApproval: Boolean((cap as Record<string, unknown>).requires_approval),
          requiresPasskeyStepup: Boolean((cap as Record<string, unknown>).requires_passkey_stepup),
          authorityEnforced: true,
        };
      });
    },
  };
}
