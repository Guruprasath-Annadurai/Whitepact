// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { api } from "../../lib/api";

export type RecoveryRecord = { id: string; type: string; rootId: string; requesterId: string; status: string; expiresAt: string };
function id(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && value !== "." && value !== ".." && !/[\s\p{Cc}/\\?#%\uD800-\uDFFF]/u.test(value);
}
function object(value: unknown): value is Record<string, unknown> {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

// Read-only addressing context, NEVER tenant authority. The server independently
// derives the session principal and enforces tenant membership on every request.
// No production caller until M12-FS contract defects are corrected and reviewed.
export async function readRecoveryRecords(session: { organization: { id: string } }, signal?: AbortSignal): Promise<RecoveryRecord[]> {
  const org = session?.organization?.id;
  if (!id(org)) throw new Error("Authenticated organization context is unavailable.");
  const result = await api<unknown>(`/api/enterprise/organizations/${encodeURIComponent(org)}/authority/recovery/requests`, { signal });
  if (!object(result) || !Array.isArray(result.requests)) throw new Error("Recovery records could not be confirmed.");
  const seen = new Set<string>();
  return result.requests.map((record: unknown) => {
    if (!object(record) || record.organization_id !== org || !id(record.request_id) || seen.has(record.request_id) || !id(record.target_root_id) || !id(record.requester_user_id) || typeof record.request_type !== "string" || typeof record.status !== "string" || typeof record.expires_at !== "string") throw new Error("Recovery records could not be confirmed.");
    seen.add(record.request_id);
    // Do not copy arbitrary proposed parameters, tokens, signatures or vote data.
    // Current backend M/N are caller-specified, not an accepted security policy.
    return { id: record.request_id, type: record.request_type, rootId: record.target_root_id, requesterId: record.requester_user_id, status: record.status, expiresAt: record.expires_at };
  });
}
