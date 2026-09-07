// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const base = process.env.WHITEPACT_TEST_BASE_URL ?? "http://127.0.0.1:8871";
const screenshots = process.env.WHITEPACT_SCREENSHOT_DIR ?? "/private/tmp/whitepact-paddle-qa";
const paths = ["/", "/pricing", "/terms", "/privacy", "/refund-policy"];
await mkdir(screenshots, { recursive: true });
const browser = await chromium.launch({ headless: true });
try {
  for (const javaScriptEnabled of [true, false]) {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ javaScriptEnabled, viewport: { width, height: 900 }, reducedMotion: "reduce" });
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
      for (const path of paths) {
        assert.equal((await page.goto(`${base}${path}`)).status(), 200);
        await page.locator("h1").waitFor();
        assert.ok((await page.locator("h1").innerText()).trim());
        assert.equal(await page.locator('link[rel="canonical"]').getAttribute("href"), `https://whitepact.com${path}`);
        assert.equal(await page.locator('meta[name="robots"]').getAttribute("content"), "index, follow");
        assert.ok(await page.locator('meta[name="description"]').getAttribute("content"));
        assert.equal(await page.locator("vite-error-overlay").count(), 0);
        if (path === "/" || path === "/pricing") {
          const cards = page.locator('.launch-pricing');
          const copy = await cards.innerText();
          for (const price of ["$0 forever", "$0/year", "$29/month", "$290/year", "$99/month", "$990/year", "Custom annual pricing"]) assert.ok(copy.includes(price), `Missing price ${price}`);
          assert.equal(await cards.getByText("Early Access", { exact: true }).count(), 2);
          assert.equal(await cards.locator('a[href="/contact"]').count(), 3);
          assert.doesNotMatch(copy, /Buy now|SSO|SCIM|SLA|certified|%/i);
        }
        const footer = page.getByRole("navigation", { name: "Public footer" });
        for (const target of paths.slice(1)) {
          assert.equal(await footer.locator(`a[href="${target}"]`).count(), 1);
        }
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${path}: overflow at ${width}, JS=${javaScriptEnabled}`);
        if (javaScriptEnabled) {
          const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa"]).analyze();
          assert.deepEqual(scan.violations.filter((v) => ["serious", "critical"].includes(v.impact)), [], `${path}: accessibility`);
        }
        await page.screenshot({ path: `${screenshots}/${path.slice(1) || "home"}-${width}-${javaScriptEnabled ? "js" : "static"}.png` });
        assert.equal((await page.reload()).status(), 200);
        console.log(`PASS ${path} width=${width} JavaScript=${javaScriptEnabled}: content, metadata, footer, reload, overflow${javaScriptEnabled ? ", Axe" : " (Axe requires JavaScript)"}`);
      }
      await page.goto(base);
      const refund = page.getByRole("navigation", { name: "Public footer" }).getByRole("link", { name: "Refund Policy" });
      await refund.focus();
      assert.ok(await refund.evaluate((element) => document.activeElement === element));
      const focus = await refund.evaluate((element) => ({ outline: getComputedStyle(element).outlineStyle, width: getComputedStyle(element).outlineWidth }));
      assert.notEqual(focus.outline, "none");
      assert.notEqual(focus.width, "0px");
      await page.keyboard.press("Enter");
      await page.waitForURL(`${base}/refund-policy`);
      await page.getByRole("heading", { level: 1, name: /Refund Policy/ }).waitFor();
      assert.deepEqual(errors, [], "Unexpected browser errors");
      await context.close();
    }
  }
  const request = await browser.newContext();
  const page = await request.newPage();
  assert.equal((await page.goto(`${base}/definitely-does-not-exist`)).status(), 404);
  const redirect = await request.request.get(`${base}/refunds`, { maxRedirects: 0 });
  assert.equal(redirect.status(), 308);
  assert.equal(redirect.headers().location, "/refund-policy");
  // Check every local link rendered by the required pages, not remote providers.
  const links = new Set();
  for (const path of paths) {
    await page.goto(`${base}${path}`);
    await page.locator("h1").waitFor();
    for (const href of await page.locator('a[href^="/"]').evaluateAll((nodes) => nodes.map((node) => node.getAttribute("href")))) links.add(href.split("#")[0] || "/");
  }
  for (const href of links) assert.ok((await request.request.get(`${base}${href}`)).ok(), `Broken local link: ${href}`);
  await request.close();
  console.log(`PASS real 404, permanent refund redirect, ${links.size} internal links; 20 rendered page/viewport/JS combinations.`);
} finally {
  await browser.close();
}
