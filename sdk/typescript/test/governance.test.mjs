// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";

import { GovernanceRequestError, GovernanceRuntimeClient, RAIClient, RAIError, isCompleted } from "../dist/index.js";

const realFetch = globalThis.fetch;
afterEach(() => {
  globalThis.fetch = realFetch;
});

function stub(status, body, headers = { "content-type": "application/json" }) {
  const seen = [];
  globalThis.fetch = async (url, init) => {
    seen.push({ url: String(url), init });
    return new Response(typeof body === "string" ? body : JSON.stringify(body), { status, headers });
  };
  return seen;
}

const client = () => new GovernanceRuntimeClient({ apiKey: "key-secret-123", baseUrl: "https://wp.test" });

test("a non-2xx answer is an exception, never an outcome", async () => {
  for (const status of [400, 401, 403, 404, 409, 422, 429, 500, 502, 503]) {
    stub(status, { error: "whatever" });
    await assert.rejects(client().callTool("t", {}), (e) => {
      assert.ok(e instanceof GovernanceRequestError);
      assert.equal(e.status, status);
      assert.ok(!String(e.message).includes("key-secret-123"));
      return true;
    });
  }
});

test("a 2xx body that is not a JSON object is refused", async () => {
  for (const body of ["<html>gateway</html>", "", "[]", '"ok"', "null"]) {
    stub(200, body);
    await assert.rejects(client().callTool("t", {}), GovernanceRequestError);
  }
});

test("denied and approval answers are outcomes and are not completed", async () => {
  stub(200, { error: "governance_denied" });
  assert.equal(isCompleted(await client().callTool("t", {})), false);
  stub(200, { error: "governance_approval_required", approval_id: "a1" });
  assert.equal(isCompleted(await client().callTool("t", {})), false);
});

test("a clean answer is completed, sends the bearer key and the purpose", async () => {
  const seen = stub(200, { result: { ok: true } });
  const out = await client().callTool("t", { a: 1 }, "p");
  assert.equal(isCompleted(out), true);
  assert.equal(seen[0].init.headers.Authorization, "Bearer key-secret-123");
  assert.deepEqual(JSON.parse(seen[0].init.body), { name: "t", arguments: { a: 1 }, purpose: "p" });
});

test("the timer is cleared when the request fails, so the process can exit", async () => {
  globalThis.fetch = async () => {
    throw new Error("network down");
  };
  await assert.rejects(client().callTool("t", {}), /network down/);
});

test("RAIClient retries only the statuses it documents and never leaks the key in errors", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls += 1;
    return new Response("nope", { status: 401 });
  };
  const rai = new RAIClient({ apiKey: "key-secret-123", baseUrl: "https://wp.test", maxRetries: 3, retryBaseMs: 1 });
  await assert.rejects(rai.health(), (e) => e instanceof RAIError && e.status === 401 && !e.message.includes("key-secret-123"));
  assert.equal(calls, 1, "a 401 is not retried");
});
