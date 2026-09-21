import { chromium } from "playwright";
import crypto from "node:crypto";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { setTimeout as delay } from "node:timers/promises";

const baseUrl = process.env.WHITEPACT_TEST_BASE_URL ?? "http://127.0.0.1:18765";
const managed = !process.env.WHITEPACT_TEST_BASE_URL;
const dbPath = `/tmp/whitepact-customer-journey-${Date.now()}.db`;
const password = "Journey-Secure-42!";
const email = `journey-${Date.now()}@whitepact.test`;

function hmacIdentity(payload, timestamp) {
  const secret = process.env.WHITEPACT_IDENTITY_WEBHOOK_SECRET || "dev-identity-webhook-secret";
  return crypto.createHmac("sha256", secret).update(payload + timestamp).digest("hex");
}

async function waitForReady(url, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const response = await fetch(`${url}/ready`);
      if (response.ok) return;
    } catch {
      // server not up yet
    }
    await delay(250);
  }
  throw new Error(`WhitePact did not become ready at ${url}`);
}

async function startServer() {
  if (!managed) return null;
  const env = {
    ...process.env,
    RAI_AUTH_ENABLED: "false",
    WHITEPACT_AUTH_ENABLED: "false",
    RAI_DB_PATH: dbPath,
    WHITEPACT_DB_PATH: dbPath,
    RAI_AUTO_MIGRATE: "true",
    WHITEPACT_WEB_AUTH_DEV_TOKENS: "true",
    RAI_WEB_AUTH_DEV_TOKENS: "true",
    WHITEPACT_WEB_PUBLIC_URL: baseUrl,
    RAI_WEB_PUBLIC_URL: baseUrl,
    WHITEPACT_WEB_SESSION_SECURE: "false",
    RAI_WEB_SESSION_SECURE: "false",
    WHITEPACT_ENV: "development",
    RAI_LOG_LEVEL: "WARNING",
    PHASE7A_DISPATCHER_ENABLED: "false",
  };
  const child = spawn(
    path.join("/workspace", ".venv", "bin", "python"),
    ["-m", "uvicorn", "responsibleai.dashboard.app:app", "--host", "127.0.0.1", "--port", "18765"],
    { cwd: "/workspace", env, stdio: "inherit" },
  );
  await waitForReady(baseUrl);
  return child;
}

async function stopServer(child) {
  if (!child) return;
  child.kill("SIGTERM");
  await delay(500);
  try {
    fs.unlinkSync(dbPath);
  } catch {
    // ignore
  }
}

const failures = [];
function check(condition, message) {
  if (!condition) {
    failures.push(message);
    console.error(`FAIL: ${message}`);
  } else {
    console.log(`ok: ${message}`);
  }
}

const publicPaths = [
  "/", "/about", "/contact", "/docs", "/trust", "/terms", "/privacy", "/pricing", "/refund-policy",
  "/login", "/signup", "/verify-email", "/forgot-password", "/reset-password",
];

