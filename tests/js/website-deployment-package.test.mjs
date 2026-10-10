// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import { verifyArtifact, rehearseRollback, deploymentEvidence } from "../../web/tooling/deployment/package.mjs";

function fixture(t, suffix, profile = "production") {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "whitepact-deployment-test-"));
  t.after(() => fs.rmSync(directory, { recursive: true }));
  const origin = profile === "production" ? "https://whitepact.com" : "https://staging.whitepact.com";
  const routes = ["/", ...Array.from({ length: 14 }, (_, index) => `/route-${index}`)];
  const content = { "public-routes.json": JSON.stringify({ origin, profile, routes }), [`assets/main-${suffix}.js`]: `// development test only ${suffix}` };
  for (const route of routes) content[`pages/${route === "/" ? "home" : route.slice(1)}.html`] = `<head><link rel="canonical" href="${origin}${route}">${profile === "staging" ? '<meta name="robots" content="noindex,nofollow">' : ""}</head><script src="/static/whitepact/assets/main-${suffix}.js"></script>`;
  for (const [name, text] of Object.entries(content)) { fs.mkdirSync(path.dirname(path.join(directory, name)), { recursive: true }); fs.writeFileSync(path.join(directory, name), text); }
  const manifest = { schema: 1, candidate: suffix.padEnd(40, "a").slice(0, 40), tree: "b".repeat(40), workingTreeClean: true, profile, origin, routeCount: 15, fileCount: Object.keys(content).length, sha256: Object.fromEntries(Object.entries(content).map(([name, text]) => [name, crypto.createHash("sha256").update(text).digest("hex")])) };
  return { directory, manifest };
}

