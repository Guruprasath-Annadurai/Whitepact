import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const baseUrl = process.env.WHITEPACT_TEST_BASE_URL ?? "http://127.0.0.1:8765";
const urls = [
  "/", "/login", "/signup", "/verify-email", "/forgot-password", "/reset-password",
  "/onboarding", "/terms", "/privacy", "/docs", "/contact", "/status", "/trust",
  "/leaderboard", "/registry", "/assess", "/incident-db", "/incident-db/report",
  "/static/login.html", "/static/signup.html", "/static/cost.html", "/static/eval.html",
  "/static/evaluate.html", "/static/guardrails.html", "/static/hallucination.html",
  "/static/incidents.html", "/static/organizations.html", "/static/redteam.html",
  "/static/router.html", "/static/settings.html", "/static/trust_scores.html",
  "/static/webhooks_manage.html", "/static/audit.html", "/static/billing.html",
  "/static/auth_complete.html", "/static/incident_db.html", "/static/incident_db_detail.html",
  "/static/incident_db_report.html", "/static/verify.html",
].map((path) => `${baseUrl}${path}`);

const browser = await chromium.launch({ headless: true });
let failures = 0;

async function scan(page, url) {
  console.log(`Checking ${url}`);
  const response = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 15000 });
  if (!response || !response.ok()) {
    console.error(`FAILED: ${url} returned ${response?.status() ?? "no response"}`);
    failures += 1;
    return;
  }
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa"])
    .analyze();
  const blocking = results.violations.filter((item) => ["critical", "serious"].includes(item.impact));
  if (blocking.length > 0) {
    failures += 1;
    console.error(`ACCESSIBILITY VIOLATIONS: ${url}`);
    for (const violation of blocking) {
      console.error(`  ${violation.id}: ${violation.help} (${violation.impact})`);
      for (const node of violation.nodes) {
        console.error(`    target: ${node.target.join(", ")}`);
        console.error(`    ${node.failureSummary ?? ""}`);
      }
    }
  }
}

try {
  const context = await browser.newContext();
  const page = await context.newPage();

  for (const url of urls) {
    await scan(page, url);
  }

  const email = `accessibility-${Date.now()}@whitepact.dev`;
  const password = "Accessible-Console-42!";
  const registration = await context.request.post(`${baseUrl}/api/v1/web/auth/register`, {
    data: { full_name: "Accessibility Auditor", email, password, accepted_terms: true },
  });
  const registrationBody = await registration.json();
  if (!registration.ok() || !registrationBody.verification_url) {
    console.error("FAILED: authenticated accessibility setup requires WHITEPACT_WEB_AUTH_DEV_TOKENS=true");
    failures += 1;
  } else {
    const verificationToken = new URL(registrationBody.verification_url).searchParams.get("token");
    await context.request.post(`${baseUrl}/api/v1/web/auth/verify`, { data: { token: verificationToken } });
    const login = await context.request.post(`${baseUrl}/api/v1/web/auth/login`, { data: { email, password } });
    const csrfCookie = (await context.cookies()).find((cookie) => cookie.name === "wp_csrf");
    const onboarding = await context.request.post(`${baseUrl}/api/v1/web/onboarding`, {
      headers: { "X-WP-CSRF": csrfCookie?.value ?? "" },
      data: { organization_name: "Accessibility Workspace", use_case: "Enterprise evaluation", plan: "FREE" },
    });
    if (!login.ok() || !onboarding.ok()) {
      console.error(`FAILED: authenticated accessibility setup returned login=${login.status()} onboarding=${onboarding.status()}`);
      failures += 1;
    } else {
      for (const path of ["/dashboard", "/dashboard/api-keys", "/dashboard/billing", "/dashboard/organization", "/dashboard/approvals", "/dashboard/evidence", "/dashboard/security"]) {
        await scan(page, `${baseUrl}${path}`);
      }
      const mobile = await context.newPage();
      await mobile.setViewportSize({ width: 390, height: 844 });
      for (const path of ["/", "/signup", "/dashboard", "/dashboard/api-keys", "/dashboard/billing"]) {
        const url = `${baseUrl}${path}`;
        await mobile.goto(url, { waitUntil: "domcontentloaded", timeout: 15000 });
        const overflow = await mobile.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
        if (overflow > 1) {
          console.error(`RESPONSIVE OVERFLOW: ${url} exceeds viewport by ${overflow}px`);
          failures += 1;
        }
      }
      await mobile.close();
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
