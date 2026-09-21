import test from "node:test";
import assert from "node:assert/strict";
import { SovereignClient } from "./client.js";
import { retryClass } from "./retry.js";

const base = "http://x";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status });
}

test("status endpoint and GET path", async () => {
  let calls = 0;
  const client = new SovereignClient(base, async (url) => {
    calls++;
    assert.equal(url, `${base}/api/sovereign/status`);
    return jsonResponse({ sovereign_version: "1.0.0", protocol_version: "1.0.0" });
  });
  const res = await client.status();
  assert.equal(calls, 1);
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data.protocol_version, "1.0.0");
});

test("capabilities negotiation", async () => {
  const client = new SovereignClient(base, async (url) => {
    assert.equal(url, `${base}/api/sovereign/capabilities`);
    return jsonResponse({
      sovereign_version: "1.0.0",
      protocol_version: "1.0.0",
      features: [{ name: "gauntlet", availability: "AVAILABLE" }],
    });
  });
  const res = await client.featureAvailability("gauntlet");
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data, "AVAILABLE");
});

test("preserves UNAVAILABLE on 501", async () => {
  const client = new SovereignClient(base, async () => new Response("", { status: 501 }));
  const res = await client.blastRadius({
    organization_id: "o",
    actor_identity_id: "a",
  });
  assert.equal(res.ok, false);
  if (!res.ok) assert.equal(res.disposition, "UNAVAILABLE");
});

test("mission UNKNOWN disposition preserved", async () => {
  const client = new SovereignClient(base, async () =>
    jsonResponse({ steps: [{ disposition: "UNKNOWN" }] }),
  );
  const res = await client.mission({ organization_id: "o", agent_id: "a", steps: ["x"] });
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data.steps[0].disposition, "UNKNOWN");
});

test("ERROR propagation on 400", async () => {
  const client = new SovereignClient(base, async () => new Response("bad", { status: 400 }));
  const res = await client.trace({ organization_id: "o", evidence_id: "e1" });
  assert.equal(res.ok, false);
  if (!res.ok) {
    assert.equal(res.disposition, "ERROR");
    assert.equal(res.status, 400);
  }
});

test("request serialization for policy lint", async () => {
  const client = new SovereignClient(base, async (url, init) => {
    assert.equal(url, `${base}/api/sovereign/policy/lint`);
    assert.equal(init?.method, "POST");
    const body = JSON.parse(String(init?.body));
    assert.equal(body.organization_id, "org-1");
    assert.deepEqual(body.rules, [{ rule_id: "r1" }]);
    return jsonResponse({ errors: [] });
  });
  const res = await client.policyLint({ organization_id: "org-1", rules: [{ rule_id: "r1" }] });
  assert.equal(res.ok, true);
});

test("endpoint correctness sample", async () => {
  const expected = new Set([
    "/api/sovereign/xray",
    "/api/sovereign/authority/effective",
    "/api/sovereign/evidence/correlate",
    "/api/sovereign/capsules/reproduce",
  ]);
  const client = new SovereignClient(base, async (url) => {
    const path = url.replace(base, "");
    assert.ok(expected.has(path));
    expected.delete(path);
    return jsonResponse({});
  });
  await client.xray({ organization_id: "o" });
  await client.authorityEffective({ organization_id: "o" });
  await client.evidenceCorrelate({ organization_id: "o", evidence_id: "e" });
  await client.capsuleReproduce({ capsule: { capsule_id: "c" } });
  assert.equal(expected.size, 0);
});

test("shadow never blindly retry — single POST attempt on network error", async () => {
  let attempts = 0;
  const client = new SovereignClient(base, async () => {
    attempts++;
    throw new Error("network");
  });
  assert.equal(retryClass("shadow"), "NEVER_BLINDLY_RETRY");
  const res = await client.shadow({
    organization_id: "o",
    agent_id: "a",
    action_type: "read",
  });
  assert.equal(attempts, 1);
  assert.equal(res.ok, false);
});

test("status may retry SAFE GET on transient network error", async () => {
  let attempts = 0;
  const client = new SovereignClient(base, async () => {
    attempts++;
    if (attempts === 1) throw new Error("transient");
    return jsonResponse({ sovereign_version: "1", protocol_version: "1" });
  });
  const res = await client.status();
  assert.equal(attempts, 2);
  assert.equal(res.ok, true);
});

test("gauntlet UNAVAILABLE case preserved", async () => {
  const client = new SovereignClient(base, async () =>
    jsonResponse({ cases: [{ status: "UNAVAILABLE" }] }),
  );
  const res = await client.gauntlet({ organization_id: "o" });
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data.cases[0].status, "UNAVAILABLE");
});
