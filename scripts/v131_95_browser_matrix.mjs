import { chromium, firefox, webkit } from "playwright";
import fs from "node:fs";
import path from "node:path";

const baseUrl = process.env.WHITEPACT_95_BASE_URL ?? "http://127.0.0.1:18765";
const outDir = process.env.WHITEPACT_95_ARTIFACTS ?? "/opt/cursor/artifacts/v131_95/browser";
fs.mkdirSync(outDir, { recursive: true });

const routes = [
  "/",
  "/signup",
  "/login",
  "/onboarding",
  "/dashboard",
  "/dashboard/api-keys",
  "/dashboard/approvals",
  "/dashboard/evidence",
  "/dashboard/billing",
];

const viewports = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "tablet", width: 834, height: 1112 },
  { name: "mobile", width: 390, height: 844 },
];

const engines = [
  { name: "chromium", launcher: chromium },
  { name: "firefox", launcher: firefox },
  { name: "webkit", launcher: webkit },
];

const rows = [];

for (const engine of engines) {
  let browser;
  try {
    browser = await engine.launcher.launch({ headless: true });
  } catch (err) {
    for (const vp of viewports) {
      for (const route of routes) {
        rows.push({
          engine: engine.name,
          viewport: vp.name,
          route,
          status: "BLOCKED",
          error: String(err),
        });
      }
    }
    continue;
  }
  for (const vp of viewports) {
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
    const page = await context.newPage();
    const consoleErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    for (const route of routes) {
      const shot = path.join(outDir, `${engine.name}-${vp.name}-${route.replaceAll("/", "_")}.png`);
      let status = "PASS";
      try {
        const resp = await page.goto(`${baseUrl}${route}`, { waitUntil: "domcontentloaded", timeout: 20000 });
        if (!resp || resp.status() >= 500) status = "FAIL";
        await page.screenshot({ path: shot, fullPage: true });
        if (consoleErrors.length > 5) status = "FAIL";
      } catch (err) {
        status = "FAIL";
        rows.push({ engine: engine.name, viewport: vp.name, route, status, error: String(err), screenshot: shot });
        continue;
      }
      rows.push({
        engine: engine.name,
        viewport: vp.name,
        route,
        status,
        screenshot: shot,
        console_errors: consoleErrors.slice(-3),
      });
    }
    await context.close();
  }
  await browser.close();
}

const md = [
  "# Browser matrix (9.5 closure)",
  "",
  "| engine | viewport | route | status | evidence |",
  "|---|---|---|---|---|",
  ...rows.map(
    (r) => `| ${r.engine} | ${r.viewport} | ${r.route} | ${r.status} | ${r.screenshot ?? r.error ?? ""} |`,
  ),
  "",
  "```json",
  JSON.stringify(rows, null, 2),
  "```",
].join("\n");

fs.writeFileSync(path.join(outDir, "WHITEPACT_V131_95_BROWSER_MATRIX.md"), md);
console.log(md.slice(0, 4000));
