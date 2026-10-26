// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Component contract for a revoked agent. This is not customer acceptance.

export const REVOKED_AGENT_DENIAL = Object.freeze({
  status: 404,
  error: "http_error",
  message: "Agent is not an active principal in this organization.",
});

const EFFECT_FIELDS = ["approval_id", "execution_authorization_id", "evidence_id", "outcome_id"];

function plainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function sameIds(left, right) {
  return Array.isArray(left) && Array.isArray(right) && left.length === right.length && left.every((id, index) => id === right[index]);
}

export function qualifyRevocationDenial(response, evidence = {}) {
  if (!plainObject(response) || response.timedOut === true) {
    return { qualified: false, reason: response?.timedOut === true ? "TIMEOUT" : "MALFORMED" };
  }
  if (typeof response.status !== "number") return { qualified: false, reason: "MALFORMED" };
  if (response.status >= 500) return { qualified: false, reason: "SERVER_ERROR" };
  if (response.status < 400 || response.status >= 500) return { qualified: false, reason: "NOT_CLIENT_DENIAL" };
  if (!plainObject(response.value)) return { qualified: false, reason: "MALFORMED" };
  const value = response.value;
  const contract = response.status === REVOKED_AGENT_DENIAL.status
    && value.error === REVOKED_AGENT_DENIAL.error
    && value.message === REVOKED_AGENT_DENIAL.message;
  if (!contract) return { qualified: false, reason: "DENIAL_CONTRACT_MISMATCH" };
  if (value.proceed === true || value.execution_status === "SUCCEEDED" || EFFECT_FIELDS.some(field => value[field] != null && value[field] !== "")) {
    return { qualified: false, reason: "DOWNSTREAM_EFFECT" };
  }
  const { priorEvidenceIds, laterEvidenceIds } = evidence;
  if (priorEvidenceIds !== undefined || laterEvidenceIds !== undefined) {
    if (!sameIds(priorEvidenceIds, laterEvidenceIds)) return { qualified: false, reason: "EVIDENCE_CHANGED" };
  }
  return { qualified: true, reason: "REVOKED_AGENT_ADMISSION_REFUSAL" };
}
