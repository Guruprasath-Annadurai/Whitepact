// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Actual compiled browser behavior against explicit local response contracts.
// No fixture is proof of customer root/consent provisioning or Core security.
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";
import { createServer } from "node:http";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const bundle = path.join(root, "src/responsibleai/dashboard/static/whitepact");
const evidenceDir = mkdtempSync(path.join(tmpdir(), "whitepact-m11-browser-"));
const mime = { ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml", ".woff2": "font/woff2", ".html": "text/html" };
const server = createServer((request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  const relative = pathname.startsWith("/static/whitepact/") ? pathname.slice("/static/whitepact/".length) : "index.html";
  const filename = path.resolve(bundle, relative);
  if (!filename.startsWith(bundle + path.sep)) { response.writeHead(403); response.end(); return; }
  try { response.writeHead(200, { "Content-Type": mime[path.extname(filename)] ?? "application/octet-stream" }); response.end(readFileSync(filename)); }
  catch { response.writeHead(404); response.end(); }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
const session = { user: { full_name: "M11 Reviewer", email: "reviewer@example.invalid" }, organization: { id: "local-fixture", name: "Explicit UI Fixture", plan: "FREE", role: "OWNER" } };
const rule = { rule_id: "bounded-rule", reason_code: "REVIEW", effect: "DENY" };
const history = { chain_valid: true, checkpoint_checked: false, head: { version: 1, entry_digest: "a".repeat(64) }, entries: [{ version: 1, change: "rule_added", actor_type: "web_user", actor_id: "reviewer-local", rule_id: rule.rule_id, created_at: "2026-10-14T00:00:00Z", entry_digest: "a".repeat(64) }] };
const record = { evidence_id: "local-evidence", action_type: "supported.action", target: "fixture-target", decision: "QUARANTINE", outcome_status: "UNKNOWN", hash: "returned-hash", api_key: "export-exclusion-canary" };
const results = [];
let browser;
try {
  browser = await chromium.launch({ headless: true });
  for (const width of [375, 768, 1024, 1440]) {
    for (const flow of ["session-outage", "policy-confirmation", "policy-uncertainty", "evidence-export"]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, reducedMotion: "reduce" });
      await context.addCookies([{ name: "wp_csrf", value: "local-ui-csrf", url: origin }]);
      const page = await context.newPage(); const errors = []; let sessionReads = 0; let mutations = 0; let removed = false;
      page.on("pageerror", (error) => errors.push(error.message));
      await context.route("**/*", async (route) => {
        const request = route.request(); const url = new URL(request.url());
        if (url.origin !== origin) return route.abort();
        if (!url.pathname.startsWith("/api/")) return route.continue();
        if (url.pathname.endsWith("/session")) {
          sessionReads++;
          if (flow === "session-outage" && sessionReads === 1) return route.fulfill({ status: 503, json: { detail: "provider unavailable" } });
          return route.fulfill({ json: session });
        }
        if (url.pathname.endsWith("/summary")) return route.fulfill({ json: { decisions: 0, agents: 0, pending_approvals: 0, blocked_actions: 0, recent_governance: [], services: {} } });
        if (url.pathname.endsWith("/history")) { assert.equal(url.searchParams.get("limit"), "100"); return route.fulfill({ json: history }); }
        if (url.pathname.includes("/policy") && request.method() !== "GET") {
          mutations++; assert.equal(request.headers()["x-wp-csrf"], "local-ui-csrf");
          if (flow === "policy-uncertainty") return route.abort();
          assert.equal(request.method(), "DELETE"); removed = true;
          return route.fulfill({ json: { status: "removed", rule_id: rule.rule_id } });
        }
        if (url.pathname.endsWith("/policy")) return route.fulfill({ json: { org_id: "local-fixture", can_edit: true, rules: flow === "policy-uncertainty" || removed ? [] : [rule] } });
        if (url.pathname.endsWith("/verify")) return route.fulfill({ json: { org_id: "local-fixture", status: "VALID", chain_intact: true, cryptographically_signed: false, integrity_note: "Explicit returned fixture verification" } });
        if (url.pathname.includes("/evidence")) return route.fulfill({ json: url.pathname.endsWith("/evidence") && url.pathname.includes("dashboard") ? { items: [record], source: "explicit-ui-fixture" } : { evidence: [record] } });
        return route.fulfill({ json: { items: [], source: "explicit-ui-fixture" } });
      });
      const route = flow.startsWith("policy") ? "/dashboard/policy" : flow === "evidence-export" ? "/dashboard/evidence" : "/dashboard";
      await page.goto(origin + route);
      if (flow === "session-outage") {
        await page.getByRole("heading", { name: "Session verification unavailable" }).waitFor();
        assert(!page.url().includes("login"));
        await page.getByRole("button", { name: "Retry session verification" }).click();
        await page.getByRole("heading", { name: "No governed activity yet", exact: true }).waitFor();
        assert.equal(mutations, 0);
      } else if (flow === "policy-confirmation") {
        await page.getByRole("button", { name: "Load policy history" }).click();
        await page.getByText("No external checkpoint was checked.", { exact: false }).waitFor();
        await page.getByRole("button", { name: "Remove rule", exact: true }).click();
        const dialog = page.getByRole("dialog", { name: "Remove policy rule?" }); await dialog.waitFor();
        assert(await dialog.evaluate((node) => node.contains(document.activeElement)));
        assert.equal(mutations, 0);
        await page.getByRole("button", { name: "Confirm removal" }).click();
        await page.getByText("No rules configured yet.").waitFor(); assert.equal(mutations, 1);
      } else if (flow === "policy-uncertainty") {
        await page.getByRole("textbox", { name: "Rule ID" }).fill("new-rule");
        await page.getByRole("textbox", { name: "Reason code" }).fill("REVIEW");
        await page.getByRole("button", { name: "Add rule" }).click();
        await page.getByRole("heading", { name: "Policy change outcome is uncertain" }).waitFor();
        assert(await page.getByRole("button", { name: "Add rule" }).isDisabled()); assert.equal(mutations, 1);
        await page.getByRole("button", { name: "Reload canonical policy" }).click();
        await page.getByRole("heading", { name: "Policy change outcome is uncertain" }).waitFor({ state: "hidden" }); assert.equal(mutations, 1);
      } else {
        await page.getByRole("combobox", { name: "Decision" }).selectOption("QUARANTINE");
        await page.getByText("QUARANTINE", { exact: true }).waitFor();
        const downloaded = page.waitForEvent("download");
        await page.getByRole("button", { name: "Download displayed records" }).click();
        const download = await downloaded; const contents = readFileSync(await download.path(), "utf8");
        assert(!contents.includes("export-exclusion-canary")); assert(contents.includes("UNKNOWN")); assert(contents.includes("not complete history")); assert.equal(mutations, 0);
      }
      assert.equal(errors.length, 0, errors.join("\n"));
      assert(!(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1)), `${flow} horizontal overflow at ${width}`);
      const axe = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
      assert.equal(axe.violations.length, 0, JSON.stringify(axe.violations.map((value) => ({ id: value.id, impact: value.impact }))));
      await page.screenshot({ path: path.join(evidenceDir, `${flow}-${width}.png`), fullPage: true });
      results.push({ width, flow, mutations, axeViolations: 0 }); await context.close();
    }
  }
  console.log(JSON.stringify({ evidenceKind: "COMPILED_UI_CONTRACT_FIXTURES_NOT_CORE_QUALIFICATION", checks: results.length, evidenceDir, results }));
} finally { await browser?.close(); await new Promise((resolve) => server.close(resolve)); }
