// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Browser UI fixtures only; not customer authentication or authority acceptance.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const origin = new URL(process.env.WHITEPACT_TEST_BASE_URL);
assert.equal(origin.hostname, "127.0.0.1");
assert.equal(origin.protocol, "http:");
assert(!origin.username && !origin.password && !origin.search && !origin.hash);
const browser = await chromium.launch({ headless: true });
const checks = [];
const violations = [];
let mutations = 0;
try {
  for (const width of [375, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    const session = { user: { full_name: "UI Fixture Owner", email: "fixture@example.invalid" }, organization: { id: "fixture-org", name: "Browser fixture workspace", plan: "FREE", role: "OWNER" } };
    let mode = "pending";
    let statusReads = 0;
    let release;
    const pending = new Promise((resolve) => { release = resolve; });
    await context.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== origin.origin) return route.abort();
      if (!url.pathname.startsWith("/api/")) return route.continue();
      if (request.method() !== "GET") { mutations++; return route.abort(); }
      if (url.pathname === "/api/v1/web/session") return route.fulfill({ json: session });
      if (url.pathname === "/api/enterprise/organizations/fixture-org/authority/agents") return route.fulfill({ json: { agents: [] } });
      if (url.pathname === "/api/enterprise/organizations/fixture-org/authority/status") {
        statusReads++;
        const selected = mode;
        if (selected === "pending") await pending;
        if (selected === "unavailable") return route.fulfill({ status: 503, json: { detail: "Browser fixture unavailable" } });
        if (selected === "expired") return route.fulfill({ status: 401, json: { detail: "Browser fixture expired" } });
        const active = selected === "active" || selected === "foreign";
        return route.fulfill({ json: { organization_id: selected === "foreign" ? "foreign-fixture" : "fixture-org", has_active_authority: active, root_authority: active ? { root_id: `root-${"a".repeat(180)}` } : null, consent_proof: active ? { consent_id: `consent-${"b".repeat(180)}` } : null, revocation_epoch: 7 } });
      }
      return route.fulfill({ status: 404, json: { detail: "No browser fixture" } });
    });
    const page = await context.newPage();
    async function audit(label) {
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `${label}: viewport overflow`);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      violations.push(...result.violations.map((item) => ({ label, width, id: item.id, targets: item.nodes.map((node) => node.target) })));
      checks.push({ label, width });
    }
    await page.goto(new URL("/dashboard/agents", origin).href);
    const panel = page.getByRole("region", { name: "Reported root and consent records" });
    const read = panel.getByRole("button", { name: "Read reported root and consent status" });
    await read.waitFor();
    assert.equal(statusReads, 0);
    await audit("unrequested record-status UI fixture");
    await read.focus();
    await page.keyboard.press("Enter");
    await panel.getByRole("status").filter({ hasText: "Loading reported" }).waitFor();
    assert.equal(await panel.getAttribute("aria-busy"), "true");
    assert.equal(await panel.getByRole("button", { name: "Refresh reported status" }).isDisabled(), true);
    await audit("pending record-status UI fixture");
    release();
    await panel.getByRole("status").filter({ hasText: "did not report an active" }).waitFor();
    assert.equal(statusReads, 1);
    await audit("inactive record-pair UI fixture");

    mode = "unavailable";
    await panel.getByRole("button", { name: "Refresh reported status" }).click();
    await panel.getByRole("alert").filter({ hasText: "No inactive or successful state is inferred" }).waitFor();
    assert.equal(await panel.getByText("Reported revocation epoch", { exact: true }).count(), 0);
    assert.equal(statusReads, 2);
    await audit("failed refresh UI fixture");

    mode = "active";
    await panel.getByRole("button", { name: "Retry status read" }).focus();
    await page.keyboard.press("Enter");
    await panel.getByRole("status").filter({ hasText: "This is not execution authority" }).waitFor();
    assert.equal(await panel.getByText(`root-${"a".repeat(180)}`, { exact: true }).count(), 1);
    await audit("reported record-pair UI fixture with long identifiers");

    mode = "foreign";
    await panel.getByRole("button", { name: "Refresh reported status" }).click();
    await panel.getByRole("alert").waitFor();
    assert.equal(await panel.getByText(`root-${"a".repeat(180)}`, { exact: true }).count(), 0);
    await audit("foreign payload rejected UI fixture");

    mode = "expired";
    await panel.getByRole("button", { name: "Retry status read" }).click();
    await panel.getByRole("alert").filter({ hasText: "session has expired" }).waitFor();
    assert.equal(await panel.getByRole("link", { name: "Sign in again" }).getAttribute("href"), "/login?next=%2Fdashboard%2Fagents");
    assert.equal(statusReads, 5);
    assert.equal(await page.getByRole("button", { name: /register|delegate|disable|execute|authorize|grant|revoke/i }).count(), 0);
    await audit("expired read UI fixture");
    await context.close();
  }
  console.log(JSON.stringify({ kind: "BROWSER_UI_FIXTURES_NOT_CUSTOMER_AUTHENTICATION_OR_AUTHORITY", browser: browser.version(), checks, violations, mutations }));
  assert.equal(mutations, 0);
  assert.equal(violations.length, 0, "Accessibility violations above require review");
} finally { await browser.close(); }
