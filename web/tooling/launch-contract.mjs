// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import http from "node:http";
import { gzipSync } from "node:zlib";

export const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
export const output = path.join(root, "src/responsibleai/dashboard/static/whitepact");
export const csp = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; object-src 'none'; base-uri 'none'; form-action 'self'";
/** Validation only. This function never publishes an unapproved security contact. */
export function validateSecurityContact({ contact, expires, ownerApproved = false }, now) {
  if (!ownerApproved) throw new Error("OFFICIAL_SECURITY_CONTACT_REQUIRED");
  if (/example|\.invalid|TODO|TBD|localhost/i.test(contact)) throw new Error("Placeholder security contact prohibited");
  const uri = new URL(contact);
  if (!["mailto:", "https:"].includes(uri.protocol) || uri.username || uri.password) throw new Error("Invalid security contact URI");
  if (uri.protocol === "https:" && (!uri.hostname.includes(".") || /(^[\d.]+$|:|\.(local|internal|test|invalid)$)/i.test(uri.hostname))) throw new Error("Security contact requires public hostname");
  if (uri.protocol === "mailto:" && !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(uri.pathname)) throw new Error("Invalid security email");
  const expiry = Date.parse(expires);
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(expires) || !Number.isFinite(expiry) || new Date(expiry).toISOString().replace(".000Z", "Z") !== expires || expiry <= now || expiry - now >= 365 * 86400000) throw new Error("Security contact expires must be valid UTC RFC3339, future and less than one year");
  return { contact, expires };
}
export function headers(resource, { https = false, privateContent = false } = {}) {
  const hashed = /^\/static\/whitepact\/assets\/.+-[A-Za-z0-9_-]{8,}\.(js|css|woff2?)$/.test(resource);
  return {
    "Content-Security-Policy": csp,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cache-Control": privateContent ? "private, no-store" : hashed ? "public, max-age=31536000, immutable" : ["/robots.txt", "/sitemap.xml", "/llms.txt"].includes(resource) ? "public, max-age=300" : "no-cache",
    ...(https ? { "Strict-Transport-Security": "max-age=300" } : {}),
  };
}
export function assetDeploymentPlan(previous, current) {
  const oldAssets = Object.keys(previous.sha256).filter(name => name.startsWith("assets/"));
  for (const name of oldAssets) {
    const hashed = /-[A-Za-z0-9_-]{8,}\.(js|css|woff2?)$/.test(name);
    if (!hashed && current.sha256[name] && current.sha256[name] !== previous.sha256[name]) throw new Error(`Unversioned asset changed; version or independently verify backward compatibility: ${name}`);
  }
  return { previousCandidate: previous.candidate, currentCandidate: current.candidate, uploadBeforeHtml: Object.keys(current.sha256).filter(name => name.startsWith("assets/")), retainPrevious: oldAssets, activation: "Atomic HTML swap only after all old/new asset references resolve; no asset deletion" };
}
function files(dir, prefix = "") {
  return fs.readdirSync(dir).sort().flatMap(name => {
    const relative = prefix + name;
    return fs.statSync(path.join(dir, name)).isDirectory() ? files(path.join(dir, name), relative + "/") : [relative];
  });
}
export function manifest(dir = output) {
  const sha256 = Object.fromEntries(files(dir).map(name => [name, crypto.createHash("sha256").update(fs.readFileSync(path.join(dir, name))).digest("hex")]));
  const git = (...args) => execFileSync("git", args, { cwd: root, encoding: "utf8" }).trim();
  const routes = JSON.parse(fs.readFileSync(path.join(dir, "public-routes.json")));
  return { schema: 1, candidate: git("rev-parse", "HEAD"), tree: git("rev-parse", "HEAD^{tree}"), workingTreeClean: git("status", "--porcelain") === "", timestampPolicy: "Git commit time; no wall-clock build timestamp", sourceEpoch: Number(git("show", "-s", "--format=%ct", "HEAD")), profile: routes.profile, origin: routes.origin, routeCount: routes.routes.length, fileCount: Object.keys(sha256).length, sha256 };
}
export function audit(dir = output) {
  const routes = JSON.parse(fs.readFileSync(path.join(dir, "public-routes.json")));
  const problems = [];
  const fail = (condition, message) => { if (!condition) problems.push(message); };
  const sitemap = fs.readFileSync(path.join(dir, "sitemap.xml"), "utf8");
  fail(routes.routes.length === 15 && new Set(routes.routes).size === 15, "Public route inventory drift");
  for (const route of routes.routes) {
    const name = route === "/" ? "home" : route.slice(1);
    const html = fs.readFileSync(path.join(dir, `pages/${name}.html`), "utf8");
    fail(html.includes(`rel="canonical" href="${routes.origin}${route}"`), `Canonical mismatch: ${route}`);
    fail(sitemap.includes(`<loc>${routes.origin}${route}</loc>`), `Sitemap missing: ${route}`);
    fail(!routes.routes.some(route => /^\/(api|dashboard|login|signup|admin|onboarding)(\/|$)/.test(route)), "Private route in sitemap inventory");
    fail(/<h1[\s>]/.test(html), `No static heading: ${route}`);
    if (routes.profile !== "production") fail(html.includes('content="noindex,nofollow"'), `Staging indexing: ${route}`);
  }
  const privateHtml = fs.readFileSync(path.join(dir, "pages/private.html"), "utf8");
  fail(privateHtml.includes('content="noindex,nofollow"') && !privateHtml.includes('rel="canonical"'), "Private shell indexing");
  for (const filename of files(dir)) {
    const buffer = fs.readFileSync(path.join(dir, filename));
    if (filename.endsWith(".js")) fail(gzipSync(buffer).length <= 100000, `JS chunk gzip budget exceeded: ${filename}`);
    if (filename.endsWith(".css")) fail(gzipSync(buffer).length <= 20000, `CSS gzip budget exceeded: ${filename}`);
    fail(!filename.endsWith(".map"), `Public source map: ${filename}`);
    if (!/\.(html|js|css|txt|json|xml)$/.test(filename)) continue;
    const text = buffer.toString();
    fail(!text.includes("__WHITEPACT_SITE_ORIGIN__"), `Unexpanded origin template: ${filename}`);
    fail(!/\/Users\/|\/home\/(runner|ag)\/|pdl_(live|sdbx)_apikey_|sk_live_[A-Za-z0-9]|BEGIN (RSA |OPENSSH )?PRIVATE KEY/.test(text), `Credential/local-path leakage: ${filename}`);
    if (filename.endsWith(".html")) {
      fail(!/\b(TODO|TBD|FIXME)\b|Example Inc\.|123 Main Street/.test(text), `Unresolved public placeholder: ${filename}`);
      for (const match of text.matchAll(/(?:src|href)="(\/static\/whitepact\/[^"?#]+)"/g)) fail(fs.existsSync(path.join(dir, match[1].slice("/static/whitepact/".length))), `Missing asset: ${match[1]}`);
    }
  }
  return { pass: problems.length === 0, problems, routes: routes.routes.length };
}

export function packageInventory() {
  const inventory = [];
  for (const filename of files(path.join(root, "web/src"))) {
    if (!/\.(json|tsx?|md)$/.test(filename) || filename.includes(".test.")) continue;
    const lines = fs.readFileSync(path.join(root, "web/src", filename), "utf8").split("\n");
    lines.forEach((line, index) => {
      for (const name of line.match(/rai-governance-platform|responsibleai|whitepact-client|rai-client|\bwhitepact\b/g) ?? []) {
        const classification = name === "responsibleai" ? "INTERNAL IMPLEMENTATION NAMESPACE" : name === "rai-client" ? "COMPATIBILITY IDENTITY" : name === "rai-governance-platform" ? "PUBLIC INSTALLATION IDENTITY" : /legacy|historical/i.test(line) ? "VALID HISTORICAL REFERENCE" : "BRAND OR FUTURE IDENTITY; MANUAL REVIEW REQUIRED";
        inventory.push({ file: `web/src/${filename}`, line: index + 1, identity: name, classification });
      }
    });
  }
  return inventory;
}

export async function previewSmoke() {
  const inventory = JSON.parse(fs.readFileSync(path.join(output, "public-routes.json")));
  const mime = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".webp": "image/webp", ".woff2": "font/woff2", ".xml": "application/xml", ".txt": "text/plain" };
  const server = http.createServer((req, res) => {
    const resource = new URL(req.url, "http://localhost").pathname;
    if (!["GET", "HEAD"].includes(req.method)) { res.writeHead(405).end(); return; }
    if (resource === "/refunds") { res.writeHead(308, { Location: "/refund-policy" }).end(); return; }
    const asset = resource.startsWith("/static/whitepact/");
    const discovery = ["/robots.txt", "/sitemap.xml", "/llms.txt"].includes(resource);
    const known = inventory.routes.includes(resource);
    const privateContent = resource === "/login";
    const name = asset ? resource.slice("/static/whitepact/".length) : discovery ? resource.slice(1) : known ? `pages/${resource === "/" ? "home" : resource.slice(1)}.html` : "pages/not-found.html";
    const target = path.resolve(output, privateContent ? "pages/private.html" : name);
    if (!target.startsWith(output + path.sep) || !fs.existsSync(target)) { res.writeHead(404, headers(resource)).end(); return; }
    res.writeHead(asset || discovery || known || privateContent ? 200 : 404, { ...headers(resource, { privateContent }), "Content-Type": mime[path.extname(target)] ?? "application/octet-stream" });
    if (req.method === "HEAD") res.end(); else fs.createReadStream(target).pipe(res);
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  try { return await smoke(`http://127.0.0.1:${server.address().port}`, { local: true, staging: inventory.profile !== "production" }); }
  finally { await new Promise(resolve => server.close(resolve)); }
}

/** Read-only HTTP checks. Explicit target mandatory; local profile does not prove TLS/edge. */
export async function smoke(base, { local = false, expectedOrigin, staging = false } = {}) {
  if (process.env.NODE_TLS_REJECT_UNAUTHORIZED === "0") throw new Error("TLS validation must remain enabled");
  let url;
  try { url = new URL(base); } catch { throw new Error("Malformed BASE_URL origin"); }
  if (url.pathname !== "/" || url.search || url.hash || url.username || url.password) throw new Error("BASE_URL must be an origin");
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("BASE_URL must be HTTP(S)");
  if (!local && url.protocol !== "https:") throw new Error("Launch target must use HTTPS");
  if (local && !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) throw new Error("Local preview must be loopback");
  const routes = JSON.parse(fs.readFileSync(path.join(output, "public-routes.json")));
  const canonical = expectedOrigin ?? routes.origin;
  const results = [];
  async function check(route, status, html = false, privateContent = false) {
    const response = await fetch(new URL(route, base), { redirect: "manual", signal: AbortSignal.timeout(15000) });
    const body = await response.text();
    const errors = [];
    if (response.status !== status) errors.push(`status ${response.status}, expected ${status}`);
    // Product routes own their CSP (checkout/auth may need other origins).
    // The website gate asserts their cache/indexing isolation, not a public CSP override.
    const expectedHeaders = privateContent ? { "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } : headers(route, { https: !local });
    for (const [key, value] of Object.entries(expectedHeaders)) if (response.headers.get(key) !== value) errors.push(`header mismatch ${key}`);
    if (html && status === 200 && !privateContent && !body.includes(`rel="canonical" href="${canonical}${route}"`)) errors.push("canonical mismatch");
    if (html && !privateContent && !/<h1[\s>]/.test(body)) errors.push("missing static heading");
    if (privateContent && (!/noindex/.test(body) || /rel="canonical"/.test(body))) errors.push("private indexing");
    if (route === "/robots.txt" && (staging ? !/^Disallow: \/\s*$/m.test(body) : /^Disallow: \/\s*$/m.test(body))) errors.push("robots profile mismatch");
    if (route === "/sitemap.xml" && (/\/(dashboard|login|signup|admin|onboarding|sovereign\/workbench)(<|\/)/.test(body) || routes.routes.some(route => !body.includes(`<loc>${canonical}${route}</loc>`)))) errors.push("sitemap route/origin mismatch");
    if (/\/Users\/|BEGIN .*PRIVATE KEY|Traceback \(most recent call last\)/.test(body)) errors.push("private/error leakage");
    if (html && staging && !/noindex/.test(body)) errors.push("staging indexing");
    if (html && /(?:src|href)="http:\/\//.test(body)) errors.push("mixed content");
    if (html && status === 200) {
      for (const match of body.matchAll(/(?:src|href)="(\/static\/whitepact\/[^"?#]+)"/g)) {
        const asset = await fetch(new URL(match[1], base), { redirect: "manual", signal: AbortSignal.timeout(15000) });
        if (asset.status !== 200) errors.push(`asset ${match[1]}: ${asset.status}`);
        if (!local && /\.(js|css)$/.test(match[1]) && !/gzip|br|zstd/.test(asset.headers.get("content-encoding") ?? "")) errors.push(`asset compression missing: ${match[1]}`);
        await asset.body?.cancel();
      }
    }
    results.push({ route, pass: !errors.length, errors });
    return response;
  }
  for (const route of routes.routes) await check(route, 200, true);
  await check("/this-page-does-not-exist", 404, true);
  for (const route of ["/robots.txt", "/sitemap.xml", "/llms.txt"]) await check(route, 200);
  await check("/login", 200, true, true);
  const redirect = await fetch(new URL("/refunds", base), { redirect: "manual" });
  results.push({ route: "/refunds", pass: [301, 308].includes(redirect.status) && new URL(redirect.headers.get("location"), base).pathname === "/refund-policy" });
  if (!local) {
    const httpOrigin = new URL(base); httpOrigin.protocol = "http:"; httpOrigin.port = "";
    const response = await fetch(httpOrigin, { redirect: "manual", signal: AbortSignal.timeout(15000) });
    const location = response.headers.get("location");
    results.push({ route: "HTTP_TO_HTTPS", pass: [301, 308].includes(response.status) && location !== null && new URL(location, httpOrigin).origin === url.origin });
  }
  return { pass: results.every(row => row.pass), transport: local ? "LOCAL ONLY; TLS/DNS/edge unverified" : "HTTPS certificate validated by client", results };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const command = process.argv[2];
  let result;
  if (command === "manifest") {
    result = manifest();
    if (!result.workingTreeClean) throw new Error("Release manifest requires clean source and build artifacts; commit/verify candidate first");
  }
  else if (command === "inventory") result = packageInventory();
  else if (command === "preview-smoke") result = await previewSmoke();
  else if (command === "verify") {
    const expected = JSON.parse(fs.readFileSync(process.argv[3]));
    result = { pass: JSON.stringify(expected) === JSON.stringify(manifest()) };
  } else if (command === "audit") result = audit();
  else if (command === "smoke") {
    if (!process.env.BASE_URL) throw new Error("Explicit BASE_URL required; no production default");
    result = await smoke(process.env.BASE_URL, { local: process.argv.includes("--local"), expectedOrigin: process.env.EXPECTED_SITE_ORIGIN, staging: process.argv.includes("--staging") });
  } else throw new Error("Expected manifest, verify <manifest>, audit, or smoke");
  const outputFlag = process.argv.indexOf("--output");
  if (command === "manifest" && outputFlag !== -1) {
    const destination = process.argv[outputFlag + 1];
    if (!destination || !path.isAbsolute(destination) || destination.startsWith(root + path.sep)) throw new Error("Manifest sidecar must use an absolute path outside the checkout/artifact set");
    fs.writeFileSync(destination, JSON.stringify(result, null, 2) + "\n", { flag: "wx" });
    console.log(JSON.stringify({ manifest: destination, candidate: result.candidate, fileCount: result.fileCount }));
  } else console.log(JSON.stringify(result, null, 2));
  if (result.pass === false) process.exitCode = 1;
}
