import assert from "node:assert/strict";
import { afterEach, test } from "node:test";
import { RAIClient, GovernanceRuntimeClient } from "../dist/index.js";

const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

for (const key of ["synthetic-local-secret", "synthetic-" + "x".repeat(250)]) {
  for (const kind of ["general", "governance"]) {
    test(`${kind} redacts reflected credential before truncation (${key.length} characters)`, async () => {
      globalThis.fetch = async () => new Response(`refused Bearer ${key}; ${key}`, { status: 403 });
      const options = { apiKey: key, baseUrl: "https://example.test" };
      const request = kind === "general"
        ? new RAIClient(options).health()
        : new GovernanceRuntimeClient(options).callTool("local");
      await assert.rejects(request, error => {
        assert.equal(error.message.includes(key), false);
        assert.equal(error.message.includes(key.slice(0, 40)), false);
        assert.equal(error.message.includes("[REDACTED]"), true);
        assert.equal(error.status, 403);
        return true;
      });
    });
  }
}
