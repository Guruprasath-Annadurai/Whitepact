// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export type KeyRecord = { id: string; name: string; prefix: string; environment: string; scopes: string[]; created_at: string; last_used_at: string | null; expires_at: string | null; status: string };

// The list endpoint exposes metadata only. Do not retain unexpected secret fields.
export function readKeyInventory(payload: unknown, organizationId?: string): KeyRecord[] {
  const invalid = () => new Error("API key metadata could not be confirmed. Retry the inventory read.");
  if (!payload || typeof payload !== "object" || !("keys" in payload) || !Array.isArray(payload.keys)) throw invalid();
  const seen = new Set<string>();
  return payload.keys.map((item: unknown) => {
    if (!item || typeof item !== "object" || Array.isArray(item)) throw invalid();
    const record = item as Record<string, unknown>;
    if (organizationId && record.org_id !== organizationId) throw invalid();
    const text = (key: string) => { const value = record[key]; if (typeof value !== "string") throw invalid(); return value; };
    const optionalDate = (key: string) => { const value = record[key]; if (value !== null && (typeof value !== "string" || !Number.isFinite(Date.parse(value)))) throw invalid(); return value as string | null; };
    const id = text("id");
    if (!id.trim() || seen.has(id)) throw invalid();
    seen.add(id);
    if (!Array.isArray(record.scopes) || record.scopes.some((scope) => typeof scope !== "string")) throw invalid();
    const created_at = text("created_at");
    if (!Number.isFinite(Date.parse(created_at))) throw invalid();
    return { id, name: text("name"), prefix: text("prefix"), environment: text("environment"), scopes: [...record.scopes] as string[], created_at, last_used_at: optionalDate("last_used_at"), expires_at: optionalDate("expires_at"), status: text("status") };
  });
}
