// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Exercises production-built public HTML without provisioning external infrastructure.
import assert from "node:assert/strict";
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const built = path.join(root, "src/responsibleai/dashboard/static/whitepact");
const routes = ["/", "/product", "/architecture", "/developers", "/docs", "/security", "/enterprise", "/trust", "/about", "/contact", "/pricing", "/privacy", "/terms", "/refund-policy", "/sovereign"];
const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const relative = url.pathname.startsWith("/static/whitepact/") ? url.pathname.slice("/static/whitepact/".length) : routes.includes(url.pathname) ? `pages/${url.pathname === "/" ? "home" : url.pathname.slice(1)}.html` : "pages/private.html";
  const filename = path.resolve(built, relative);
  if (!filename.startsWith(built + path.sep) || !fs.existsSync(filename)) { res.writeHead(404).end(); return; }
  res.writeHead(200, { "Content-Type": mime[path.extname(filename)] ?? "application/octet-stream" });
  fs.createReadStream(filename).pipe(res);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
console.log(`Local production-built public preview: ${origin}`);
const browser = await chromium.launch({ headless: true });
const failures = [];
const widths = [375, 390, 430, 768, 820, 1024, 1280, 1440, 1600, 1920];
const screenshotDirectory = process.env.WHITEPACT_WEBSITE_SCREENSHOTS;
if (screenshotDirectory) {
  assert.ok(path.isAbsolute(screenshotDirectory), "screenshot directory must be absolute");
  assert.ok(!path.resolve(screenshotDirectory).startsWith(root + path.sep), "screenshots must remain outside the repository");
  fs.mkdirSync(screenshotDirectory, { recursive: true });
}
let scans = 0;
let layouts = 0;
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  for (const width of widths) {
    console.log(`Checking ${routes.length} public routes at ${width}px`);
    await page.setViewportSize({ width, height: 900 });
    for (const route of routes) {
      const errors = [];
      const onError = error => errors.push(error.message);
      page.on("pageerror", onError);
      await page.goto(origin + route, { waitUntil: "networkidle" });
      await page.getByRole("heading", { level: 1 }).waitFor();
      try {
        assert.equal(await page.getByRole("heading", { level: 1 }).count(), 1);
        assert.equal(await page.getByRole("main").getAttribute("id"), "main-content");
        await page.getByRole("link", { name: "Skip to main content" }).focus();
        await page.keyboard.press("Enter");
        assert.equal(await page.getByRole("main").evaluate(element => element === document.activeElement), true, `${route} skip focus`);
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${route} overflow at ${width}`);
        assert.deepEqual(errors, [], `${route} runtime error`);
        for (const diagram of await page.locator("figure").all()) {
          assert.ok((await diagram.innerText()).trim().length > 0, `${route} diagram has readable semantic equivalent`);
        }
        if (width < 1190) {
          const toggle = page.getByRole("button", { name: "Open menu" });
          await toggle.click();
          await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Product", exact: true }).waitFor({ state: "visible" });
          await page.keyboard.press("Escape");
          assert.equal(await toggle.getAttribute("aria-expanded"), "false");
          assert.equal(await toggle.evaluate(element => element === document.activeElement), true);
        } else {
          assert.equal(await page.getByRole("navigation", { name: "Primary navigation" }).isVisible(), true);
        }
        const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
        const violations = axe.violations.filter(v => ["critical", "serious"].includes(v.impact));
        assert.deepEqual(violations.map(v => ({ id: v.id, nodes: v.nodes.map(n => n.target) })), [], `${route} axe at ${width}`);
        scans += 1;
        layouts += 1;
        if (screenshotDirectory && [375, 390, 1440].includes(width)) await page.screenshot({ path: path.join(screenshotDirectory, `${route === "/" ? "home" : route.slice(1)}-${width}.png`), fullPage: true });
      } catch (error) { failures.push(error.message); }
      page.off("pageerror", onError);
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(origin + "/docs", { waitUntil: "networkidle" });
  for (const disclosure of await page.locator("details").all()) {
    const summary = disclosure.locator("summary");
    assert.ok((await summary.innerText()).trim(), "documentation disclosure has a name");
    await summary.focus();
    const before = await disclosure.evaluate(element => element.open);
    await page.keyboard.press("Enter");
    assert.equal(await disclosure.evaluate(element => element.open), !before, "native disclosure opens with keyboard");
    await page.keyboard.press("Enter");
    assert.equal(await disclosure.evaluate(element => element.open), before);
  }
  for (const code of await page.locator("pre").all()) {
    assert.equal(await code.getAttribute("tabindex"), "0", "code scrolling is keyboard reachable");
    await code.focus();
    await page.keyboard.press("ArrowRight");
  }
  await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Architecture", exact: true }).click();
  await page.getByRole("heading", { level: 1 }).filter({ hasText: "authority" }).waitFor();
  assert.equal(new URL(page.url()).pathname, "/architecture");
  assert.equal(await page.getByRole("navigation", { name: "Primary navigation" }).getByRole("link", { name: "Architecture", exact: true }).getAttribute("aria-current"), "page");
  const requests = [];
  page.on("request", request => requests.push(request.url()));
  await page.goto(origin, { waitUntil: "networkidle" });
  assert.equal(requests.some(url => /TrustCore-.*\.js/.test(url)), false, "3D loaded before opt-in");
  await page.getByRole("tab", { name: "Delete repository" }).click();
  assert.equal(await page.getByRole("tabpanel").getByText("REQUIRE APPROVAL").count(), 0);
  await page.getByRole("button", { name: "Inspect decision" }).click();
  assert.match(await page.getByRole("dialog").innerText(), /NOT AVAILABLE FOR DENIED AUTHORITY/);
  await page.keyboard.press("Escape");
  await page.getByRole("tab", { name: "Transfer funds" }).focus();
  await page.keyboard.press("ArrowRight");
  assert.equal(await page.getByRole("tab", { name: "Send sensitive email" }).getAttribute("aria-selected"), "true");
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.reload({ waitUntil: "networkidle" });
  assert.equal(await page.getByRole("button", { name: "Enable optional 3D illustration" }).isVisible().catch(() => false), false);
  // Browser-equivalent 200% layout viewport (1440 physical pixels / 2) plus
  // explicit text scaling. This is a reflow check, not a claim of OS-level zoom.
  for (const route of routes) {
    await page.setViewportSize({ width: 720, height: 450 });
    await page.goto(origin + route, { waitUntil: "networkidle" });
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${route} 200% equivalent reflow`);
    const textScale = await page.evaluate(() => {
      const elements = Array.from(document.querySelectorAll("main *, header *, footer *"));
      const sizes = elements.map(element => [element, parseFloat(getComputedStyle(element).fontSize)]);
      const sample = document.querySelector("main p");
      const before = parseFloat(getComputedStyle(sample).fontSize);
      // Snapshot first, then apply bottom-up: inherited sizes cannot compound.
      for (const [element, size] of sizes.reverse()) element.style.setProperty("font-size", `${size * 2}px`, "important");
      return { before, after: parseFloat(getComputedStyle(sample).fontSize), sample: sample.outerHTML.slice(0, 500) };
    });
    await page.waitForTimeout(400);
    textScale.after = await page.locator("main p").first().evaluate(element => parseFloat(getComputedStyle(element).fontSize));
    assert.equal(textScale.after, textScale.before * 2, `${route} actual text enlargement: ${textScale.sample}`);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1), `${route} 200% text scaling overflow`);
    assert.equal(await page.getByRole("heading", { level: 1 }).isVisible(), true);
  }
  const noJs = await browser.newContext({ javaScriptEnabled: false });
  const staticPage = await noJs.newPage();
  for (const route of routes) {
    await staticPage.goto(origin + route);
    assert.equal(await staticPage.locator("h1").count(), 1, `static H1 ${route}`);
    assert.equal(await staticPage.locator('link[rel="canonical"]').getAttribute("href"), `https://whitepact.com${route}`);
  }
  await noJs.close();
  console.log(JSON.stringify({ axeScansPassed: scans, responsiveLayoutsPassed: layouts, expected: routes.length * widths.length, widths, keyboardAndTruthChecks: "PASS", reducedMotion: "PASS", zoomEquivalentAndTextScalingRoutes: routes.length, noJsRoutes: 15, failures }, null, 2));
  if (failures.length) process.exitCode = 1;
} finally {
  await browser.close();
  await new Promise(resolve => server.close(resolve));
}
