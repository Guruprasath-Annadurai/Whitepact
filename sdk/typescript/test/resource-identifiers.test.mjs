// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { GovernanceRuntimeClient } from "../dist/index.js";

const original = globalThis.fetch;
afterEach(() => { globalThis.fetch = original; });
const operations = [
  (c, id) => c.resolveApproval(id, "APPROVED"),
  (c, id) => c.executeApproval(id),
  (c, id) => c.revokeDelegation(id, "test"),
  (c, id) => c.getEvidence(id),
  (c, id) => c.getAttestation(id),
];
const invalid = ["", ".", "..", "../other", "a/b", "a\\b", "a?b", "a#b", "%2e%2e", " a", "a ", "a b", "a\t", "a\n", "a\0", "a\x7f", "a\u00a0b", "a\u0080b", "a\ud800b", null, 42];

test("all malformed resource IDs fail before any authenticated fetch", async () => {
  let requests = 0;
  globalThis.fetch = async () => { requests++; return Response.json({ result: {} }); };
  const client = new GovernanceRuntimeClient({ apiKey: "local-test", baseUrl: "https://wp.test" });
  for (const operation of operations)
    for (const id of invalid)
      await assert.rejects(operation(client, id), /Invalid resource identifier/);
  assert.equal(requests, 0);
});

test("valid resource binding and UNKNOWN are retained", async () => {
  const seen = [];
  globalThis.fetch = async (url, init) => { seen.push({ url, init }); return Response.json({ outcome_status: "UNKNOWN" }); };
  const client = new GovernanceRuntimeClient({ apiKey: "local-test", baseUrl: "https://wp.test" });
  for (const id of ["apr-9", "abc_123", "ev.1", "urn:opaque:123", "évidence"]) {
    const out = await client.getAttestation(id);
    assert.equal(out.outcome_status, "UNKNOWN");
    const request = seen.at(-1);
    assert.equal(request.url, `https://wp.test/api/governance/evidence/${encodeURIComponent(id)}/attestation`);
    assert.equal(request.init.headers.Authorization, "Bearer local-test");
    assert.equal(request.init.body, undefined);
  }
});
