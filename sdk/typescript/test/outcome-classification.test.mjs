import assert from "node:assert/strict";
import { test } from "node:test";
import { isCompleted } from "../dist/index.js";

test("all non-success and malformed outcome markers fail closed", () => {
  for (const field of ["status", "outcome_status", "decision"]) {
    for (const value of ["UNKNOWN", "DENY", "DENIED", "REQUIRE_APPROVAL", "QUARANTINE", "FAILED",
      "PENDING", "ERRORED", "BLOCKED", "ALLOW", "unrecognized", null, 1, {}]) {
      if (field === "decision" && value === "ALLOW" || field === "outcome_status" && value === null) continue;
      assert.equal(isCompleted({ [field]: value, result: { ok: true } }), false, `${field}: ${value}`);
    }
  }
});

test("missing result and contradictory envelopes are not success", () => {
  for (const body of [{}, { status: "SUCCEEDED" }, { decision: "ALLOW" }, { message: "ok" },
    { result: {}, reconciliation_required: true }, { result: {}, denied: true },
    { result: {}, requires_approval: true }, { result: { error: "downstream_failure" } },
    { result: { is_error: true } }, { result: { isError: true } },
    { result: {}, status: "SUCCEEDED", decision: "DENY" },
    { result: {}, reconciliation_required: "false" }, null, [], "ok"])
    assert.equal(isCompleted(body), false);
});

test("canonical and legacy success envelopes remain supported", () => {
  for (const body of [{ result: { ok: true } }, { tool: "local", result: null, outcome_status: "SUCCEEDED" },
    { tool: "local", result: 0, outcome_status: null },
    { result: {}, status: "SUCCEEDED", decision: "ALLOW", reconciliation_required: false }])
    assert.equal(isCompleted(body), true);
});
