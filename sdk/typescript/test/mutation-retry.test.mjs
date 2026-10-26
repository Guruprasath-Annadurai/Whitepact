import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import http from "node:http";
import { RAIClient, GovernanceRuntimeClient } from "../dist/index.js";
const realFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = realFetch; });

for (const failure of ["status", "transport"]) test(`mutation is one shot on ${failure} failure`, async () => {
  let calls = 0;
  globalThis.fetch = async () => {
    calls++;
    if (failure === "transport") throw new TypeError("lost response");
    return new Response("unavailable", { status: 503 });
  };
  await assert.rejects(new RAIClient({ maxRetries: 3, retryBaseMs: 1 }).createApiKey("local", "admin"));
  assert.equal(calls, 1);
});

test("read retries remain bounded", async () => {
  let calls = 0;
  globalThis.fetch = async () => new Response(JSON.stringify({ ok: true }), { status: ++calls < 3 ? 503 : 200 });
  assert.deepEqual(await new RAIClient({ maxRetries: 3, retryBaseMs: 1 }).health(), { ok: true });
  assert.equal(calls, 3);
});

test("all governed requests refuse automatic redirect dispatch", async () => {
  const requests = [];
  globalThis.fetch = async (url, init) => {
    requests.push(init);
    return new Response('{"result":true}', { status: 200 });
  };
  const c = new GovernanceRuntimeClient({ apiKey: "synthetic-local" });
  await c.callTool("local"); await c.listApprovals(); await c.resolveApproval("a", "DENIED");
  await c.revokeDelegation("a", "local"); await c.executeApproval("a"); await c.getEvidence("e");
  await new RAIClient().health();
  assert.ok(requests.every(r => r.redirect === "error"));
});

test("real redirect cannot forward a mutation or bearer token", async () => {
  globalThis.fetch = realFetch;
  let redirected = 0;
  const server = http.createServer((req, res) => {
    if (req.url === "/redirected") { redirected++; res.end('{"result":true}'); }
    else { res.writeHead(307, { Location: "/redirected" }); res.end(); }
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try {
    const baseUrl = `http://127.0.0.1:${server.address().port}`;
    await assert.rejects(new RAIClient({ apiKey: "synthetic-local", baseUrl }).createApiKey("local", "admin"));
    await assert.rejects(new GovernanceRuntimeClient({ apiKey: "synthetic-local", baseUrl }).callTool("local"));
    assert.equal(redirected, 0);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