const child = await startServer();
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  const page = await context.newPage();

  for (const item of publicPaths) {
    const response = await page.goto(`${baseUrl}${item}`, { waitUntil: "domcontentloaded", timeout: 20000 });
    check(response && response.ok(), `${item} returned ${response?.status()}`);
  }

  await page.goto(`${baseUrl}/signup`, { waitUntil: "domcontentloaded" });
  await page.getByLabel(/full name/i).fill("Journey Customer");
  await page.getByLabel(/work email/i).fill(email);
  await page.locator("input[autocomplete='new-password']").fill(password);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /create account/i }).click();
  await page.waitForURL(/verify-email/, { timeout: 15000 });
  await page.getByRole("button", { name: /verify email/i }).click();
  await page.getByRole("button", { name: /continue to sign in/i }).click();

  await page.getByLabel(/^email$/i).fill(email);
  await page.locator("input[autocomplete='current-password']").fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await page.waitForURL(/onboarding/, { timeout: 15000 });

  await page.getByLabel(/organization name/i).fill("Journey Org");
  await page.locator("select").selectOption({ label: "Engineering" });
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /continue/i }).click();
  await page.getByRole("button", { name: /create workspace/i }).click();
  await page.waitForURL(/dashboard/, { timeout: 15000 });

  const session = await context.request.get(`${baseUrl}/api/v1/web/session`);
  check(session.ok(), `session API ${session.status()}`);
  const sessionBody = await session.json();
  check(sessionBody.organization?.name === "Journey Org", "onboarding persisted organization");
  check(sessionBody.user?.email === email, "session email matches signup");

  await page.goto(`${baseUrl}/dashboard/api-keys`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /create api key/i }).first().click();
  await page.getByLabel(/^name$/i).fill("browser-agent");
  await page.getByRole("button", { name: /^create key$/i }).click();
  await page.waitForTimeout(500);
  const deniedVisible = await page.locator(".form-error, [role='alert']").count();
  check(deniedVisible > 0, "API key create denied before IDENTITY_VERIFIED");

  const timestamp = new Date().toISOString();
  const payload = JSON.stringify({
    event_id: `evt-e2e-${Date.now()}`,
    subject_id: sessionBody.user.id,
    outcome: "VERIFIED",
  });
  const webhook = await context.request.post(`${baseUrl}/api/enterprise/identity/verification/webhook`, {
    headers: {
      "Content-Type": "application/json",
      "X-Identity-Signature": hmacIdentity(payload, timestamp),
      "X-Identity-Timestamp": timestamp,
    },
    data: payload,
  });
  check(webhook.ok(), `identity webhook ${webhook.status()}`);

  await page.reload({ waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /create api key/i }).first().click();
  await page.getByLabel(/^name$/i).fill("browser-agent");
  await page.getByRole("button", { name: /^create key$/i }).click();
  await page.getByText(/this is the only time the full secret is displayed/i).waitFor({ timeout: 10000 });
  const revealed = await page.locator("code").first().innerText();
  check(revealed.startsWith("wp_"), "raw API key shown once");
  await page.getByRole("button", { name: /^done$/i }).click();

  const keys = await context.request.get(`${baseUrl}/api/v1/web/api-keys`);
  const keyBody = await keys.json();
  check(Array.isArray(keyBody.keys) && keyBody.keys.length === 1, "backend lists created key");
  check(!JSON.stringify(keyBody).includes(revealed), "raw secret is not listed later");

  await page.goto(`${baseUrl}/dashboard`, { waitUntil: "domcontentloaded" });
  await page.getByText(/governance decisions/i).waitFor();
  await page.goto(`${baseUrl}/dashboard/approvals`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /approvals/i }).waitFor();
  await page.goto(`${baseUrl}/dashboard/evidence`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /evidence/i }).waitFor();
  await page.goto(`${baseUrl}/dashboard/members`, { waitUntil: "domcontentloaded" });
  await page.getByText(/owner\.|Journey Customer|owner/i).waitFor({ timeout: 10000 }).catch(() => {});
  const membersApi = await context.request.get(`${baseUrl}/api/v1/web/dashboard/members`);
  const members = await membersApi.json();
  check(members.items?.some((item) => item.email === email), "members API matches signed-in owner");
  await page.goto(`${baseUrl}/dashboard/billing`, { waitUntil: "domcontentloaded" });
  await page.getByText(/not configured|current plan|free/i).first().waitFor();
  await page.goto(`${baseUrl}/dashboard/security`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /security/i }).waitFor();
  await page.goto(`${baseUrl}/dashboard/organization`, { waitUntil: "domcontentloaded" });
  await page.getByDisplayValue("Journey Org").waitFor();

  page.once("dialog", (dialog) => dialog.accept());
  await page.goto(`${baseUrl}/dashboard/api-keys`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /revoke/i }).click();
  await page.getByText(/no api keys/i).waitFor({ timeout: 10000 });
  const keysAfter = await context.request.get(`${baseUrl}/api/v1/web/api-keys`);
  check((await keysAfter.json()).keys.length === 0, "revoked key absent from backend");

  await page.getByRole("button", { name: /sign out/i }).click();
  await page.waitForURL(/\/$|login/, { timeout: 15000 });
  const afterLogout = await context.request.get(`${baseUrl}/api/v1/web/session`);
  check(!afterLogout.ok(), `post-logout session is ${afterLogout.status()}`);
} catch (error) {
  failures.push(String(error));
  console.error(error);
} finally {
  await browser.close();
  await stopServer(child);
}

if (failures.length) {
  console.error(`customer journey e2e failed (${failures.length})`);
  process.exit(1);
}
console.log("customer journey e2e passed");
