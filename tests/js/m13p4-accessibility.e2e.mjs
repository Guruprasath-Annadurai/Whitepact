// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Browser UI fixtures only: no customer authentication, authority or mutation.
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
const session = { user: { full_name: "UI Fixture", email: "fixture@example.invalid" }, organization: { id: "fixture-org", name: "Browser fixture workspace", plan: "FREE" } };
const summary = { decisions: 0, agents: 0, pending_approvals: 0, blocked_actions: 0, recent_governance: [], services: {} };
const agents = Array.from({ length: 11 }, (_, index) => ({
  agent_id: index === 0 ? `agent-${"a".repeat(180)}` : `agent-${index}`,
  organization_id: "fixture-org", display_name: `Browser fixture agent ${index}`,
  lifecycle_state: index === 0 ? "UNKNOWN_FUTURE" : "REGISTERED",
  has_active_delegation: index === 0,
}));
let mutations = 0;
try {
  for (const width of [375, 768, 1280]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    let sessionStatus = 200;
    await context.route("**/*", async (route) => {
      const request = route.request();
      const url = new URL(request.url());
      if (url.origin !== origin.origin) return route.abort();
      if (url.pathname.startsWith("/api/")) {
        if (request.method() !== "GET") { mutations++; return route.abort(); }
        if (url.pathname === "/api/v1/web/session") return route.fulfill({ status: sessionStatus, json: sessionStatus === 200 ? session : { detail: "Unavailable" } });
        if (url.pathname === "/api/v1/web/dashboard/summary") return route.fulfill({ json: summary });
        if (url.pathname === "/api/enterprise/organizations/fixture-org/authority/agents") return route.fulfill({ json: { agents } });
        return route.fulfill({ status: 404, json: { detail: "No browser fixture" } });
      }
      return route.continue();
    });
    const page = await context.newPage();
    async function audit(label) {
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `${label}: viewport overflow`);
      const result = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      violations.push(...result.violations.map((item) => ({ label, width, id: item.id, targets: item.nodes.map((node) => node.target) })));
      checks.push({ label, width });
    }
    for (const path of ["/signup", "/login", "/onboarding"]) {
      await page.goto(new URL(path, origin).href);
      await page.getByRole("heading", { level: 1 }).waitFor();
      await audit(path);
    }
    await page.goto(new URL("/dashboard", origin).href);
    await page.getByRole("heading", { name: "No governed activity yet" }).waitFor();
    await audit("dashboard read fixture");
    const skip = page.getByRole("link", { name: "Skip to workspace content" });
    await skip.focus();
    await page.keyboard.press("Enter");
    assert.equal(await page.locator("#workspace-content").evaluate((node) => document.activeElement === node), true);
    if (width <= 820) {
      const opener = page.getByRole("button", { name: "Open navigation" });
      await opener.click();
      const dialog = page.getByRole("dialog", { name: "Workspace navigation" });
      await dialog.waitFor();
      assert.equal(await opener.getAttribute("aria-expanded"), "true");
      await audit("mobile drawer fixture");
      await page.keyboard.press("Shift+Tab");
      assert.equal(await page.getByRole("button", { name: "Sign out" }).evaluate((node) => document.activeElement === node), true);
      await page.keyboard.press("Escape");
      assert.equal(await opener.evaluate((node) => document.activeElement === node), true);
      assert.equal(await page.getByRole("navigation", { name: "Dashboard" }).count(), 0);
    }
    await page.goto(new URL("/dashboard/agents", origin).href);
    await page.getByRole("heading", { name: "Agent inventory", exact: true }).waitFor();
    await page.getByText("UNKNOWN_FUTURE", { exact: true }).waitFor();
    assert.equal(await page.getByText("Reported active — not execution authority", { exact: true }).count(), 1);
    assert.equal(await page.getByRole("button", { name: /register|delegate|disable|execute|authorize|grant|revoke/i }).count(), 0);
    await audit("agent inventory read fixture");
    const filter = page.getByRole("searchbox", { name: "Filter loaded agent registrations" });
    await filter.fill("no-matching-agent-fixture");
    await page.getByText("No loaded agent registrations match this filter.", { exact: true }).waitFor();
    assert.equal(await page.getByRole("list", { name: "Returned agent registrations" }).getByRole("listitem").count(), 0);
    await audit("agent inventory no-match fixture");
    await filter.fill("");
    await page.getByRole("button", { name: "Next loaded page" }).click();
    await page.getByText("Page 2 of 2", { exact: true }).waitFor();
    assert.equal(await page.getByRole("list", { name: "Returned agent registrations" }).getByRole("listitem").count(), 1);
    assert.equal(await page.getByRole("button", { name: "Next loaded page" }).isDisabled(), true);
    await audit("agent inventory next local page fixture");
    sessionStatus = 403;
    await page.reload();
    await page.getByRole("heading", { name: "Workspace access unavailable" }).waitFor();
    await audit("forbidden session fixture");
    sessionStatus = 401;
    await page.reload();
    await page.getByRole("status").filter({ hasText: "Your session is no longer available" }).waitFor();
    await audit("expired session fixture");
    await context.close();
  }
  console.log(JSON.stringify({ kind: "BROWSER_UI_FIXTURES_NOT_CUSTOMER_AUTHENTICATION_OR_AUTHORITY", browser: browser.version(), checks, violations, mutations }));
  assert.equal(mutations, 0);
  assert.equal(violations.length, 0, "Accessibility violations above require review");
} finally { await browser.close(); }
