// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Actual HTTP/browser ceremonies. No response fixtures, rewrites or credential imports.
import assert from "node:assert/strict";
import { chromium } from "playwright";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const config = JSON.parse(input);
const origin = new URL(config.origin);
assert.equal(origin.hostname, "localhost");
assert.equal(origin.protocol, "http:");
const receiptOrigin = new URL(config.receiptUrl);
assert.equal(receiptOrigin.hostname, "localhost");
assert.equal(receiptOrigin.protocol, "http:");
const phases = [];
let browser;
let page;
let stop = "UNEXPECTED_HARNESS_FAILURE";
const unexecuted = ["consent", "root_authority", "application", "agent", "delegation", "policy", "approval", "controlled_execution", "execution_evidence", "authority_revocation", "post_revocation_denial"];
async function call(phase, path, method = "GET", body, csrfName = "X-WP-CSRF") {
  const result = await page.evaluate(async ({ path, method, body, csrfName }) => {
    const csrf = document.cookie.split("; ").find((item) => item.startsWith("wp_csrf="))?.slice(8);
    const response = await fetch(path, { method, credentials: "same-origin", headers: { "Content-Type": "application/json", ...(csrf ? { [csrfName]: csrf } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    let value;
    try { value = await response.json(); } catch { value = null; }
    return { status: response.status, value };
  }, { path, method, body, csrfName });
  phases.push({ phase, path, method, http_status: result.status, result: "OBSERVED" });
  return result;
}
function confirm(response, expected, invariant = true) {
  if (response.status !== expected || invariant !== true) {
    phases.at(-1).result = "BLOCKED";
    const code = response.value?.code ?? (typeof response.value?.error === "string" ? response.value.error : response.value?.error?.code);
    if (new Set(["AUTHENTICATION_ASSURANCE_TOO_LOW", "STEP_UP_REQUIRED", "FORBIDDEN", "UNAUTHENTICATED", "WEBAUTHN_INVALID", "CHALLENGE_REPLAY"]).has(code)) phases.at(-1).code = code;
    stop = phases.at(-1).code ?? "HTTP_OR_SEMANTIC_CONTRACT_NOT_CONFIRMED";
    throw new Error("Journey boundary");
  }
  phases.at(-1).result = "CONFIRMED";
}
try {
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  await context.route("**/*", (route) => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
  page = await context.newPage();
  await page.goto(new URL("/login", origin).href);
  assert.equal(await page.evaluate(() => location.origin), origin.origin);
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  assert.equal((await cdp.send("WebAuthn.getCredentials", { authenticatorId })).credentials.length, 0);
  let credentialCount = 0;
  cdp.on("WebAuthn.credentialAdded", () => { credentialCount++; });
  phases.push({ phase: "empty_chromium_virtual_authenticator", result: "CONFIRMED", imported_credentials: 0 });
  let response = await call("signup", "/api/v1/web/auth/register", "POST", { ...config.credentials, accepted_terms: true });
  confirm(response, 202, response.value?.status === "verification_required" && !response.value?.verification_url);
  const receiptResponse = await fetch(config.receiptUrl, { headers: { Authorization: `Bearer ${config.receiptSecret}` }, signal: AbortSignal.timeout(10000) });
  assert.equal(receiptResponse.status, 200);
  const receipt = await receiptResponse.json();
  const token = new URL(receipt.verification_url).searchParams.get("token");
  assert(token);
  response = await call("genuine_mail_verification", "/api/v1/web/auth/verify", "POST", { token });
  confirm(response, 200, response.value?.status === "verified");
  response = await call("password_login", "/api/v1/web/auth/login", "POST", config.credentials);
  confirm(response, 200);
  response = await call("organization_onboarding", "/api/v1/web/onboarding", "POST", { organization_name: "Actual I3 Browser Customer", use_case: "Independent local browser qualification", plan: "FREE" });
  confirm(response, 200, response.value?.next === "/dashboard");
  response = await call("authenticated_owner_session", "/api/v1/web/session");
  confirm(response, 200, response.value?.organization?.role === "OWNER" && response.value?.user?.email === config.credentials.email);
  const organizationId = response.value.organization.id;
  response = await call("recorded_authority_snapshot", `/api/enterprise/organizations/${encodeURIComponent(organizationId)}/authority/status`);
  confirm(response, 200, response.value?.organization_id === organizationId && response.value?.root_authority === null && response.value?.consent_proof === null);
  response = await call("registration_challenge", "/api/enterprise/passkeys/register/begin", "POST", undefined, "X-WhitePact-CSRF");
  confirm(response, 200, typeof response.value?.challenge === "string");
  const challenge = response.value;
  if (challenge.origin !== origin.origin || challenge.rpId !== origin.hostname) {
    stop = "RP_OR_ORIGIN_CONTRACT_MISMATCH";
    phases.push({ phase: "browser_origin_binding", result: "BLOCKED", browser_origin: origin.origin, expected_origin: challenge.origin, rp_id: challenge.rpId });
    throw new Error("Journey boundary");
  }
  phases.push({ phase: "browser_origin_binding", result: "CONFIRMED", browser_origin: origin.origin, rp_id: challenge.rpId });
  const registration = await page.evaluate(async ({ challenge, email }) => {
    const decode = (value) => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
    const encode = (value) => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    const credential = await navigator.credentials.create({ publicKey: { challenge: decode(challenge.challenge), rp: { id: challenge.rpId, name: "WhitePact local acceptance" }, user: { id: new TextEncoder().encode(email), name: email, displayName: "Actual I3 Customer" }, pubKeyCredParams: [{ type: "public-key", alg: -7 }], authenticatorSelection: { residentKey: "required", userVerification: "required" }, timeout: 30000, attestation: "none" } });
    const response = credential.response;
    return { client_data_json: encode(response.clientDataJSON), authenticator_data: encode(response.getAuthenticatorData()), credential_id: credential.id, display_name: "Chromium CDP local acceptance", transports: response.getTransports() };
  }, { challenge, email: config.credentials.email });
  const count = credentialCount;
  assert.equal(count, 1);
  phases.push({ phase: "browser_generated_registration", result: "CONFIRMED", credential_count: count, response_source: "navigator.credentials.create", private_key_exported: false });
  response = await call("request_registration_step_up", "/api/enterprise/security/step-up", "POST", { action: "ADD_PASSKEY" }, "X-WhitePact-CSRF");
  confirm(response, 200, typeof response.value?.grant === "string");
  response = await call("server_registration_verification", "/api/enterprise/passkeys/register/finish", "POST", { ...registration, grant: response.value.grant }, "X-WhitePact-CSRF");
  confirm(response, 200, response.value?.code === "OK" && response.value?.credential_id === registration.credential_id);
  response = await call("authentication_challenge", "/api/enterprise/passkeys/authenticate/begin", "POST", undefined, "X-WhitePact-CSRF");
  confirm(response, 200, response.value?.origin === origin.origin && response.value?.rpId === origin.hostname);
  const assertion = await page.evaluate(async ({ challenge, credentialId }) => {
    const decode = (value) => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), (c) => c.charCodeAt(0));
    const encode = (value) => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    const credential = await navigator.credentials.get({ publicKey: { challenge: decode(challenge.challenge), rpId: challenge.rpId, allowCredentials: [{ type: "public-key", id: decode(credentialId) }], userVerification: "required", timeout: 30000 } });
    return { client_data_json: encode(credential.response.clientDataJSON), authenticator_data: encode(credential.response.authenticatorData), signature: encode(credential.response.signature), credential_id: credential.id };
  }, { challenge: response.value, credentialId: registration.credential_id });
  phases.push({ phase: "browser_generated_assertion", result: "CONFIRMED", response_source: "navigator.credentials.get", signature_forged: false });
  response = await call("server_assertion_verification", "/api/enterprise/passkeys/authenticate/finish", "POST", assertion, "X-WhitePact-CSRF");
  confirm(response, 200, response.value?.status === "AUTHENTICATED" && response.value?.assurance === "PASSKEY_UV");
  stop = "DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED";
} catch (error) {
  if (stop === "UNEXPECTED_HARNESS_FAILURE") phases.push({ phase: "harness_stop", result: "BLOCKED", error_type: error.name });
} finally {
  const boundary = stop;
  if (page) {
    if (phases.some((phase) => phase.phase === "authenticated_owner_session" && phase.result === "CONFIRMED")) {
      try {
        const response = await call("persisted_passkey_inventory", "/api/enterprise/passkeys");
        confirm(response, 200, Array.isArray(response.value?.passkeys));
        phases.at(-1).returned_passkeys = response.value.passkeys.length;
      } catch { /* Record read failure without replacing the ceremony boundary. */ }
    }
    try { const response = await call("session_cleanup_logout", "/api/v1/web/auth/logout", "POST"); confirm(response, 200, response.value?.status === "signed_out"); } catch { /* Prior failure remains recorded. */ }
  }
  stop = boundary;
  const version = browser?.version();
  await browser?.close();
  const remainingCeremony = ["browser_generated_registration", "server_registration_verification", "authentication_challenge", "browser_generated_assertion", "server_assertion_verification"].filter((phase) => !phases.some((item) => item.phase === phase));
  console.log(JSON.stringify({ kind: "ACTUAL_POSTGRESQL_HTTP_CHROMIUM_WEBAUTHN_EMULATOR", acceptance: "BLOCKED", production: "GLOBAL PRODUCTION NO-GO", stop, browser: version, phases, not_executed: [...remainingCeremony, ...unexecuted], limitations: ["CDP authenticator is an emulator, not hardware authenticator qualification", "No credentials imported, signature checks disabled or customer authority seeded", "Browser HTTP account setup is not a full visual form usability test", "Privileged chain stops at the first unqualified contract"] }));
}
