import assert from "node:assert/strict";
import { test } from "node:test";
import { isCompleted } from "../dist/index.js";

test("UNKNOWN and reconciliation-required results never claim completed", () => {
  for (const body of [
    { status: "UNKNOWN", evidence_id: "ev-local" },
    { reconciliation_required: true },
    { status: "UNKNOWN", reconciliation_required: true },
    { tool: "local.tool", result: null, outcome_status: "UNKNOWN" },
    { error: "governance_unknown_outcome" },
  ]) assert.equal(isCompleted(body), false);
});

test("confirmed legacy tool result retains completion semantics", () => {
  assert.equal(isCompleted({ result: { ok: true } }), true);
});