test("exact offline bytes verify without qualification claim", t => {
  const f = fixture(t, "12345678");
  assert.equal(verifyArtifact(f.directory, f.manifest).pass, true);
});
test("tampered bytes fail", t => {
  const f = fixture(t, "12345678"); fs.appendFileSync(path.join(f.directory, "pages/home.html"), "tampered");
  assert.throws(() => verifyArtifact(f.directory, f.manifest), /digest mismatch/);
});
test("unmanifested and missing files fail", t => {
  const f = fixture(t, "12345678"); fs.writeFileSync(path.join(f.directory, "extra.txt"), "extra");
  assert.throws(() => verifyArtifact(f.directory, f.manifest), /unmanifested/);
  fs.unlinkSync(path.join(f.directory, "extra.txt")); fs.unlinkSync(path.join(f.directory, "pages/home.html"));
  assert.throws(() => verifyArtifact(f.directory, f.manifest), /Missing/);
});
test("symlinks and path traversal fail", t => {
  const f = fixture(t, "12345678"); fs.symlinkSync("pages/home.html", path.join(f.directory, "alias"));
  assert.throws(() => verifyArtifact(f.directory, f.manifest), /Symlink/);
  assert.throws(() => verifyArtifact(f.directory, { ...f.manifest, sha256: { "../escape": "a".repeat(64) }, fileCount: 1 }), /Invalid digest/);
});
test("dirty source and invalid production origin fail", t => {
  const f = fixture(t, "12345678");
  assert.throws(() => verifyArtifact(f.directory, { ...f.manifest, workingTreeClean: false }), /Clean/);
  assert.throws(() => verifyArtifact(f.directory, { ...f.manifest, origin: "https://staging.whitepact.com" }), /Noncanonical/);
});
test("staging inventory is isolated from production", t => {
  const f = fixture(t, "12345678", "staging"); assert.equal(verifyArtifact(f.directory, f.manifest).profile, "staging");
  const prod = fixture(t, "abcdef12");
  assert.throws(() => rehearseRollback(prod.directory, prod.manifest, f.directory, f.manifest), /mix profiles/);
});
test("emergency rollback preserves both HTML generations and changes nothing", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "abcdef12");
  const result = rehearseRollback(old.directory, old.manifest, next.directory, next.manifest);
  assert.equal(result.checkedReferences, 30); assert.equal(result.retainedAssetCount, 2);
  assert.equal(result.infrastructureRollbackProven, false); assert.equal(result.networkRequests, 0); assert.equal(result.filesChanged, 0);
  assert.equal(verifyArtifact(old.directory, old.manifest).pass, true); assert.equal(verifyArtifact(next.directory, next.manifest).pass, true);
});
test("same asset URL with different bytes blocks activation", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "12345678");
  const name = "assets/main-12345678.js"; fs.writeFileSync(path.join(next.directory, name), "changed");
  next.manifest.sha256[name] = crypto.createHash("sha256").update("changed").digest("hex");
  assert.throws(() => rehearseRollback(old.directory, old.manifest, next.directory, next.manifest), /collision/);
});
test("missing old HTML dependency fails despite internally valid manifest", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "abcdef12");
  const name = "pages/home.html";
  const html = fs.readFileSync(path.join(old.directory, name), "utf8").replace("main-12345678.js", "missing-12345678.js");
  fs.writeFileSync(path.join(old.directory, name), html);
  old.manifest.sha256[name] = crypto.createHash("sha256").update(html).digest("hex");
  assert.throws(() => rehearseRollback(old.directory, old.manifest, next.directory, next.manifest), /dependency absent/);
});
test("staging loopback and private route inventory fail", t => {
  const f = fixture(t, "12345678", "staging");
  assert.throws(() => verifyArtifact(f.directory, { ...f.manifest, origin: "https://127.0.0.1" }), /public HTTPS/);
  const name = "public-routes.json", routes = JSON.parse(fs.readFileSync(path.join(f.directory, name), "utf8"));
  routes.routes[1] = "/dashboard";
  const content = JSON.stringify(routes); fs.writeFileSync(path.join(f.directory, name), content);
  f.manifest.sha256[name] = crypto.createHash("sha256").update(content).digest("hex");
  assert.throws(() => verifyArtifact(f.directory, f.manifest), /Invalid public/);
});
test("deployment evidence is deterministic and never claims external activation", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "abcdef12");
  const first = deploymentEvidence(old.directory, old.manifest, next.directory, next.manifest);
  assert.deepEqual(first, deploymentEvidence(old.directory, old.manifest, next.directory, next.manifest));
  assert.equal(first.deploymentAuthorized, false);
  assert.ok(Object.values(first.externalChecks).every(value => value === "NOT VERIFIED"));
  assert.equal(first.networkRequests, 0); assert.equal(first.filesChanged, 0);
  assert.equal(first.layout.nextRelease, `releases/${next.manifest.candidate}/public`);
  assert.match(first.failureRecovery.beforeActivation, /current unchanged/);
  assert.match(first.failureRecovery.afterActivation, /prior current target on every serving instance/);
});
test("evidence manifest digest independent of key order and contains no local path", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "abcdef12");
  const a = deploymentEvidence(old.directory, old.manifest, next.directory, next.manifest);
  const reordered = Object.fromEntries(Object.entries(next.manifest).reverse());
  reordered.sha256 = Object.fromEntries(Object.entries(next.manifest.sha256).reverse());
  const b = deploymentEvidence(old.directory, old.manifest, next.directory, reordered);
  assert.equal(a.next.manifestDigest, b.next.manifestDigest);
  assert.equal(JSON.stringify(a).includes(next.directory), false);
});
test("evidence generation rejects failed-deploy artifact before any plan", t => {
  const old = fixture(t, "12345678"), next = fixture(t, "abcdef12");
  fs.appendFileSync(path.join(next.directory, "pages/home.html"), "failed upload");
  assert.throws(() => deploymentEvidence(old.directory, old.manifest, next.directory, next.manifest), /digest mismatch/);
  assert.equal(verifyArtifact(old.directory, old.manifest).pass, true);
});
