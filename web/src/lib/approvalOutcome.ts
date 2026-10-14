// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { ApiError } from "./api";
import type { ConsequentialOutcome } from "./contracts";

export function approvalResourceSegment(id: string): string {
  if (!id || id === "." || id === "..") throw new Error("Invalid approval reference");
  return encodeURIComponent(id);
}

export function mutationAcknowledgementUncertain(cause: unknown): boolean {
  return !(cause instanceof ApiError) || cause.status >= 500;
}

export function uncertainExecution(approvalId: string): Extract<ConsequentialOutcome, { state: "UNKNOWN" }> {
  return { state: "UNKNOWN", approvalId, reconciliationRequired: true,
    message: "WhitePact cannot confirm whether the downstream effect occurred. Inspect the approval and evidence before any further action." };
}

// Runtime validation is required: TypeScript typing cannot make a malformed or
// contradictory HTTP-success acknowledgement into confirmed execution.
export function executionAcknowledgement(approvalId: string, value: unknown): ConsequentialOutcome {
  if (!value || typeof value !== "object" || Array.isArray(value)) return uncertainExecution(approvalId);
  const response = value as Record<string, unknown>;
  if (response.approval_id !== approvalId || "error" in response || typeof response.message !== "string" || typeof response.reconciliation_required !== "boolean") return uncertainExecution(approvalId);
  const evidenceId = typeof response.evidence_id === "string" && response.evidence_id ? response.evidence_id : undefined;
  const outcomeId = typeof response.outcome_id === "string" && response.outcome_id ? response.outcome_id : undefined;
  if (response.execution_status === "UNKNOWN" || response.reconciliation_required) return { ...uncertainExecution(approvalId), evidenceId, outcomeId };
  if (response.execution_status === "SUCCEEDED") return { state: "SUCCESS", approvalId, message: response.message, evidenceId, outcomeId };
  if (response.execution_status === "FAILED" || response.execution_status === "NOT_ATTEMPTED") return { state: "FAILED", approvalId, message: response.message };
  return uncertainExecution(approvalId);
}
