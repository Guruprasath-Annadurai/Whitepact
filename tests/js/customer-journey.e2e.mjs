import { chromium } from "playwright";
import crypto from "node:crypto";
import { spawn, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";

const baseUrl = process.env.WHITEPACT_TEST_BASE_URL ?? "http://127.0.0.1:18765";
const managed = !process.env.WHITEPACT_TEST_BASE_URL;
const dbPath = path.join(os.tmpdir(), `whitepact-customer-journey-${Date.now()}.db`);
const databaseUrl = process.env.WHITEPACT_TEST_DATABASE_URL ?? `sqlite:///${dbPath}`;
const password = "Journey-Secure-42!";
const email = `journey-${Date.now()}@example.com`;
const repositoryRoot = process.env.WHITEPACT_TEST_REPOSITORY_ROOT
  ? path.resolve(process.env.WHITEPACT_TEST_REPOSITORY_ROOT)
  : path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const testPython = process.env.WHITEPACT_TEST_PYTHON
  ?? (fs.existsSync(path.join(repositoryRoot, ".venv", "bin", "python"))
    ? path.join(repositoryRoot, ".venv", "bin", "python")
    : "python3");

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
  if (!process.env.WHITEPACT_TEST_DATABASE_URL) fs.closeSync(fs.openSync(dbPath, "w"));
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
    WHITEPACT_AUTH_ENABLED: "true",
    RAI_AUTH_ENABLED: "true",
    RAI_LOG_LEVEL: "WARNING",
    PHASE7A_DISPATCHER_ENABLED: "false",
  };
  if (process.env.WHITEPACT_TEST_DATABASE_URL) env.WHITEPACT_DATABASE_URL = databaseUrl;
  const child = spawn(
    testPython,
    ["-m", "uvicorn", "responsibleai.dashboard.app:app", "--host", "127.0.0.1", "--port", "18765"],
    { cwd: repositoryRoot, env, stdio: "inherit" },
  );
  await waitForReady(baseUrl);
  return child;
}

