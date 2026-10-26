// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Source-bound logging guard, not real customer-journey qualification.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

test("registration diagnostics omit response bodies and verification URLs", () => {
  const source = readFileSync(new URL("./customer-journey.e2e.mjs", import.meta.url), "utf8");
  assert.match(source, /console\.log\("register HTTP status", registerResponse\.status\(\)\)/);
  assert.doesNotMatch(source, /console\.(log|error)\([^\n]*(registerBody|verification_url|page\.url\(\))/);
  assert.doesNotMatch(source, /authority fixture exit[^\n]*(seed\.stderr|seed\.stdout)/);
});
