// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Real application/DB public and unauthenticated reads only. No seeded authority.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const origin = new URL(process.env.WHITEPACT_TEST_BASE_URL);
assert.equal(origin.hostname, "127.0.0.1");
assert.equal(origin.protocol, "http:");
assert(!origin.username && !origin.password && !origin.search && !origin.hash);
const browser = await chromium.launch({ headless: true });
let checks = 0;
try {
  for (const width of [375, 768, 1024, 1440]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
    // External resources cannot receive requests from this local acceptance test.
    await context.route("**/*", (route) => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
    const page = await context.newPage();
    for (const path of ["/docs", "/about"]) {
      const response = await page.goto(new URL(path, origin).href);
      assert.equal(response.status(), 200);
      assert(await page.getByRole("main").count());
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)));
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      assert.equal(axe.violations.length, 0, JSON.stringify(axe.violations.map((item) => item.id)));
      checks++;
    }
    const missing = await page.goto(new URL("/m12p-known-missing-route", origin).href);
    assert.equal(missing.status(), 404);
    await page.getByRole("link", { name: /return home/i }).waitFor();
    checks++;
    await page.goto(new URL("/dashboard/evidence", origin).href);
    await page.waitForURL(/\/login\?next=/);
    assert.equal(await page.getByRole("heading", { name: "Evidence details" }).count(), 0);
    const session = await context.request.get(new URL("/api/v1/web/session", origin).href);
    assert.equal(session.status(), 401);
    checks++;
    await context.close();
  }
  console.log(JSON.stringify({ kind: "REAL_APP_PUBLIC_UNAUTHENTICATED_POSTGRESQL_NOT_CUSTOMER_AUTHORITY", checks, mutations: 0 }));
} finally { await browser.close(); }
