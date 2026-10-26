// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Adversarial component cases. They do not qualify the default customer journey.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { qualifyRevocationDenial, REVOKED_AGENT_DENIAL } from "./revocation-denial.mjs";

const denial = (extra = {}) => ({
  status: REVOKED_AGENT_DENIAL.status,
  value: { error: REVOKED_AGENT_DENIAL.error, message: REVOKED_AGENT_DENIAL.message, ...extra },
});

test("documented revoked-agent refusal qualifies only with unchanged evidence", () => {
  const ids = ["evidence-1"];
  const result = qualifyRevocationDenial(denial(), { priorEvidenceIds: ids, laterEvidenceIds: [...ids] });
  assert.equal(result.qualified, true);
  assert.equal(result.reason, "REVOKED_AGENT_ADMISSION_REFUSAL");
});

test("HTTP 500 is not a revocation denial", () => {
  const result = qualifyRevocationDenial({
    status: 500,
    value: { error: "internal_server_error", message: "An unexpected error occurred." },
  });
  assert.equal(result.qualified, false);
  assert.equal(result.reason, "SERVER_ERROR");
});

test("malformed bodies fail qualification", () => {
  for (const response of [null, undefined, "nope", { status: 404, value: null }, { status: 404, value: [] }, { value: denial().value }]) {
    assert.equal(qualifyRevocationDenial(response).qualified, false);
    assert.equal(qualifyRevocationDenial(response).reason, "MALFORMED");
  }
});

test("missing denial fields fail qualification", () => {
  assert.equal(qualifyRevocationDenial({ status: 404, value: { error: "http_error" } }).reason, "DENIAL_CONTRACT_MISMATCH");
  assert.equal(qualifyRevocationDenial({ status: 404, value: { message: REVOKED_AGENT_DENIAL.message } }).reason, "DENIAL_CONTRACT_MISMATCH");
  assert.equal(qualifyRevocationDenial({ status: 404, value: { error: "http_error", message: "denied" } }).reason, "DENIAL_CONTRACT_MISMATCH");
});

test("ambiguous success-shaped and non-contract denials fail qualification", () => {
  assert.equal(qualifyRevocationDenial({ status: 200, value: { proceed: false, error: "governance_denied" } }).reason, "NOT_CLIENT_DENIAL");
  assert.equal(qualifyRevocationDenial({ status: 403, value: { error: "governance_denied", proceed: false } }).reason, "DENIAL_CONTRACT_MISMATCH");
  assert.equal(qualifyRevocationDenial(denial({ proceed: true })).reason, "DOWNSTREAM_EFFECT");
  assert.equal(qualifyRevocationDenial(denial({ approval_id: "apr-new" })).reason, "DOWNSTREAM_EFFECT");
  assert.equal(qualifyRevocationDenial(denial({ execution_authorization_id: "auth-new" })).reason, "DOWNSTREAM_EFFECT");
  assert.equal(qualifyRevocationDenial(denial({ evidence_id: "ev-new", outcome_id: "out-new" })).reason, "DOWNSTREAM_EFFECT");
  assert.equal(qualifyRevocationDenial(denial({ execution_status: "SUCCEEDED" })).reason, "DOWNSTREAM_EFFECT");
});

test("timeouts fail qualification", () => {
  assert.equal(qualifyRevocationDenial({ timedOut: true }).reason, "TIMEOUT");
  assert.equal(qualifyRevocationDenial({ timedOut: true, status: 404, value: denial().value }).qualified, false);
});

test("changed evidence ids fail qualification", () => {
  const result = qualifyRevocationDenial(denial(), { priorEvidenceIds: ["evidence-1"], laterEvidenceIds: ["evidence-1", "evidence-2"] });
  assert.equal(result.qualified, false);
  assert.equal(result.reason, "EVIDENCE_CHANGED");
});

test("the permissive historical predicate is not the harness", () => {
  const source = readFileSync(new URL("./m13-apex-customer.mjs", import.meta.url), "utf8");
  assert.match(source, /qualifyRevocationDenial\(denied/);
  assert.doesNotMatch(source, /denied\.status === 404 \|\|/);
  assert.doesNotMatch(source, /governance_denied/);
  const historical = response => response.value?.error !== undefined
    && (response.status === 404 || response.value?.error === "governance_denied" || response.value?.proceed !== true);
  const serverError = { status: 500, value: { error: "internal_server_error" } };
  assert.equal(historical(serverError), true);
  assert.equal(qualifyRevocationDenial(serverError).qualified, false);
});
