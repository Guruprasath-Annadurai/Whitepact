// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Local Vite fixture preparation, NOT authenticated backend qualification.
import assert from "node:assert/strict";
import { chromium } from "playwright";
import AxeBuilder from "@axe-core/playwright";

const origin = process.env.M12FP_PREVIEW_ORIGIN;
assert(origin && ["127.0.0.1", "localhost"].includes(new URL(origin).hostname), "Explicit local Vite preview required");
const browser = await chromium.launch();
let checks = 0;
try {
  const context = await browser.newContext();
  const page = await context.newPage();
  // Let Vite prepare its dependency graph in a fresh clone before importing
  // optimized dependencies into the isolated fixture shell.
  await page.goto(`${origin}/static/whitepact/`);
  await page.locator("#root > *").first().waitFor();
  await page.route(`${origin}/m12fp-fixture`, (route) => route.fulfill({ contentType: "text/html", body: '<!doctype html><html lang="en"><head><title>Authority preparation fixture</title></head><body><main><h1>Customer authority preparation fixture</h1><div id="fixture"></div></main></body></html>' }));
  await page.goto(`${origin}/m12fp-fixture`);
  await page.evaluate(async () => {
    const { default: refresh } = await import("/static/whitepact/@react-refresh");
    refresh.injectIntoGlobalHook(window);
    window.$RefreshReg$ = () => {};
    window.$RefreshSig$ = () => (type) => type;
    window.__vite_plugin_react_preamble_installed__ = true;
    await import("/static/whitepact/src/styles.css");
  });
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    for (const kind of ["unavailable", "loading", "authentication-required", "forbidden", "expired", "unknown", "error"]) {
      await page.evaluate(async (state) => {
        const reactModule = await import("/static/whitepact/node_modules/.vite/deps/react.js");
        const React = reactModule.default ?? reactModule;
        const clientModule = await import("/static/whitepact/node_modules/.vite/deps/react-dom_client.js");
        const { createRoot } = clientModule.default ?? clientModule;
        const { CustomerAuthorityPreparation } = await import("/static/whitepact/src/features/authority/CustomerAuthorityPreparation.tsx");
        window.preparationRoot ??= createRoot(document.getElementById("fixture"));
        window.preparationRoot.render(React.createElement(CustomerAuthorityPreparation, { state: { kind: state } }));
      }, kind);
      await page.getByRole(kind === "unavailable" || kind === "loading" || kind === "authentication-required" ? "status" : "alert").waitFor();
      assert.equal(await page.locator("button:enabled").count(), 0);
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
      const results = await new AxeBuilder({ page }).analyze();
      assert.deepEqual(results.violations.map((v) => v.id), []);
      checks++;
    }
  }
  let recoveryChecks = 0;
  for (const width of [375, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.evaluate(async () => {
      const module = await import("/static/whitepact/node_modules/.vite/deps/react.js");
      const React = module.default ?? module;
      const { RecoveryRecordsPreparation } = await import("/static/whitepact/src/features/authority/RecoveryRecordsPreparation.tsx");
      window.preparationRoot.render(React.createElement(RecoveryRecordsPreparation, { state: { kind: "ready", records: [{ id: "long-request-".repeat(30), type: "ROOT_RECOVERY", rootId: "root-1", requesterId: "user-1", status: "UNKNOWN_FUTURE", expiresAt: "2026-10-16T00:00:00Z" }] } }));
    });
    await page.getByText("UNKNOWN_FUTURE", { exact: true }).waitFor();
    assert.equal(await page.locator("button").count(), 0);
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    const results = await new AxeBuilder({ page }).analyze();
    assert.deepEqual(results.violations.map((v) => v.id), []);
    recoveryChecks++;
  }
  // Actual Chromium WebAuthn with a virtual authenticator. The local options
  // below are test fixtures, not a server challenge or server verification.
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("WebAuthn.enable");
  await cdp.send("WebAuthn.addVirtualAuthenticator", { options: { protocol: "ctap2", transport: "internal", hasResidentKey: true, hasUserVerification: true, isUserVerified: true, automaticPresenceSimulation: true } });
  const result = await page.evaluate(async () => {
    const { requestPasskey } = await import("/static/whitepact/src/features/authority/passkeyClient.ts");
    const signal = new AbortController().signal;
    const registration = await requestPasskey({ kind: "enroll", options: { challenge: crypto.getRandomValues(new Uint8Array(32)), rp: { id: location.hostname, name: "Local fixture" }, user: { id: new Uint8Array([1]), name: "fixture", displayName: "Fixture" }, pubKeyCredParams: [{ type: "public-key", alg: -7 }], authenticatorSelection: { userVerification: "required" } } }, signal);
    const assertion = await requestPasskey({ kind: "step-up", options: { challenge: crypto.getRandomValues(new Uint8Array(32)), rpId: location.hostname, allowCredentials: [{ type: "public-key", id: registration.rawId }], userVerification: "required" } }, signal);
    return { registration: registration instanceof PublicKeyCredential, assertion: assertion instanceof PublicKeyCredential, sameCredential: assertion.id === registration.id };
  });
  assert.deepEqual(result, { registration: true, assertion: true, sameCredential: true });
  console.log(JSON.stringify({ fixtureViewportStates: checks, recoveryChecks, axeViolations: 0, nativeVirtualAuthenticator: "create/get passed; not server verification", authenticatedBackend: "NOT RUN — accepted M12-FS contract required" }));
} finally { await browser.close(); }
