// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Repeatable local laboratory measurement, not field CWV or measured INP.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const built = path.join(root, "src/responsibleai/dashboard/static/whitepact");
const server = http.createServer((req, res) => {
  const url = new URL(req.url, "http://localhost");
  const relative = url.pathname.startsWith("/static/whitepact/") ? url.pathname.slice(18) : "pages/home.html";
  const filename = path.resolve(built, relative);
  if (!filename.startsWith(built + path.sep) || !fs.existsSync(filename)) { res.writeHead(404).end(); return; }
  const type = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2" };
  res.writeHead(200, { "Content-Type": type[path.extname(filename)] ?? "application/octet-stream" });
  fs.createReadStream(filename).pipe(res);
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
const browser = await chromium.launch({ headless: true });
const measurements = [];
try {
  for (const profile of [{ name: "mobile", width: 390, latency: 150, throughput: 200000, cpu: 4 }, { name: "desktop", width: 1440, latency: 40, throughput: 1250000, cpu: 1 }]) {
    for (let run = 1; run <= 3; run += 1) {
      const context = await browser.newContext({ viewport: { width: profile.width, height: 900 }, reducedMotion: "reduce" });
      const page = await context.newPage();
      await page.addInitScript(() => {
        window.lab = { lcp: null, cls: 0, longTasks: [] };
        new PerformanceObserver(list => { window.lab.lcp = list.getEntries().at(-1)?.startTime ?? null; }).observe({ type: "largest-contentful-paint", buffered: true });
        new PerformanceObserver(list => { for (const entry of list.getEntries()) if (!entry.hadRecentInput) window.lab.cls += entry.value; }).observe({ type: "layout-shift", buffered: true });
        new PerformanceObserver(list => { window.lab.longTasks.push(...list.getEntries().map(entry => entry.duration)); }).observe({ type: "longtask", buffered: true });
      });
      const cdp = await context.newCDPSession(page);
      await cdp.send("Network.enable");
      await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
      await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: profile.latency, downloadThroughput: profile.throughput, uploadThroughput: profile.throughput });
      await cdp.send("Emulation.setCPUThrottlingRate", { rate: profile.cpu });
      await page.goto(`http://127.0.0.1:${server.address().port}`, { waitUntil: "networkidle" });
      await page.getByRole("heading", { level: 1 }).waitFor();
      await page.waitForTimeout(2000);
      measurements.push(await page.evaluate(({ profile, run }) => {
        const nav = performance.getEntriesByType("navigation")[0];
        const resources = performance.getEntriesByType("resource");
        return { profile: profile.name, run, width: profile.width, latencyMs: profile.latency, throughputBytesPerSecond: profile.throughput, cpuSlowdown: profile.cpu, lcpMs: window.lab.lcp, cls: window.lab.cls, domContentLoadedMs: nav.domContentLoadedEventEnd, loadMs: nav.loadEventEnd, longTaskCount: window.lab.longTasks.length, longTaskTotalMs: window.lab.longTasks.reduce((a, b) => a + b, 0), resources: resources.length, transferBytes: resources.reduce((a, b) => a + b.transferSize, nav.transferSize), decodedBytes: resources.reduce((a, b) => a + b.decodedBodySize, nav.decodedBodySize), optional3DLoaded: resources.some(entry => /TrustCore-.*\.js/.test(entry.name)) };
      }, { profile, run }));
      await context.close();
    }
  }
  console.log(JSON.stringify({ kind: "LOCAL_LAB_NOT_FIELD_CWV", inp: "NOT_MEASURED", cache: "disabled", browser: browser.version(), measurements }, null, 2));
} finally { await browser.close(); await new Promise(resolve => server.close(resolve)); }