async function stopServer(child) {
  if (!child) return;
  child.kill("SIGTERM");
  await delay(500);
  if (!process.env.WHITEPACT_TEST_DATABASE_URL) {
    try { fs.unlinkSync(dbPath); } catch { /* ignore */ }
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

  await page.goto(`${baseUrl}/signup`, { waitUntil: "networkidle" });
  await page.getByRole("heading", { name: /create your/i }).waitFor();
  await page.getByLabel(/full name/i).fill("Journey Customer");
  await page.getByLabel(/work email/i).fill(email);
  await page.locator("input[autocomplete='new-password']").fill(password);
  await page.locator("label.checkbox input[type='checkbox']").check();
  const registerWait = page.waitForResponse((response) => response.url().includes("/api/v1/web/auth/register"));
  await page.getByRole("button", { name: /create account/i }).click();
  const registerResponse = await registerWait;
  const registerBody = await registerResponse.json().catch(() => ({}));
  console.log("register", registerResponse.status(), registerBody, "url", page.url());
  if (registerBody.verification_url) {
    const target = String(registerBody.verification_url).replace(/https?:\/\/[^/]+/, baseUrl);
    await page.goto(target, { waitUntil: "domcontentloaded" });
  } else {
    await page.waitForURL(/verify-email/, { timeout: 15000 });
  }
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
  await page.locator("label.checkbox", { hasText: "governance:write" }).locator("input").check();
  await page.locator("label.checkbox", { hasText: "evidence:read" }).locator("input").check();
  await page.getByRole("button", { name: /^create key$/i }).click();
  await page.getByText(/this is the only time the full secret is displayed/i).waitFor({ timeout: 10000 });
  const revealed = (await page.locator(".key-reveal code").innerText()).trim();
  check(revealed.startsWith("wp_") && revealed.length > 20, "raw API key shown once");
  await page.getByRole("button", { name: /^done$/i }).click();

  const keys = await context.request.get(`${baseUrl}/api/v1/web/api-keys`);
  const keyBody = await keys.json();
  check(Array.isArray(keyBody.keys) && keyBody.keys.length === 1, "backend lists created key");
  check(!("api_key" in (keyBody.keys[0] ?? {})), "raw secret is not listed later");

  const seed = spawnSync(
    testPython,
    ["tests/js/seed_journey_authority.py", "--database-url", databaseUrl, "--api-key", revealed],
    { cwd: repositoryRoot, encoding: "utf8" },
  );
  check(seed.status === 0, `authority seed exit ${seed.status} ${seed.stderr || seed.stdout}`);

  const csrf = (await context.cookies()).find((cookie) => cookie.name === "wp_csrf")?.value;
  const adminEmail = `admin-${Date.now()}@example.com`;
  const invite = await context.request.post(`${baseUrl}/api/v1/web/invitations`, {
    headers: { "X-WP-CSRF": csrf, "Content-Type": "application/json" },
    data: JSON.stringify({ email: adminEmail, role: "ADMIN" }),
  });
  const inviteBody = await invite.json();
  check(invite.ok(), `invite ${invite.status()}`);
  const inviteToken = new URL(String(inviteBody.invitation_url).replace(/https?:\/\/[^/]+/, baseUrl)).searchParams.get("token");
  const adminContext = await browser.newContext();
  const adminRegister = await adminContext.request.post(`${baseUrl}/api/v1/web/auth/register`, {
    data: { full_name: "Journey Admin", email: adminEmail, password, accepted_terms: true },
  });
  const adminRegisterBody = await adminRegister.json();
  const adminVerifyUrl = String(adminRegisterBody.verification_url || "").replace(/https?:\/\/[^/]+/, baseUrl);
  const adminVerifyToken = new URL(adminVerifyUrl).searchParams.get("token");
  await adminContext.request.post(`${baseUrl}/api/v1/web/auth/verify`, { data: { token: adminVerifyToken } });
  await adminContext.request.post(`${baseUrl}/api/v1/web/auth/login`, { data: { email: adminEmail, password } });
  const adminCsrf = (await adminContext.cookies()).find((cookie) => cookie.name === "wp_csrf")?.value;
  const accepted = await adminContext.request.post(`${baseUrl}/api/v1/web/invitations/accept`, {
    headers: { "X-WP-CSRF": adminCsrf, "Content-Type": "application/json" },
    data: JSON.stringify({ token: inviteToken }),
  });
  check(accepted.ok(), `accept invitation ${accepted.status()} ${await accepted.text()}`);
  const adminPage = await adminContext.newPage();

  const callTool = async (failAfter = false) => context.request.post(`${baseUrl}/api/v1/governance/tools/call`, {
    headers: { Authorization: `Bearer ${revealed}` },
    data: { name: "test.counter.increment", arguments: { fail_after_effect: failAfter }, purpose: "automated-test" },
  });
  const pending = await callTool();
  const pendingBody = await pending.json();
  check(pendingBody.error === "governance_approval_required", `approval required ${JSON.stringify(pendingBody)}`);
  const before = await context.request.get(`${baseUrl}/api/v1/governance/test-counter`, {
    headers: { Authorization: `Bearer ${revealed}` },
  });
  const beforeBody = await before.json();
  check(beforeBody.counter === 0 && beforeBody.downstream_call_count === 0, `before approval ${JSON.stringify(beforeBody)}`);

  await page.goto(`${baseUrl}/dashboard/approvals`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Approve" }).click();
  await page.getByRole("button", { name: /confirm approve/i }).click();
  await page.getByText("PENDING").first().waitFor({ timeout: 10000 }).catch(() => {});
  await adminPage.goto(`${baseUrl}/dashboard/approvals`, { waitUntil: "domcontentloaded" });
  await adminPage.getByRole("button", { name: "Approve" }).click();
  await adminPage.getByRole("button", { name: /confirm approve/i }).click();
  let afterBody = { counter: -1, downstream_call_count: -1 };
  for (let i = 0; i < 20; i += 1) {
    const afterApprove = await context.request.get(`${baseUrl}/api/v1/governance/test-counter`, {
      headers: { Authorization: `Bearer ${revealed}` },
    });
    afterBody = await afterApprove.json();
    if (afterBody.counter === 1 && afterBody.downstream_call_count === 1) break;
    await delay(250);
  }
  check(afterBody.counter === 1 && afterBody.downstream_call_count === 1, `after approve ${JSON.stringify(afterBody)}`);

  const denyPending = await callTool();
  const denyBody = await denyPending.json();
  check(denyBody.error === "governance_approval_required", "second mutation requires approval");
  await page.goto(`${baseUrl}/dashboard/approvals`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: "Deny" }).click();
  await page.getByRole("button", { name: /confirm denied/i }).click();
  await page.getByText(/no requests are waiting/i).waitFor({ timeout: 10000 }).catch(() => {});
  const afterDeny = await context.request.get(`${baseUrl}/api/v1/governance/test-counter`, {
    headers: { Authorization: `Bearer ${revealed}` },
  });
  const denyState = await afterDeny.json();
  check(denyState.counter === 1 && denyState.downstream_call_count === 1, `after deny ${JSON.stringify(denyState)}`);

  await page.goto(`${baseUrl}/dashboard/evidence`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Evidence", exact: true }).waitFor();
  const evidenceApi = await context.request.get(`${baseUrl}/api/v1/web/dashboard/evidence`);
  const evidenceJson = await evidenceApi.json();
  check(Array.isArray(evidenceJson.items) && evidenceJson.items.length > 0, "evidence backend has records");

  await page.goto(`${baseUrl}/dashboard/members`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /invite a member/i }).waitFor();
  await page.goto(`${baseUrl}/accept-invitation?token=invalid`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: /accept invitation/i }).waitFor();

  await page.goto(`${baseUrl}/dashboard/security`, { waitUntil: "domcontentloaded" });
  const securityApi = await context.request.get(`${baseUrl}/api/v1/web/dashboard/security`);
  const securityJson = await securityApi.json();
  check(securityJson.source === "identity_security_stores", `security source ${securityJson.source}`);
  check(securityJson.items?.some((item) => item.title === "Assurance level"), "assurance comes from backend");
  await page.getByText(/PASSWORD|UNAVAILABLE|NOT CONFIGURED|IDENTITY_VERIFIED|BASIC_VERIFIED/i).first().waitFor();

  await page.goto(`${baseUrl}/dashboard`, { waitUntil: "domcontentloaded" });
  await page.getByText(/governance decisions/i).waitFor();
  await page.goto(`${baseUrl}/dashboard/approvals`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Approvals", exact: true }).waitFor();
  await page.goto(`${baseUrl}/dashboard/evidence`, { waitUntil: "domcontentloaded" });
  await page.getByRole("heading", { name: "Evidence", exact: true }).waitFor();
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
  await page.locator("input").first().waitFor();
  const orgName = await page.locator("input").first().inputValue();
  check(orgName === "Journey Org", "organization page shows persisted name");

  await page.goto(`${baseUrl}/dashboard/api-keys`, { waitUntil: "domcontentloaded" });
  await page.getByRole("button", { name: /revoke/i }).click();
  await page.getByRole("button", { name: /confirm revoke/i }).click();
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
