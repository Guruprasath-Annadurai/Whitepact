import assert from "node:assert/strict";
import http from "node:http";
import { afterEach, test } from "node:test";
import { RAIClient, GovernanceRuntimeClient, isCompleted } from "../dist/index.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

test("HTTPS validation and redirect refusal compose without a second request", async () => {
  let calls = 0;
  globalThis.fetch = async (_url, init) => {
    calls++;
    assert.equal(init.redirect, "error");
    throw new TypeError("redirect refused");
  };
  assert.throws(() => new RAIClient({ baseUrl: "http://remote.test", apiKey: "synthetic" }));
  assert.equal(calls, 0);
  await assert.rejects(new RAIClient({ baseUrl: "https://remote.test", apiKey: "synthetic" }).createApiKey("local", "admin"));
  assert.equal(calls, 1);
});

test("UNKNOWN response and lost mutation acknowledgement never become completion or retry", async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    return new Response(JSON.stringify({ result: null, outcome_status: "UNKNOWN" }));
  };
  const client = new GovernanceRuntimeClient({ apiKey: "synthetic" });
  assert.equal(isCompleted(await client.callTool("local")), false);
  globalThis.fetch = async () => { calls++; throw new TypeError("lost acknowledgement"); };
  await assert.rejects(client.callTool("local"));
  assert.equal(calls, 2);
});

test("body timeout and reflected-key redaction remain safe on mutating requests", async () => {
  globalThis.fetch = originalFetch;
  let calls = 0;
  const key = "synthetic-combined-key";
  const server = http.createServer((_req, res) => {
    calls++;
    res.writeHead(403);
    res.write(`refused ${key}`);
    // First call stalls its error body; second completes and must redact.
    if (calls > 1) res.end();
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const client = new RAIClient({ baseUrl: `http://127.0.0.1:${server.address().port}`, apiKey: key, timeout: 100 });
    await assert.rejects(client.createApiKey("local", "admin"), error => !error.message.includes(key));
    assert.equal(calls, 1);
    await assert.rejects(client.createApiKey("local", "admin"), error => error.message.includes("[REDACTED]") && !error.message.includes(key));
    assert.equal(calls, 2);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
