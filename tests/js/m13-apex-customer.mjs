// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Separate APEX harness. Original I3 and Forge reproducers remain unchanged.
import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign } from "node:crypto";
import { chromium } from "playwright";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const config = JSON.parse(input);
const origin = new URL(config.origin);
assert.equal(origin.hostname, "localhost");
assert.equal(origin.protocol, "http:");
assert.equal(new URL(config.receiptUrl).hostname, "localhost");
const names = ["signup", "email_verification", "password_login", "organization_onboarding", "passkey_enrollment", "passkey_assertion_verification", "secure_elevated_session", "explicit_customer_consent", "root_initiation", "root_proof_of_possession", "root_activation", "application_registration", "agent_registration", "capability_delegation", "policy_assignment", "human_approval", "judgment", "execution_grant", "controlled_execution", "evidence_verification", "revocation", "post_revocation_denial", "incident_recovery_visibility", "logout_session_invalidation"];
const stages = new Map(names.map(phase => [phase, { phase, status: "NOT_EXECUTED" }]));
const requests = [];
let browser, context, page, current = "signup", stop;
const sha = value => createHash("sha256").update(value).digest("hex");
function mark(phase, status, extra = {}) { stages.set(phase, { phase, status, ...extra }); }
async function call(path, method = "GET", body) {
  const result = await page.evaluate(async ({ path, method, body }) => {
    const csrf = document.cookie.split("; ").find(item => item.startsWith("wp_csrf="))?.slice(8);
    const response = await fetch(path, { method, credentials: "same-origin", signal: AbortSignal.timeout(15000), headers: { "Content-Type": "application/json", ...(csrf ? { "X-WP-CSRF": csrf, "X-WhitePact-CSRF": csrf } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    let value = null;
    try { value = await response.json(); } catch { /* Invalid success remains unconfirmed. */ }
    return { status: response.status, value };
  }, { path, method, body });
  requests.push({ phase: current, path, method, http_status: result.status });
  return result;
}
function expect(response, status, invariant = true) {
  if (response.status !== status || !invariant) {
    const code = [response.value?.detail, response.value?.code, response.value?.error, response.value?.error?.code].find(value => typeof value === "string" && /^[A-Z][A-Z_]{2,79}$/.test(value));
    mark(current, response.status === 403 ? "BLOCKED" : "FAIL", { http_status: response.status, expected_status: status, ...(code ? { error_code: code } : {}) });
    stop = current;
    throw new Error("Customer contract boundary");
  }
  return response.value;
}
async function assertion(challenge, credentialId) {
  return page.evaluate(async ({ challenge, credentialId }) => {
    const decode = value => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
    const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    const credential = await navigator.credentials.get({ publicKey: { challenge: decode(challenge.challenge), rpId: challenge.rpId ?? challenge.rp_id, allowCredentials: [{ type: "public-key", id: decode(credentialId) }], userVerification: "required", timeout: 30000 } });
    return { credential_id: credential.id, client_data_json: encode(credential.response.clientDataJSON), authenticator_data: encode(credential.response.authenticatorData), signature: encode(credential.response.signature) };
  }, { challenge, credentialId });
}
try {
  browser = await chromium.launch({ headless: true });
  context = await browser.newContext();
  await context.route("**/*", route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
  page = await context.newPage();
  await page.goto(new URL("/login", origin).href);
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  await cdp.send("WebAuthn.clearCredentials", { authenticatorId });
  let response = await call("/api/v1/web/auth/register", "POST", { ...config.credentials, accepted_terms: true });
  expect(response, 202, !response.value?.verification_url);
  mark(current, "PASS");
  current = "email_verification";
  const mail = await fetch(config.receiptUrl, { headers: { Authorization: `Bearer ${config.receiptSecret}` }, signal: AbortSignal.timeout(10000) });
  assert.equal(mail.status, 200);
  const token = new URL((await mail.json()).verification_url).searchParams.get("token");
  response = await call("/api/v1/web/auth/verify", "POST", { token });
  expect(response, 200, response.value?.status === "verified"); mark(current, "PASS");
  current = "password_login"; expect(await call("/api/v1/web/auth/login", "POST", config.credentials), 200); mark(current, "PASS");
  current = "organization_onboarding";
  expect(await call("/api/v1/web/onboarding", "POST", { organization_name: "Actual APEX Customer", use_case: "Independent local qualification", plan: "FREE" }), 200);
  const session = expect(await call("/api/v1/web/session"), 200);
  assert.equal(session.user.email, config.credentials.email); assert.equal(session.organization.role, "OWNER");
  const org = session.organization.id;
  const authority = `/api/enterprise/organizations/${encodeURIComponent(org)}/authority`;
  const empty = expect(await call(`${authority}/status`), 200);
  assert.equal(empty.root_authority, null); assert.equal(empty.consent_proof, null); mark(current, "PASS");
  current = "passkey_enrollment";
  const challenge = expect(await call("/api/enterprise/passkeys/register/begin", "POST"), 200);
  if (challenge.origin !== origin.origin || challenge.rpId !== origin.hostname) { mark(current, "BLOCKED", { reason: "RP_OR_ORIGIN_CONTRACT_MISMATCH" }); stop = current; throw new Error("Origin boundary"); }
  const registration = await page.evaluate(async ({ challenge, email }) => {
    const decode = value => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
    const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    const credential = await navigator.credentials.create({ publicKey: { challenge: decode(challenge.challenge), rp: { id: challenge.rpId, name: "WhitePact local acceptance" }, user: { id: new TextEncoder().encode(email), name: email, displayName: "Actual APEX Customer" }, pubKeyCredParams: [{ type: "public-key", alg: -7 }], authenticatorSelection: { residentKey: "required", userVerification: "required" }, timeout: 30000, attestation: "none" } });
    return { credential_id: credential.id, client_data_json: encode(credential.response.clientDataJSON), authenticator_data: encode(credential.response.getAuthenticatorData()), transports: credential.response.getTransports(), display_name: "Actual Chromium credential" };
  }, { challenge, email: config.credentials.email });
  const grant = expect(await call("/api/enterprise/security/step-up", "POST", { action: "ADD_PASSKEY" }), 200).grant;
  response = await call("/api/enterprise/passkeys/register/finish", "POST", { ...registration, grant });
  expect(response, 200, response.value?.credential_id === registration.credential_id); mark(current, "PASS");
  const before = await context.cookies();
  current = "passkey_assertion_verification";
  const authChallenge = expect(await call("/api/enterprise/passkeys/authenticate/begin", "POST"), 200);
  assert.equal(authChallenge.origin, origin.origin); assert.equal(authChallenge.rpId, origin.hostname);
  response = await call("/api/enterprise/passkeys/authenticate/finish", "POST", await assertion(authChallenge, registration.credential_id));
  expect(response, 200, response.value?.assurance === "PASSKEY_UV"); mark(current, "PASS");
  current = "secure_elevated_session";
  const after = await context.cookies();
  const oldSession = before.find(cookie => cookie.name === "wp_session")?.value;
  const newSession = after.find(cookie => cookie.name === "wp_session");
  const newCsrf = after.find(cookie => cookie.name === "wp_csrf");
  assert.ok(oldSession); assert.ok(newSession?.value); assert.ok(newCsrf?.value);
  assert.equal(newSession.httpOnly, true); assert.notEqual(newSession.value, oldSession);
  assert.notEqual(newCsrf.value, before.find(cookie => cookie.name === "wp_csrf")?.value);
  const oldResponse = await fetch(new URL("/api/v1/web/session", origin), { headers: { Cookie: `wp_session=${oldSession}` }, signal: AbortSignal.timeout(10000) });
  assert.equal(oldResponse.status, 401);
  const elevated = expect(await call("/api/v1/web/session"), 200);
  assert.equal(elevated.user.email, config.credentials.email); assert.equal(elevated.organization.id, org); mark(current, "PASS", { prior_session_status: oldResponse.status, cookies_rotated: true });
  current = "root_initiation";
  const boot = expect(await call(`${authority}/bootstrap/initiate`, "POST", { require_identity_assurance: true, require_passkey_stepup: true }), 200);
  assert.equal(boot.organization_id, org); assert.equal(boot.require_passkey_stepup, true); mark(current, "PASS");
  current = "root_proof_of_possession";
  const rootKey = generateKeyPairSync("ed25519");
  const publicKey = rootKey.publicKey.export({ format: "der", type: "spki" }).subarray(-32).toString("hex");
  const tokenHash = sha(boot.token);
  const operation = { action: "COMPLETE_ROOT_BOOTSTRAP", org_id: org, nonce: boot.nonce, token_hash: tokenHash, root_public_key: publicKey };
  const digest = sha(JSON.stringify(Object.fromEntries(Object.keys(operation).sort().map(key => [key, operation[key]]))));
  const stepup = expect(await call(`${authority}/webauthn/challenge`, "POST", { action: "COMPLETE_ROOT_BOOTSTRAP", operation_digest: digest }), 200);
  assert.equal(stepup.origin, origin.origin); assert.equal(stepup.rp_id, origin.hostname);
  const proof = sign(null, Buffer.from(`WP_ROOT_POP:${org}:${boot.nonce}:${tokenHash}`), rootKey.privateKey).toString("base64url");
  const consent = { scope_description: "Harmless local APEX read only", purpose: "Independent ephemeral customer qualification", allowed_action_types: ["apex.local.read"], allowed_targets: ["apex:local-read"], consent_method: "API_AUTHENTICATED_REQUEST" };
  response = await call(`${authority}/bootstrap/complete`, "POST", { token: boot.token, nonce: boot.nonce, root_public_key: publicKey, root_signature: proof, webauthn_assertion: await assertion(stepup, registration.credential_id), ...consent });
  const established = expect(response, 200, response.value?.status === "BOOTSTRAPPED" && response.value?.passkey_verified === true && response.value?.proof_of_possession_verified === true);
  mark(current, "PASS"); current = "root_activation";
  const records = expect(await call(`${authority}/status`), 200);
  assert.equal(records.organization_id, org); assert.equal(records.root_authority.root_id, established.root_id); assert.equal(records.consent_proof.consent_id, established.consent_id);
  assert.equal(records.consent_proof.scope_description, consent.scope_description); assert.equal(records.consent_proof.purpose, consent.purpose);
  assert.equal(records.consent_proof.consent_method, consent.consent_method);
  assert.deepEqual(records.consent_proof.allowed_action_types, consent.allowed_action_types); assert.deepEqual(records.consent_proof.allowed_targets, consent.allowed_targets);
  mark(current, "PASS"); mark("explicit_customer_consent", "PASS");
  current = "application_registration"; mark(current, "BLOCKED", { reason: "DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED" }); stop = current;
} catch (error) {
  if (!stop) { stop = current; mark(current, "FAIL", { error_type: error.name }); }
} finally {
  const boundary = stop;
  if (page) {
    try {
      current = "logout_session_invalidation";
      const response = await call("/api/v1/web/auth/logout", "POST");
      expect(response, 200, response.value?.status === "signed_out");
      const invalid = await call("/api/v1/web/session");
      assert.equal(invalid.status, 401); mark(current, "PASS");
    } catch (error) { mark("logout_session_invalidation", "FAIL", { error_type: error.name }); }
  }
  const version = browser?.version();
  await browser?.close();
  stop = boundary ?? stop;
  const phases = [...stages.values()];
  console.log(JSON.stringify({ kind: "ACTUAL_APEX_POSTGRESQL_HTTP_CHROMIUM", acceptance: phases.some(phase => phase.status === "FAIL") ? "FAIL" : "BLOCKED", stop, stages: phases, requests, browser: version, authority_seeded: false, limitations: ["Virtual browser authenticator, not physical hardware certification", "No credential imports or forged signatures", "No later privileged stage run after a failed or blocked boundary"] }));
}
