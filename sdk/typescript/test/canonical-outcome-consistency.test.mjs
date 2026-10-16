// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import { isCompleted, GovernanceRuntimeClient } from "../dist/index.js";

test("both allowing decisions require a successful result envelope", () => {
  for (const decision of ["ALLOW", "ALLOW_WITH_REDACTION"]) {
    assert.equal(isCompleted({decision, result: {}, outcome_status: "SUCCEEDED"}), true);
    assert.equal(isCompleted({decision}), false);
  }
});
test("deep or cyclic result cannot become completed", () => {
  const result = {};
  result.result = result;
  assert.equal(isCompleted(result), false);
});
test("policy reader uses existing tenant-derived GET route", async () => {
  const previous = globalThis.fetch;
  const seen = [];
  try {
    globalThis.fetch = async (url, options) => {
      seen.push({url, options});
      return new Response(JSON.stringify({rules:[]}), {status:200});
    };
    const client = new GovernanceRuntimeClient({apiKey:"local-key",baseUrl:"http://127.0.0.1:8765"});
    assert.deepEqual(await client.getPolicy(), {rules:[]});
    assert.equal(seen.length, 1);
    assert.equal(seen[0].url, "http://127.0.0.1:8765/api/governance/policy");
    assert.equal(seen[0].options.method, "GET");
    assert.equal(seen[0].options.body, undefined);
  } finally { globalThis.fetch = previous; }
});
test("nested approval outcomes cannot become completed", () => {
  for (const result of [
    {result:{},outcome_status:"UNKNOWN"}, {result:{},decision:"DENY"},
    {result:{},decision:"REQUIRE_APPROVAL"}, {result:{},decision:"QUARANTINE"},
    {error:null}, {result:{isError:true}},
  ]) assert.equal(isCompleted({approval_id:"local-test",result}), false);
});
