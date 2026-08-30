import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const urls = [
  "http://127.0.0.1:8765/",
  "http://127.0.0.1:8765/signup",
  "http://127.0.0.1:8765/status",
  "http://127.0.0.1:8765/trust",
  "http://127.0.0.1:8765/leaderboard",
  "http://127.0.0.1:8765/registry",
  "http://127.0.0.1:8765/assess",
  "http://127.0.0.1:8765/incident-db",
  "http://127.0.0.1:8765/incident-db/report",
  "http://127.0.0.1:8765/static/login.html",
  "http://127.0.0.1:8765/static/signup.html",
  "http://127.0.0.1:8765/static/cost.html",
  "http://127.0.0.1:8765/static/eval.html",
  "http://127.0.0.1:8765/static/evaluate.html",
  "http://127.0.0.1:8765/static/guardrails.html",
  "http://127.0.0.1:8765/static/hallucination.html",
  "http://127.0.0.1:8765/static/incidents.html",
  "http://127.0.0.1:8765/static/organizations.html",
  "http://127.0.0.1:8765/static/redteam.html",
  "http://127.0.0.1:8765/static/router.html",
  "http://127.0.0.1:8765/static/settings.html",
  "http://127.0.0.1:8765/static/trust_scores.html",
  "http://127.0.0.1:8765/static/webhooks_manage.html",
  "http://127.0.0.1:8765/static/audit.html",
  "http://127.0.0.1:8765/static/billing.html",
  "http://127.0.0.1:8765/static/auth_complete.html",
  "http://127.0.0.1:8765/static/incident_db.html",
  "http://127.0.0.1:8765/static/incident_db_detail.html",
  "http://127.0.0.1:8765/static/incident_db_report.html",
  "http://127.0.0.1:8765/static/verify.html",
];

const browser = await chromium.launch({ headless: true });
let failures = 0;

try {
  const context = await browser.newContext();
  const page = await context.newPage();

  for (const url of urls) {
    console.log(`Checking ${url}`);

    const response = await page.goto(url, {
      waitUntil: "domcontentloaded",
      timeout: 15000,
    });

    await page.waitForTimeout(500);

    if (!response || !response.ok()) {
      console.error(
        `FAILED: ${url} returned ${response?.status() ?? "no response"}`
      );
      failures += 1;
      continue;
    }

    const results = await new AxeBuilder({ page })
      .withTags(["wcag2a", "wcag2aa"])
      .analyze();

    if (results.violations.length > 0) {
      failures += 1;
      console.error(`ACCESSIBILITY VIOLATIONS: ${url}`);

      for (const violation of results.violations) {
        console.error(
          `  ${violation.id}: ${violation.help} (${violation.impact ?? "unknown impact"})`
        );

        for (const node of violation.nodes) {
          console.error(`    target: ${node.target.join(", ")}`);
          console.error(`    ${node.failureSummary ?? ""}`);
        }
      }
    }
  }

  await context.close();
} finally {
  await browser.close();
}

if (failures > 0) {
  console.error(`Accessibility gate failed on ${failures} page(s).`);
  process.exit(1);
}

console.log(`Accessibility gate passed for all ${urls.length} pages.`);
