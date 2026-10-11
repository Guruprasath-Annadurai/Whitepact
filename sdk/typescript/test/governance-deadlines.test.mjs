import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";
import { GovernanceRuntimeClient, GovernanceRequestError, RAIClient } from "../dist/index.js";

const methods = {
  callTool: (c, options) => c.callTool("local", {}, "test", options),
  listApprovals: (c, options) => c.listApprovals(undefined, options),
  resolveApproval: (c, options) => c.resolveApproval("a", "DENIED", undefined, options),
  revokeDelegation: (c, options) => c.revokeDelegation("a", "test", options),
  executeApproval: (c, options) => c.executeApproval("a", options),
  getEvidence: (c, options) => c.getEvidence("e", options),
  listEvidence: (c, options) => c.listEvidence(50, options),
  getAttestation: (c, options) => c.getAttestation("e", options),
};

for (const stage of ["headers", "body"]) for (const [name, invoke] of Object.entries(methods)) {
  test(`${name}: bounded hanging ${stage}, one dispatch`, async () => {
    let calls = 0;
    const server = http.createServer((_req, res) => {
      calls++;
      if (stage === "body") { res.writeHead(200); res.write('{"result":'); }
    });
    await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
    let deadline;
    try {
      const client = new GovernanceRuntimeClient({ apiKey: "synthetic", baseUrl: `http://127.0.0.1:${server.address().port}`, timeout: 100 });
      const observed = await Promise.race([
        invoke(client).then(() => "success", e => e.name),
        new Promise(resolve => { deadline = setTimeout(() => resolve("unbounded"), 1500); }),
      ]);
      assert.equal(observed, "AbortError");
      assert.equal(calls, 1);
    } finally {
      clearTimeout(deadline);
      server.closeAllConnections();
      await new Promise(resolve => server.close(resolve));
    }
  });
}

test("all methods preserve caller cancellation without dispatching an already canceled request", async () => {
  const controller = new AbortController();
  controller.abort(new Error("synthetic-sensitive-reason"));
  for (const invoke of Object.values(methods)) {
    await assert.rejects(invoke(new GovernanceRuntimeClient({ apiKey: "synthetic" }), { signal: controller.signal }),
      error => error.name === "AbortError" && !error.message.includes("synthetic-sensitive-reason"));
  }
});

test("all methods reject malformed success envelopes and redact authenticated errors", async () => {
  const original = globalThis.fetch;
  try {
    for (const invoke of Object.values(methods)) {
      for (const body of ["not JSON", "null", "[]", '"ok"']) {
        globalThis.fetch = async () => new Response(body);
        await assert.rejects(invoke(new GovernanceRuntimeClient({ apiKey: "synthetic" })), GovernanceRequestError);
      }
      globalThis.fetch = async () => new Response("expired synthetic", { status: 401 });
      await assert.rejects(invoke(new GovernanceRuntimeClient({ apiKey: "synthetic" })), e =>
        e.status === 401 && !e.detail.includes("synthetic") && e.detail.includes("[REDACTED]"));
    }
  } finally { globalThis.fetch = original; }
});

test("invalid governance deadlines fail before network configuration", () => {
  for (const timeout of [0, -1, NaN, Infinity, 2147483648])
    assert.throws(() => new GovernanceRuntimeClient({ apiKey: "synthetic", timeout }), RangeError);
});

test("invalid general SDK retry and timeout settings are rejected", () => {
  for (const timeout of [0, -1, NaN, Infinity, 2147483648]) assert.throws(() => new RAIClient({ timeout }), RangeError);
  for (const maxRetries of [0, -1, 1.5, Infinity, NaN]) assert.throws(() => new RAIClient({ maxRetries }), RangeError);
  for (const retryBaseMs of [-1, Infinity, NaN, 2147483648]) assert.throws(() => new RAIClient({ retryBaseMs }), RangeError);
});

test("canceling one concurrent request leaves the other intact and removes the listener", async () => {
  let started;
  const ready = new Promise(resolve => { started = resolve; });
  const server = http.createServer((req, res) => {
    if (req.url.includes("approvals")) started();
    else res.end('{"evidence_id":"e"}');
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const controller = new AbortController();
  let listeners = 0;
  const add = controller.signal.addEventListener.bind(controller.signal);
  const remove = controller.signal.removeEventListener.bind(controller.signal);
  controller.signal.addEventListener = (...args) => { listeners++; return add(...args); };
  controller.signal.removeEventListener = (...args) => { listeners--; return remove(...args); };
  try {
    const client = new GovernanceRuntimeClient({ apiKey: "synthetic", baseUrl: `http://127.0.0.1:${server.address().port}`, timeout: 2000 });
    const rejected = assert.rejects(client.listApprovals(undefined, { signal: controller.signal }), e => e.name === "AbortError");
    await ready;
    const healthy = client.getEvidence("e");
    controller.abort("sensitive reason");
    await rejected;
    assert.deepEqual(await healthy, { evidence_id: "e" });
    assert.equal(listeners, 0);
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
