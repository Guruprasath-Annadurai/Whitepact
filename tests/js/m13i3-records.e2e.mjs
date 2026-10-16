// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Rendered UI fixtures only; separate from the actual CDP customer ceremony.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const origin = new URL(process.env.WHITEPACT_TEST_BASE_URL);
assert.equal(origin.hostname, "127.0.0.1");
const browser = await chromium.launch({ headless: true });
const checks = [];
const violations = [];
let mutations = 0;
try {
  for (const width of [375, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 } });
    let mode = "records";
    const session = { user: { full_name: "UI fixture", email: "fixture@example.invalid" }, organization: { id: "fixture-org", name: "Fixture organization", plan: "FREE", role: "OWNER" } };
    await context.route("**/*", async (route) => {
      const request = route.request(); const url = new URL(request.url());
      if (url.origin !== origin.origin) return route.abort();
      if (!url.pathname.startsWith("/api/")) return route.continue();
      if (request.method() !== "GET") { mutations++; return route.abort(); }
      if (url.pathname === "/api/v1/web/session") return route.fulfill({ json: session });
      if (url.pathname.endsWith("/authority/agents")) return route.fulfill({ json: { agents: [] } });
      if (url.pathname.endsWith("/authority/status")) {
        if (mode === "expired") return route.fulfill({ status: 401, json: {} });
        if (mode === "unavailable") return route.fulfill({ status: 503, json: {} });
        return route.fulfill({ json: { organization_id: mode === "foreign" ? "foreign-org" : "fixture-org", has_active_authority: true, revocation_epoch: 3,
          root_authority: { root_id: "root-fixture", subject_id: "subject-fixture", issuer: "W".repeat(200), root_type: "CUSTOMER", verification_method: "Browser fixture only", issued_at: "2025-01-01T00:00:00Z", expires_at: "2025-02-01T00:00:00Z", canonical_digest: "a".repeat(64) },
          consent_proof: { consent_id: "consent-fixture", scope_description: "s".repeat(1000), purpose: "Fixture purpose", consent_method: "CRYPTOGRAPHIC_CEREMONY", allowed_action_types: ["local:read"], allowed_targets: Array.from({ length: 20 }, (_, index) => `local-${index}-${"t".repeat(200)}`), consented_at: "2025-01-01T00:00:00Z", canonical_digest: "b".repeat(64) } } });
      }
      return route.fulfill({ status: 404, json: {} });
    });
    const page = await context.newPage();
    const audit = async (label) => {
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), label);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      violations.push(...result.violations.map((item) => ({ width, label, id: item.id })));
      checks.push({ width, label });
    };
    await page.goto(new URL("/dashboard/agents", origin).href);
    const panel = page.getByRole("region", { name: "Recorded consent and root details" });
    const read = panel.getByRole("button", { name: "Read recorded consent details" });
    await read.focus(); await page.keyboard.press("Enter");
    await panel.getByText("Fixture purpose", { exact: true }).waitFor();
    assert.equal(await panel.getByRole("list", { name: "Recorded consent targets" }).getByRole("listitem").count(), 10);
    assert.equal(await panel.getByRole("button").count(), 1);
    await audit("recorded metadata with long scope, bounded entries and no permission claim");
    mode = "unavailable";
    await panel.getByRole("button", { name: "Refresh recorded details" }).click();
    await panel.getByRole("alert").waitFor();
    assert.equal(await panel.getByText("Fixture purpose", { exact: true }).count(), 0);
    await audit("lost detail refresh hides prior consent");
    mode = "foreign";
    await panel.getByRole("button", { name: "Retry detail read" }).click();
    await panel.getByRole("alert").waitFor();
    assert.equal(await panel.getByText("consent-fixture", { exact: true }).count(), 0);
    await audit("foreign recorded details rejected");
    mode = "expired";
    await panel.getByRole("button", { name: "Retry detail read" }).click();
    await panel.getByRole("link", { name: "Sign in again" }).waitFor();
    await audit("expired detail session offers sign-in");
    await context.close();
  }
  console.log(JSON.stringify({ kind: "BROWSER_UI_FIXTURES_NOT_CUSTOMER_AUTHENTICATION_OR_AUTHORITY", browser: browser.version(), checks, violations, mutations }));
  assert.equal(mutations, 0); assert.equal(violations.length, 0);
} finally { await browser.close(); }
