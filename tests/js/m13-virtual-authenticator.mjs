// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Component ceremony qualification only; never grants application authority.
import assert from "node:assert/strict";
import { chromium } from "playwright";

let input = "";
for await (const chunk of process.stdin) input += chunk;
const config = JSON.parse(input);
const origin = new URL(config.origin);
assert.equal(origin.hostname, "localhost");
assert.equal(origin.protocol, "http:");
const browser = await chromium.launch({ headless: true });
try {
  const context = await browser.newContext();
  await context.route("**/*", route => new URL(route.request().url()).origin === origin.origin ? route.continue() : route.abort());
  const page = await context.newPage();
  await page.goto(origin.href);
  const cdp = await context.newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  const { authenticatorId } = await cdp.send("WebAuthn.addVirtualAuthenticator", {
    options: { protocol: "ctap2", transport: "internal", hasResidentKey: true,
      hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true },
  });
  assert.equal((await cdp.send("WebAuthn.getCredentials", { authenticatorId })).credentials.length, 0);
  const result = await page.evaluate(async config => {
    const decode = value => Uint8Array.from(atob(value.replace(/-/g, "+").replace(/_/g, "/")), c => c.charCodeAt(0));
    const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
    const credential = await navigator.credentials.create({ publicKey: {
      challenge: decode(config.registrationChallenge), rp: { id: "localhost", name: "WhitePact isolated component" },
      user: { id: decode(config.userId), name: "disposable@example.invalid", displayName: "Disposable CI identity" },
      pubKeyCredParams: [{ type: "public-key", alg: -7 }],
      authenticatorSelection: { residentKey: "required", userVerification: "required" },
      timeout: 15000, attestation: "none",
    } });
    const registration = { client_data_b64: encode(credential.response.clientDataJSON),
      authenticator_data_b64: encode(credential.response.getAuthenticatorData()), id: credential.id };
    const assertion = await navigator.credentials.get({ publicKey: {
      challenge: decode(config.authenticationChallenge), rpId: "localhost",
      allowCredentials: [{ type: "public-key", id: credential.rawId }],
      userVerification: "required", timeout: 15000,
    } });
    return { registration, assertion: { client_data_b64: encode(assertion.response.clientDataJSON),
      authenticator_data_b64: encode(assertion.response.authenticatorData),
      signature_b64: encode(assertion.response.signature), id: assertion.id } };
  }, config);
  assert.equal(result.registration.id, result.assertion.id);
  console.log(JSON.stringify({ ...result, browser: browser.version(), scope: "COMPONENT_ONLY" }));
} finally {
  await browser.close();
}
