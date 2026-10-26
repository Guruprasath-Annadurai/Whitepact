// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Prepared read-only qualification harness; no production default or deployment.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { output, smoke } from "../../web/tooling/launch-contract.mjs";

assert.ok(process.env.BASE_URL, "Explicit authorized BASE_URL required");
const target = new URL(process.env.BASE_URL);
assert.equal(target.protocol, "https:", "Post-deployment target must use HTTPS");
const inventory = JSON.parse(fs.readFileSync(path.join(output, "public-routes.json")));
const expectedOrigin = process.env.EXPECTED_SITE_ORIGIN ?? inventory.origin;
const httpResult = await smoke(target.origin, { expectedOrigin, staging: inventory.profile !== "production" });
assert.equal(httpResult.pass, true, JSON.stringify(httpResult.results.filter(row => !row.pass)));
const browser = await chromium.launch({ headless: true });
const results = [];
try {
  for (const javaScriptEnabled of [true, false]) for (const width of [375, 1440]) {
    const context = await browser.newContext({ javaScriptEnabled, viewport: { width, height: 900 }, reducedMotion: "reduce" });
    const page = await context.newPage();
    const errors = [];
    const unexpectedNetwork = [];
    page.on("pageerror", error => errors.push(error.name));
    await context.route("**/*", async route => {
      const request = new URL(route.request().url());
      if (request.origin !== target.origin && !["data:", "blob:"].includes(request.protocol)) {
        unexpectedNetwork.push(request.origin); await route.abort();
      } else await route.continue();
    });
    for (const route of inventory.routes) {
      errors.length = 0; unexpectedNetwork.length = 0;
      const response = await page.goto(new URL(route, target).href, { waitUntil: "networkidle" });
      assert.equal(response.status(), 200);
      await page.locator("h1").first().waitFor();
      assert.ok(await page.title());
      assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"), expectedOrigin + route);
      assert.ok(await page.locator("main").count());
      const privacy = await page.evaluate(() => ({ local: localStorage.length, session: sessionStorage.length, overflow: document.documentElement.scrollWidth > innerWidth + 1 }));
      assert.deepEqual(privacy, { local: 0, session: 0, overflow: false });
      assert.equal((await context.cookies()).length, 0);
      assert.deepEqual(errors, []);
      assert.deepEqual(unexpectedNetwork, []);
      const accessibility = javaScriptEnabled ? await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze() : null;
      assert.equal(accessibility?.violations.length ?? 0, 0);
      results.push({ route, width, javaScriptEnabled, pass: true });
    }
    await context.close();
  }
} finally { await browser.close(); }
console.log(JSON.stringify({ pass: true, http: httpResult, browserChecks: results, limitations: ["External link targets not contacted; separately authorized link verification required", "Infrastructure HTTP-to-HTTPS redirect, origin protection and rollback need operator evidence", "Lab/browser checks are not field CWV/INP"] }, null, 2));
