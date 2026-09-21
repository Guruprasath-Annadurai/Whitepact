import test from "node:test";
import assert from "node:assert/strict";
import { SovereignClient } from "./client.js";

test("maps status endpoint", async () => {
  const client = new SovereignClient("http://x", async (url) => {
    assert.equal(url, "http://x/api/sovereign/status");
    return new Response(JSON.stringify({ sovereign_version: "1.0.0", protocol_version: "1.0.0" }));
  });
  const res = await client.status();
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data.sovereign_version, "1.0.0");
});

test("preserves UNAVAILABLE on 501", async () => {
  const client = new SovereignClient("http://x", async () => new Response("", { status: 501 }));
  const res = await client.blastRadius({ organization_id: "o", actor_identity_id: "a" });
  assert.equal(res.ok, false);
  if (!res.ok) assert.equal(res.disposition, "UNAVAILABLE");
});

test("mission disposition typing path", async () => {
  const client = new SovereignClient("http://x", async () =>
    new Response(
      JSON.stringify({
        steps: [{ disposition: "UNKNOWN" }],
      }),
    ),
  );
  const res = await client.mission({ organization_id: "o", agent_id: "a", steps: ["x"] });
  assert.equal(res.ok, true);
  if (res.ok) assert.equal(res.data.steps[0].disposition, "UNKNOWN");
});
