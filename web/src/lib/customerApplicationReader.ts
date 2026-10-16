// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Application and capability inventory read contracts. Application registration
// never grants execution authority; capabilities are reachability projections
// only and require root_id, delegation_id, and consent_id when AUTHORIZED.
import { api } from "./api";

type SessionContext = { organization: { id: string } };
type ObjectValue = Record<string, unknown>;

const VALID_APPLICATION_STATES = new Set(["ACTIVE", "DISABLED", "QUARANTINED", "REVOKED"]);
const VALID_CAPABILITY_STATUSES = new Set([
  "AUTHORIZED",
  "PENDING_DELEGATION",
  "DISABLED",
  "REVOKED",
  "EXPIRED",
  "POLICY_DENIED",
]);

function object(value: unknown): value is ObjectValue {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function identifier(value: unknown): value is string {
  return (
    typeof value === "string" &&
    value.length > 0 &&
    value !== "." &&
    value !== ".." &&
    !/[\s\p{Cc}/\\?#%]/u.test(value) &&
    !/[\uD800-\uDFFF]/u.test(value)
  );
}

function optionalIdentifier(value: unknown, errorMessage: string): string | null {
  if (value === null || value === undefined) return null;
  if (!identifier(value)) throw new Error(errorMessage);
  return value;
}

export interface ApplicationInfo {
  id: string;
  name: string;
  description: string;
  environment: string;
  lifecycleState: string;
  hasExecutionAuthority: false;
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
  rootId: string | null;
  delegationId: string | null;
  consentId: string | null;
  authorityEnforced: true;
}

export function customerApplicationReader(session: SessionContext) {
  const organizationId = session?.organization?.id;
  if (!identifier(organizationId)) throw new Error("Authenticated organization context is unavailable.");
  const base = `/api/enterprise/organizations/${encodeURIComponent(organizationId)}/authority`;

  return {
    async applications(signal?: AbortSignal): Promise<ApplicationInfo[]> {
      const value = await api<unknown>(`${base}/applications`, { signal });
      if (!object(value) || !Array.isArray(value.applications)) {
        throw new Error("Application inventory could not be confirmed.");
      }
      const ids = new Set<string>();
      return value.applications.map((app: unknown) => {
        if (
          !object(app) ||
          app.organization_id !== organizationId ||
          !identifier(app.application_id) ||
          ids.has(app.application_id) ||
          typeof app.name !== "string" ||
          app.name.trim().length === 0 ||
          typeof app.description !== "string" ||
          typeof app.environment !== "string" ||
          app.environment.trim().length === 0 ||
          typeof app.lifecycle_state !== "string" ||
          !VALID_APPLICATION_STATES.has(app.lifecycle_state) ||
          app.has_execution_authority !== false ||
          !Number.isSafeInteger(app.agent_count) ||
          (app.agent_count as number) < 0
        ) {
          throw new Error("Application inventory could not be confirmed.");
        }
        ids.add(app.application_id);
        return {
          id: app.application_id,
          name: app.name,
          description: app.description,
          environment: app.environment,
          lifecycleState: app.lifecycle_state,
          hasExecutionAuthority: false,
          agentCount: app.agent_count as number,
        };
      });
    },

    async capabilities(signal?: AbortSignal, agentId?: string): Promise<CapabilityInfo[]> {
      if (agentId !== undefined && !identifier(agentId)) {
        throw new Error("Agent identifier is invalid.");
      }
      const path = agentId
        ? `${base}/agents/${encodeURIComponent(agentId)}/capabilities`
        : `${base}/capabilities`;
      const value = await api<unknown>(path, { signal });
      if (!object(value) || !Array.isArray(value.capabilities)) {
        throw new Error("Capabilities could not be confirmed.");
      }
      const ids = new Set<string>();
      return value.capabilities.map((cap: unknown) => {
        if (
          !object(cap) ||
          cap.organization_id !== organizationId ||
          !identifier(cap.capability_id) ||
          ids.has(cap.capability_id) ||
          !identifier(cap.agent_id) ||
          (agentId !== undefined && cap.agent_id !== agentId) ||
          typeof cap.kind !== "string" ||
          cap.kind.trim().length === 0 ||
          typeof cap.action_type !== "string" ||
          cap.action_type.trim().length === 0 ||
          !Array.isArray(cap.allowed_targets) ||
          !cap.allowed_targets.every((t: unknown) => typeof t === "string" && t.trim().length > 0) ||
          typeof cap.status !== "string" ||
          !VALID_CAPABILITY_STATUSES.has(cap.status) ||
          typeof cap.requires_approval !== "boolean" ||
          typeof cap.requires_passkey_stepup !== "boolean" ||
          cap.authority_enforced !== true
        ) {
          throw new Error("Capability could not be confirmed.");
        }
        const applicationId = optionalIdentifier(
          cap.application_id,
          "Capability could not be confirmed."
        );
        const rootId = optionalIdentifier(cap.root_id, "Capability could not be confirmed.");
        const delegationId = optionalIdentifier(
          cap.delegation_id,
          "Capability could not be confirmed."
        );
        const consentId = optionalIdentifier(cap.consent_id, "Capability could not be confirmed.");
        if (cap.status === "AUTHORIZED") {
          if (!rootId || !delegationId || !consentId || cap.allowed_targets.length === 0) {
            throw new Error("Capability could not be confirmed.");
          }
        } else if (cap.requires_approval !== true) {
          throw new Error("Capability could not be confirmed.");
        }
        ids.add(cap.capability_id);
        return {
          id: cap.capability_id,
          agentId: cap.agent_id,
          applicationId,
          kind: cap.kind,
          actionType: cap.action_type,
          allowedTargets: [...(cap.allowed_targets as string[])],
          status: cap.status,
          requiresApproval: cap.requires_approval,
          requiresPasskeyStepup: cap.requires_passkey_stepup,
          rootId,
          delegationId,
          consentId,
          authorityEnforced: true,
        };
      });
    },
  };
}
