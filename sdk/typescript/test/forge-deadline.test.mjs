// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { test } from "node:test";
import { GovernanceRuntimeClient } from "../dist/index.js";

for (const stage of ["headers", "success-body", "error-body"]) {
  test(`deadline settles even when ${stage} ignores abort`, async () => {
    const original = globalThis.fetch;
    let calls = 0;
    const never = () => new Promise(() => {});
    globalThis.fetch = async () => {
      calls++;
      if (stage === "headers") return never();
      return { ok: stage === "success-body", status: stage === "success-body" ? 200 : 503, json: never, text: never };
    };
    let watchdog;
    try {
      const client = new GovernanceRuntimeClient({ apiKey: "synthetic", baseUrl: "http://localhost:8765", timeout: 20 });
      const result = await Promise.race([
        client.getAttestation("e").then(() => "success", error => error.name),
        new Promise(resolve => { watchdog = setTimeout(() => resolve("unbounded"), 1000); }),
      ]);
      assert.equal(result, "AbortError");
      assert.equal(calls, 1);
    } finally {
      clearTimeout(watchdog);
      globalThis.fetch = original;
    }
  });
}
