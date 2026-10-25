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
const names = config.phases;
assert.equal(names.length, 25);
const stages = new Map(names.map(phase => [phase, { phase, status: "NOT_EXECUTED" }]));
const requests = [];
let browser, context, page, current = "signup", stop, issuedKeyId;
const sha = value => createHash("sha256").update(value).digest("hex");
function mark(phase, status, extra = {}) { stages.set(phase, { phase, status, ...extra }); }
async function call(path, method = "GET", body, apiKey) {
  const result = await page.evaluate(async ({ path, method, body, apiKey }) => {
    const csrf = document.cookie.split("; ").find(item => item.startsWith("wp_csrf="))?.slice(8);
    const response = await fetch(path, { method, credentials: "same-origin", signal: AbortSignal.timeout(path.endsWith("/execute") ? 60000 : 15000), headers: { "Content-Type": "application/json", ...(csrf ? { "X-WP-CSRF": csrf, "X-WhitePact-CSRF": csrf } : {}), ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}) }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
    let value = null;
    try { value = await response.json(); } catch { /* Invalid success remains unconfirmed. */ }
    return { status: response.status, value };
  }, { path, method, body, apiKey });
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
  current = "legitimate_identity_qualification";
  const identity = expect(await call("/api/enterprise/identity/verification"), 200);
  assert.equal(identity.email_verified, true);
  const identityProjection = { reported_status: identity.status, email_verified: identity.email_verified, provider_present: Boolean(identity.provider), assurance_present: Boolean(identity.assurance_level) };
  current = "root_initiation";
  const initiated = await call(`${authority}/bootstrap/initiate`, "POST", { require_identity_assurance: true, require_passkey_stepup: true });
  if (initiated.status === 403 && initiated.value?.error === "IDENTITY_ASSURANCE_REQUIRED") mark("legitimate_identity_qualification", "BLOCKED", { ...identityProjection, reason: "PUBLIC_PROJECTION_NOT_ACCEPTED_AS_ROOT_QUALIFICATION" });
  const boot = expect(initiated, 200);
  mark("legitimate_identity_qualification", "PASS", identityProjection);
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
  const consent = { scope_description: "Harmless local APEX policy check", purpose: "Independent ephemeral customer qualification", allowed_action_types: ["rai_policy_check"], allowed_targets: ["rai_policy_check"], consent_method: "API_AUTHENTICATED_REQUEST" };
  response = await call(`${authority}/bootstrap/complete`, "POST", { token: boot.token, nonce: boot.nonce, root_public_key: publicKey, root_signature: proof, webauthn_assertion: await assertion(stepup, registration.credential_id), ...consent });
  const established = expect(response, 200, response.value?.status === "BOOTSTRAPPED" && response.value?.passkey_verified === true && response.value?.proof_of_possession_verified === true);
  mark(current, "PASS"); current = "root_activation";
  const records = expect(await call(`${authority}/status`), 200);
  assert.equal(records.organization_id, org); assert.equal(records.root_authority.root_id, established.root_id); assert.equal(records.consent_proof.consent_id, established.consent_id);
  assert.equal(records.consent_proof.scope_description, consent.scope_description); assert.equal(records.consent_proof.purpose, consent.purpose);
  assert.equal(records.consent_proof.consent_method, consent.consent_method);
  assert.deepEqual(records.consent_proof.allowed_action_types, consent.allowed_action_types); assert.deepEqual(records.consent_proof.allowed_targets, consent.allowed_targets);
  mark(current, "PASS"); mark("explicit_customer_consent", "PASS");
  current = "application_registration";
  const application = expect(await call(`${authority}/applications`, "POST", { name: "Actual local APEX application", description: "Ephemeral customer qualification", environment: "development" }), 200);
  assert.equal(application.organization_id, org); assert.equal(application.owner_user_id, elevated.user.id);
  assert.equal(application.has_execution_authority, false); assert.ok(application.application_id);
  const persistedApplication = expect(await call(`${authority}/applications/${application.application_id}`), 200);
  assert.equal(persistedApplication.application_id, application.application_id);
  mark(current, "PASS", { registration_authority: false });
  current = "agent_registration";
  const agent = expect(await call(`${authority}/agents`, "POST", { name: "Actual local APEX agent", application_id: application.application_id, framework: "custom", purpose: consent.purpose }), 200);
  assert.equal(agent.organization_id, org); assert.equal(agent.application_id, application.application_id);
  assert.equal(agent.has_delegated_authority, false); assert.ok(agent.agent_id);
  mark(current, "PASS", { registration_authority: false });
  current = "capability_delegation";
  const delegation = expect(await call(`${authority}/agents/${agent.agent_id}/delegations`, "POST", { granted_action_types: consent.allowed_action_types, allowed_targets: consent.allowed_targets, purpose: consent.purpose, expires_at: new Date(Date.now() + 120000).toISOString() }), 200);
  assert.equal(delegation.agent_id, agent.agent_id); assert.equal(delegation.organization_id, org);
  assert.deepEqual(delegation.granted_action_types, consent.allowed_action_types);
  assert.deepEqual(delegation.allowed_targets, consent.allowed_targets);
  assert.ok(delegation.delegation_id); assert.ok(delegation.consent_id); mark(current, "PASS");
  current = "policy_assignment";
  const rule = expect(await call("/api/web/policy/rules", "POST", { rule_id: "apex-local-requires-human", reason_code: "APEX_LOCAL_APPROVAL_REQUIRED", effect: "REQUIRE_APPROVAL", action_types: consent.allowed_action_types, targets: consent.allowed_targets }), 200);
  assert.equal(rule.effect, "REQUIRE_APPROVAL"); assert.equal(rule.rule_id, "apex-local-requires-human");
  const policy = expect(await call("/api/web/policy"), 200);
  assert.equal(policy.org_id, org);
  assert.ok(policy.rules.some(persisted => persisted.rule_id === rule.rule_id && persisted.effect === "REQUIRE_APPROVAL"));
  mark(current, "PASS");
  current = "judgment";
  if (config.developmentAgentPrototype) {
    const { runDevelopmentAgent } = await import("./sovereign-agent-customer.mjs");
    await runDevelopmentAgent({ origin, call, expect, mark, setPhase: phase => { current = phase; }, agent, authority, consent, requests });
  } else {
  const credentialAdmission = await call("/api/web/api-keys", "POST", { name: "Ephemeral APEX intent qualification", environment: "test", scopes: ["governance:read", "governance:write"], expires_at: new Date(Date.now() + 120000).toISOString() });
  if ([401, 403].includes(credentialAdmission.status)) {
    const credentialError = credentialAdmission.value?.detail?.error ?? credentialAdmission.value?.detail?.code ?? credentialAdmission.value?.error;
    mark(current, "BLOCKED", { reason: "QUALIFIED_IDENTITY_REQUIRED_FOR_CANONICAL_API_CREDENTIAL", http_status: credentialAdmission.status, ...(typeof credentialError === "string" && /^[A-Z][A-Z_]{2,79}$/.test(credentialError) ? { error_code: credentialError } : {}) });
  } else {
    const credential = expect(credentialAdmission, 201);
    assert.ok(credential.api_key); issuedKeyId = credential.id ?? credential.key_id;
    assert.ok(issuedKeyId);
    const intent = { name: "rai_policy_check", arguments: { text: "Harmless local customer evaluation", policy: { blocked_topics: ["prohibited-content"] } }, purpose: consent.purpose };
    const intentAdmission = await call("/api/governance/intent-contracts", "POST", { agent_id: agent.agent_id, goal: consent.purpose, max_value_usd: 0, allowed_targets: consent.allowed_targets, allowed_action_types: consent.allowed_action_types, expires_in_minutes: 2 }, credential.api_key);
    if ([401, 403].includes(intentAdmission.status)) mark(current, "BLOCKED", { reason: "AGENT_BOUND_INTENT_ADMISSION_NOT_QUALIFIED", http_status: intentAdmission.status });
    else {
      const declared = expect(intentAdmission, 201);
      assert.equal(declared.agent_id, agent.agent_id);
      const judgment = await call("/api/governance/tools/call", "POST", { name: intent.name, arguments: intent.arguments, purpose: intent.purpose, agent_id: agent.agent_id }, credential.api_key);
      const approvalId = judgment.value?.approval_id;
      if (judgment.status !== 200 || judgment.value?.error !== "governance_approval_required" || !approvalId) {
        mark(current, "FAIL", { http_status: judgment.status, error: judgment.value?.error ?? "AGENT_BOUND_JUDGMENT_NOT_RECORDED" });
        throw new Error("Customer contract boundary");
      }
      mark(current, "PASS", { approval_id: approvalId, authentication: "api_key", agent_id: agent.agent_id, intent_contract_id: declared.contract_id });
      current = "human_approval";
      const approval = expect(await call(`/api/web/approvals/${approvalId}`), 200);
      assert.equal(approval.requester, agent.agent_id);
      assert.equal(approval.organization_id, agent.organization_id);
      assert.ok(approval.action_digest);
      const resolved = expect(await call(`/api/web/approvals/${approvalId}/resolve`, "POST", { outcome: "APPROVED", notes: "Explicit human approval of harmless local tool" }), 200);
      assert.equal(resolved.status, "APPROVED");
      mark(current, "PASS", { approval_id: approvalId, action_digest: approval.action_digest });
      current = "execution_grant";
      const executed = expect(await call(`/api/web/approvals/${approvalId}/execute`, "POST"), 200);
      assert.equal(executed.execution_status, "SUCCEEDED");
      assert.equal(executed.reconciliation_required, false);
      assert.ok(executed.evidence_id && executed.outcome_id);
      const evidence = expect(await call(`/api/web/evidence/${executed.evidence_id}`), 200);
      assert.equal(evidence.approval_id, approvalId);
      assert.equal(evidence.agent_id, agent.agent_id);
      assert.equal(evidence.identity_id, agent.agent_id);
      assert.equal(evidence.authentication_method, "api_key");
      assert.ok(evidence.execution_authorization_id && evidence.execution_nonce_reference);
      mark(current, "PASS", { permit_type: "ExecutionAuthorization", authorization_id: evidence.execution_authorization_id, nonce_reference: evidence.execution_nonce_reference, evidence_id: executed.evidence_id });
      current = "controlled_execution";
      mark(current, "PASS", { tool: intent.name, evidence_id: executed.evidence_id, outcome_id: executed.outcome_id, execution_status: executed.execution_status });
      current = "evidence_verification";
      const verified = expect(await call("/api/web/evidence/verify"), 200);
      assert.equal(verified.chain_intact, true);
      assert.equal(verified.cryptographically_signed, false);
      assert.equal(evidence.organization_id, agent.organization_id);
      assert.equal(evidence.action_type, intent.name);
      assert.ok(evidence.request_fingerprint && evidence.arguments_fingerprint);
      mark(current, "PASS", { evidence_id: evidence.evidence_id, local_chain_status: verified.status, independently_witnessed: false });
      const before = expect(await call("/api/web/evidence?limit=100"), 200);
      current = "revocation";
      const disabled = expect(await call(`${authority}/agents/${agent.agent_id}/disable`, "POST", { reason: "Actual customer authority revocation" }), 200);
      assert.equal(disabled.status, "DISABLED");
      assert.equal(disabled.agent_id, agent.agent_id);
      assert.ok(Array.isArray(disabled.revoked_delegations) && disabled.revoked_delegations.length >= 1);
      const inventory = expect(await call(`${authority}/agents`), 200);
      const persisted = inventory.agents.find(item => item.agent_id === agent.agent_id);
      assert.equal(persisted.lifecycle_state, "DISABLED");
      assert.equal(persisted.has_active_delegation, false);
      mark(current, "PASS", { agent_id: agent.agent_id, lifecycle_state: persisted.lifecycle_state, revoked_delegations: disabled.revoked_delegations, revocation_epoch: disabled.revocation_epoch });
      current = "post_revocation_execution_attempt";
      const denied = await call("/api/governance/tools/call", "POST", { name: intent.name, arguments: intent.arguments, purpose: intent.purpose, agent_id: agent.agent_id }, credential.api_key);
      assert.notEqual(denied.value?.error, undefined);
      assert.notEqual(denied.value?.approval_id, approvalId);
      assert.ok(denied.status === 404 || denied.value?.error === "governance_denied" || denied.value?.proceed !== true);
      mark(current, "PASS", { http_status: denied.status, error: denied.value?.error ?? "agent_not_active" });
      current = "post_revocation_denial";
      const replay = await call(`/api/web/approvals/${approvalId}/execute`, "POST");
      assert.equal(replay.status, 409);
      const after = expect(await call("/api/web/evidence?limit=100"), 200);
      assert.deepEqual(after.evidence.map(item => item.evidence_id), before.evidence.map(item => item.evidence_id));
      mark(current, "PASS", { http_status: denied.status, approval_replay_status: replay.status, evidence_unchanged: true });
    }
  }
  }
  stop = current;
} catch (error) {
  if (!stop) { stop = current; mark(current, "FAIL", { error_type: error.name }); }
} finally {
  const boundary = stop;
  if (page) {
    try {
      current = "logout_session_invalidation";
      if (issuedKeyId) expect(await call(`/api/web/api-keys/${issuedKeyId}`, "DELETE"), 200);
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
  console.log(JSON.stringify({ kind: "ACTUAL_APEX_POSTGRESQL_HTTP_CHROMIUM", acceptance: phases.some(phase => phase.status === "FAIL") ? "FAIL" : phases.every(phase => phase.status === "PASS") ? "PASS" : "BLOCKED", stop: phases.every(phase => phase.status === "PASS") ? null : stop, stages: phases, requests, browser: version, authority_seeded: false, development_prototype: Boolean(config.developmentAgentPrototype), production_enabled: false, limitations: ["Virtual browser authenticator, not physical hardware certification", "No credential imports or forged signatures", "No later privileged stage run after a failed or blocked boundary", "Local chain verification is not independent witnessing", "B1 is development-only and default-disabled"] }));
}
