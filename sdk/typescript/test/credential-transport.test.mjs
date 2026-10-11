import assert from "node:assert/strict";
import { test } from "node:test";
import { RAIClient, GovernanceRuntimeClient } from "../dist/index.js";

test("credential clients reject remote HTTP and URL credentials before network access", () => {
  for (const C of [RAIClient, GovernanceRuntimeClient]) for (const baseUrl of [
    "http://remote.example", "http://localhost.evil.example", "https://user:password@example.com", "ftp://127.0.0.1",
  ]) assert.throws(() => new C({ apiKey: "synthetic-local-key", baseUrl }));
});

test("HTTPS and literal loopback remain supported", () => {
  for (const C of [RAIClient, GovernanceRuntimeClient]) for (const baseUrl of [
    "https://example.com", "http://localhost:8765", "http://127.0.0.1:8765", "http://[::1]:8765",
  ]) new C({ apiKey: "synthetic-local-key", baseUrl });
});
