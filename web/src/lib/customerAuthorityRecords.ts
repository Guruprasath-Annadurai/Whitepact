// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Recorded metadata only. No effective authorization or consent-validity inference.
import { api } from "./api";

type ObjectValue = Record<string, unknown>;
function object(value: unknown): value is ObjectValue { return value !== null && typeof value === "object" && !Array.isArray(value); }
function text(value: unknown): string { if (typeof value !== "string" || !value.length) throw new Error("Recorded authority details could not be confirmed."); return value; }
function id(value: unknown): string { const result = text(value); if (/[\s\p{Cc}/\\?#%]/u.test(result) || result === "." || result === "..") throw new Error("Invalid record identifier"); return result; }
function timestamp(value: unknown): string { const result = text(value); if (!Number.isFinite(Date.parse(result))) throw new Error("Invalid recorded timestamp"); return result; }
function digest(value: unknown): string { const result = text(value); if (!/^[0-9a-f]{64}$/i.test(result)) throw new Error("Invalid recorded digest"); return result; }
function strings(value: unknown): string[] { if (!Array.isArray(value)) throw new Error("Invalid recorded scope"); return value.map(text); }

export async function readCustomerAuthorityRecords(organizationId: string, signal?: AbortSignal) {
  const expected = id(organizationId);
  const value = await api<unknown>(`/api/enterprise/organizations/${encodeURIComponent(expected)}/authority/status`, { signal });
  if (!object(value) || value.organization_id !== expected || typeof value.has_active_authority !== "boolean" || !Number.isSafeInteger(value.revocation_epoch) || (value.revocation_epoch as number) < 0) throw new Error("Recorded authority details could not be confirmed.");
  const root = value.root_authority;
  const consent = value.consent_proof;
  if ((root !== null && !object(root)) || (consent !== null && !object(consent)) || (value.has_active_authority && (!root || !consent))) throw new Error("Incomplete recorded authority pair");
  return {
    epoch: value.revocation_epoch as number,
    root: root === null ? null : { id: id(root.root_id), subject: id(root.subject_id), issuer: text(root.issuer), type: text(root.root_type), method: text(root.verification_method), issuedAt: timestamp(root.issued_at), expiresAt: root.expires_at === null ? null : timestamp(root.expires_at), digest: digest(root.canonical_digest) },
    consent: consent === null ? null : { id: id(consent.consent_id), scope: text(consent.scope_description), purpose: text(consent.purpose), method: text(consent.consent_method), actionTypes: strings(consent.allowed_action_types), targets: strings(consent.allowed_targets), consentedAt: timestamp(consent.consented_at), digest: digest(consent.canonical_digest) },
  };
}
