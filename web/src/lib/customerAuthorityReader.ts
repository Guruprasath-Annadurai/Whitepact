// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Ordinary customer reads report registration and root/consent record state.
// These GET consumers cannot issue authority or enumerate effective capabilities.
import { api } from "./api";

type SessionContext = { organization: { id: string } };
type ObjectValue = Record<string, unknown>;
function object(value: unknown): value is ObjectValue {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function identifier(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value !== "." && value !== ".." && !/[\s\p{Cc}/\\?#%]/u.test(value) && !/[\uD800-\uDFFF]/u.test(value);
}
function nullableId(value: unknown, field: string): string | null {
  if (value === null) return null;
  if (!object(value) || !identifier(value[field])) throw new Error("Authority status could not be confirmed.");
  return value[field];
}

export function customerAuthorityReader(session: SessionContext) {
  const organizationId = session?.organization?.id;
  if (!identifier(organizationId)) throw new Error("Authenticated organization context is unavailable.");
  // Addressing context only. The server must independently bind the session tenant.
  const base = `/api/enterprise/organizations/${encodeURIComponent(organizationId)}/authority`;
  return {
    async status(signal?: AbortSignal) {
      const value = await api<unknown>(`${base}/status`, { signal });
      if (!object(value) || value.organization_id !== organizationId || typeof value.has_active_authority !== "boolean" || !Number.isSafeInteger(value.revocation_epoch) || (value.revocation_epoch as number) < 0) throw new Error("Authority status could not be confirmed.");
      const rootId = nullableId(value.root_authority, "root_id");
      const consentId = nullableId(value.consent_proof, "consent_id");
      if (value.has_active_authority && (!rootId || !consentId)) throw new Error("Authority status could not be confirmed.");
      return { reportedActive: value.has_active_authority, rootId, consentId, epoch: value.revocation_epoch as number };
    },
    async agents(signal?: AbortSignal) {
      const value = await api<unknown>(`${base}/agents`, { signal });
      if (!object(value) || !Array.isArray(value.agents)) throw new Error("Agent inventory could not be confirmed.");
      const ids = new Set<string>();
      return value.agents.map((agent: unknown) => {
        if (!object(agent) || agent.organization_id !== organizationId || !identifier(agent.agent_id) || ids.has(agent.agent_id) || typeof agent.display_name !== "string" || typeof agent.lifecycle_state !== "string" || typeof agent.has_active_delegation !== "boolean") throw new Error("Agent inventory could not be confirmed.");
        ids.add(agent.agent_id);
        return { id: agent.agent_id, displayName: agent.display_name, lifecycleState: agent.lifecycle_state, reportedActiveDelegation: agent.has_active_delegation };
      });
    },
  };
}
