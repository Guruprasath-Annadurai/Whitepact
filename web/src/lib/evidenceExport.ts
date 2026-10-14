// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import type { DomainRecord } from "./contracts";

const fields = ["evidence_id", "action_type", "target", "agent_id", "identity_id", "purpose", "risk_tier", "decision", "policy_version", "recorded_at", "evaluated_at", "approval_id", "execution_authorization_id", "hash", "prev_hash", "integrity_status", "outcome_status", "reconciliation_status"] as const;

export function boundedEvidenceExport(records: DomainRecord[]) {
  return {
    format: "whitepact-bounded-evidence-v1",
    scope: "Loaded records only; not complete history, a signed attestation, or independent verification.",
    records: records.map((record) => Object.fromEntries(fields.flatMap((field) => {
      const value = record[field];
      return typeof value === "string" || typeof value === "number" || typeof value === "boolean" || value === null ? [[field, value]] : [];
    }))),
  };
}

export function downloadBoundedEvidence(records: DomainRecord[]): void {
  const blob = new Blob([JSON.stringify(boundedEvidenceExport(records), null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url; link.download = "whitepact-loaded-evidence.json";
  try { document.body.append(link); link.click(); }
  finally { link.remove(); URL.revokeObjectURL(url); }
}
