// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import test from "node:test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { execFileSync } from "node:child_process";
import crypto from "node:crypto";
import { headers, csp, audit, manifest, output, root, smoke, validateSecurityContact, assetDeploymentPlan } from "../../web/tooling/launch-contract.mjs";
test("CSP forbids inline/eval and framing", () => {
  assert.ok(csp.includes("frame-ancestors 'none'"));
  assert.ok(!csp.includes("unsafe-"));
});
test("cache distinguishes immutable assets, HTML, discovery and private content", () => {
  assert.match(headers("/static/whitepact/assets/index-abcdefgh.js")["Cache-Control"], /immutable/);
  assert.equal(headers("/static/whitepact/assets/whitepact-mark.png")["Cache-Control"], "no-cache");
  assert.equal(headers("/")["Cache-Control"], "no-cache");
  assert.equal(headers("/dashboard", { privateContent: true })["Cache-Control"], "private, no-store");
  assert.match(headers("/robots.txt")["Cache-Control"], /max-age=300/);
});
test("HSTS starts short without subdomain/preload commitment", () => {
  assert.equal(headers("/", { https: true })["Strict-Transport-Security"], "max-age=300");
  assert.equal(headers("/")["Strict-Transport-Security"], undefined);
});
test("built public routes and leak/asset checks pass", () => assert.deepEqual(audit().problems, []));
test("generated route inventory agrees with the actual React router", () => {
  const source = fs.readFileSync(path.join(root, "web/src/App.tsx"), "utf8");
  const discovered = [...source.matchAll(/<Route path="(\/[^"]*)"/g)].map(match => match[1]);
  const dynamic = source.match(/\(\[([^\]]+)\] as const\)\.map\(\(pageKey\)/);
  assert.ok(dynamic, "Review router inventory extraction when routing architecture changes");
  discovered.push(...[...dynamic[1].matchAll(/"([^"]+)"/g)].map(match => "/" + match[1]));
  const publicRoutes = discovered.filter(route => !/^\/(dashboard|onboarding|login|signup|verify-email|forgot-password|reset-password|accept-invitation|billing|admin|sovereign\/workbench)(\/|$)/.test(route) && route !== "/refunds").sort();
  assert.deepEqual(publicRoutes, JSON.parse(fs.readFileSync(path.join(output, "public-routes.json"))).routes);
});
test("manifest deterministic with complete deployment hashes", () => {
  const first = manifest();
  assert.deepEqual(first, manifest());
  assert.equal(first.routeCount, 15);
  for (const file of ["robots.txt", "sitemap.xml", "pages/not-found.html", "pages/home.html", "index.html"]) assert.match(first.sha256[file], /^[a-f0-9]{64}$/);
  assert.equal(first.fileCount, Object.keys(first.sha256).length);
});
test("tampered artifact changes hashes and fails private-indexing audit", () => {
  const temp = fs.mkdtempSync(path.join(os.tmpdir(), "whitepact-launch-negative-"));
  try {
    fs.cpSync(output, temp, { recursive: true });
    const before = manifest(temp);
    fs.writeFileSync(path.join(temp, "pages/private.html"), '<html><title>Private</title></html>');
    assert.notEqual(manifest(temp).sha256["pages/private.html"], before.sha256["pages/private.html"]);
    assert.ok(audit(temp).problems.includes("Private shell indexing"));
  } finally { fs.rmSync(temp, { recursive: true }); }
});
test("smoke rejects insecure remote and nonlocal local profile before networking", async () => {
  await assert.rejects(smoke("http://whitepact.com"), /HTTPS/);
  await assert.rejects(smoke("https://whitepact.com", { local: true }), /loopback/);
});
test("security contact activation requires owner approval and valid nonplaceholder expiry", () => {
  const now = Date.parse("2026-10-06T00:00:00Z");
  const actualPolicy = "https://github.com/Guruprasath-Annadurai/Whitepact/security/policy";
  assert.throws(() => validateSecurityContact({ contact: actualPolicy, expires: "2027-01-01T00:00:00Z" }, now), /REQUIRED/);
  assert.throws(() => validateSecurityContact({ contact: "mailto:security@example.com", expires: "2027-01-01T00:00:00Z", ownerApproved: true }, now), /Placeholder/);
  assert.throws(() => validateSecurityContact({ contact: actualPolicy, expires: "2020-01-01T00:00:00Z", ownerApproved: true }, now), /expires/);
  assert.throws(() => validateSecurityContact({ contact: actualPolicy, expires: "2027-02-31T00:00:00Z", ownerApproved: true }, now), /expires/);
  assert.equal(validateSecurityContact({ contact: actualPolicy, expires: "2027-01-01T00:00:00Z", ownerApproved: true }, now).contact, actualPolicy);
});
test("deployment retention covers actual qualified old HTML and new HTML assets", () => {
  const base = "9a721aa078daba5d554120d7aeb61d5febcdcc79";
  const prefix = "src/responsibleai/dashboard/static/whitepact/";
  const git = (...args) => execFileSync("git", args, { cwd: root, encoding: "utf8" });
  const names = git("ls-tree", "-r", "--name-only", base, "--", prefix + "assets").trim().split("\n").map(name => name.slice(prefix.length));
  const current = manifest();
  const previousHashes = Object.fromEntries(names.map(name => [name, crypto.createHash("sha256").update(execFileSync("git", ["show", `${base}:${prefix}${name}`], { cwd: root })).digest("hex")]));
  const plan = assetDeploymentPlan({ candidate: base, sha256: previousHashes }, current);
  const retained = new Set([...plan.retainPrevious, ...plan.uploadBeforeHtml]);
  for (const html of [git("show", `${base}:${prefix}pages/home.html`), fs.readFileSync(path.join(output, "pages/home.html"), "utf8")]) {
    for (const match of html.matchAll(/(?:src|href)="\/static\/whitepact\/(assets\/[^"?#]+)"/g)) assert.ok(retained.has(match[1]), `Deployment plan missing ${match[1]}`);
  }
});
test("unsafe mixed-version unversioned replacement fails closed", () => {
  assert.throws(() => assetDeploymentPlan({ sha256: { "assets/logo.png": "old" } }, { sha256: { "assets/logo.png": "new" } }), /Unversioned asset changed/);
});
