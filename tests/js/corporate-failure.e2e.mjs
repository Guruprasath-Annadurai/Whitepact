// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

export async function verifyCorporateFailureModes(browser, origin, routes) {
  assert.equal(new URL(origin).hostname, "127.0.0.1", "failure injection is localhost-only");
  const blocked = await browser.newContext({ viewport: { width: 320, height: 900 } });
  try {
    await blocked.route("**/*", route => /\.(?:js|woff2|png|webp)(?:\?|$)/.test(route.request().url()) ? route.abort() : route.continue());
    const page = await blocked.newPage();
    for (const path of routes) {
      await page.goto(origin + path, { waitUntil: "networkidle" });
      assert.equal(await page.locator("h1").count(), 1, `${path} has static readable content`);
      assert.ok(await page.locator('a[href="/contact"]').count(), `${path} keeps evaluation navigation`);
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${path} missing-asset reflow`);
    }
  } finally { await blocked.close(); }

  const delayed = await browser.newContext();
  try {
    await delayed.route("**/*.js", async route => {
      await new Promise(resolve => setTimeout(resolve, 1000));
      await route.continue();
    });
    const page = await delayed.newPage();
    await page.goto(origin, { waitUntil: "commit" });
    await page.locator("h1").waitFor();
    assert.ok(await page.locator('a[href="/docs"]').count(), "docs remains a genuine link during JS delay");
    await page.waitForLoadState("networkidle");
    await page.getByRole("tab", { name: "Delete repository" }).click();
    assert.equal(await page.getByRole("tab", { name: "Delete repository" }).getAttribute("aria-selected"), "true", "interaction works after hydration");
    await delayed.setOffline(true);
    assert.equal(await page.locator("h1").isVisible(), true, "connection loss after load preserves content");
  } finally { await delayed.close(); }

  const clipboard = await browser.newContext();
  try {
    await clipboard.addInitScript(() => {
      Object.defineProperty(navigator, "clipboard", { value: { writeText: async () => { throw new Error("Clipboard denied by test"); } }, configurable: true });
    });
    const page = await clipboard.newPage();
    const errors = [];
    page.on("pageerror", error => errors.push(error.message));
    await page.goto(origin + "/docs", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: /^Copy / }).first().click();
    await page.getByRole("status").filter({ hasText: "Clipboard unavailable. Select and copy the example manually." }).waitFor();
    assert.deepEqual(errors, [], "clipboard denial is handled, not an unhandled rejection");
  } finally { await clipboard.close(); }
  console.log(JSON.stringify({ assetAndScriptFailureRoutes: routes.length, delayedHydration: "PASS", offlineAfterLoad: "PASS", clipboardDenial: "PASS" }));
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const browser = await chromium.launch({ headless: true });
  try { await verifyCorporateFailureModes(browser, process.argv[2], ["/", "/product", "/architecture", "/developers", "/docs", "/security", "/enterprise", "/trust", "/about", "/contact", "/pricing", "/privacy", "/terms", "/refund-policy", "/sovereign"]); }
  finally { await browser.close(); }
}
