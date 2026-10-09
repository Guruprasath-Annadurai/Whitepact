// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
// Deterministic artifact checks; not a production deployment/field-CWV claim.
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../..");
const built = path.join(root, "src/responsibleai/dashboard/static/whitepact");
const content = path.join(root, "web/src/content");
const pages = Object.assign({}, ...["commerce", "public-info", "corporate"].map(name => JSON.parse(fs.readFileSync(path.join(content, `${name}.json`)))));
const assets = fs.readdirSync(path.join(built, "assets"));
const titles = new Set();
const routes = [];
for (const [key, page] of Object.entries(pages)) {
  const html = fs.readFileSync(path.join(built, "pages", `${key}.html`), "utf8");
  const title = html.match(/<title>([^<]+)<\/title>/)?.[1];
  assert.ok(title && !titles.has(title), `unique static title: ${page.path}`);
  titles.add(title);
  assert.ok(html.includes(`href="https://whitepact.com${page.path}"`), `canonical: ${page.path}`);
  for (const attribute of ['name="description"', 'property="og:title"', 'property="og:description"', 'name="twitter:title"', 'name="twitter:description"', 'property="og:image:alt"', 'name="twitter:image:alt"']) {
    assert.match(html, new RegExp(`<meta ${attribute} content="[^"]+"`), `${page.path}: ${attribute}`);
  }
  assert.equal((html.match(/<h1[ >]/g) ?? []).length, 1, `static H1: ${page.path}`);
  assert.equal(html.includes("og-whitepact.png"), false, "obsolete social card excluded");
  assert.ok(html.includes("og-whitepact-phase3.png"), "current social card is shared");
  assert.equal(html.includes("/Users/ag/"), false, "no local source-path leakage");
  assert.equal(/unsafe-eval|NODE_TLS_REJECT_UNAUTHORIZED/.test(html), false);
  routes.push(page.path);
}
const home = fs.readFileSync(path.join(built, "pages/home.html"), "utf8");
const main = home.match(/<script[^>]+src="([^"]+)"/)?.[1];
const modules = [...home.matchAll(/<link[^>]+rel="modulepreload"[^>]+href="([^"]+)"/g)].map(match => match[1]);
const css = [...home.matchAll(/<link[^>]+rel="stylesheet"[^>]+href="([^"]+)"/g)].map(match => match[1]);
const localSize = url => fs.statSync(path.join(built, url.replace("/static/whitepact/", ""))).size;
const initialJs = [...new Set([main, ...modules])].reduce((total, url) => total + localSize(url), 0);
const initialCss = css.reduce((total, url) => total + localSize(url), 0);
assert.ok(initialJs <= 310000, `initial JS budget: ${initialJs}`);
assert.ok(initialCss <= 80000, `initial CSS budget: ${initialCss}`);
assert.ok(Buffer.byteLength(home) <= 40000, "prerendered homepage HTML budget");
assert.equal(assets.some(name => /^TrustCore-.*\.js$/.test(name)), false, "no corporate 3D chunk");
assert.equal(assets.some(name => /\.map$/.test(name)), false, "no public source maps");
const fonts = assets.filter(name => name.endsWith(".woff2"));
const fontBytes = fonts.reduce((total, name) => total + fs.statSync(path.join(built, "assets", name)).size, 0);
assert.ok(fontBytes <= 102000, "shared font inventory must not grow without review");
const social = fs.readFileSync(path.join(built, "assets/og-whitepact-phase3.png"));
assert.equal(social.readUInt32BE(16), 1672);
assert.equal(social.readUInt32BE(20), 941);
assert.ok(social.length <= 500000, "social image byte budget");
assert.equal(fs.existsSync(path.join(built, "assets/og-whitepact.png")), false, "obsolete preview not shipped");
const sitemap = fs.readFileSync(path.join(built, "sitemap.xml"), "utf8");
for (const route of routes) assert.ok(sitemap.includes(`<loc>https://whitepact.com${route}</loc>`), `sitemap: ${route}`);
assert.equal(/dashboard|workbench|login|signup/.test(sitemap), false, "private routes absent from sitemap");
const inventory = assets.map(name => ({ name, bytes: fs.statSync(path.join(built, "assets", name)).size }));
console.log(JSON.stringify({ status: "PASS", publicRoutes: routes, initialJs, initialCss, homeHtml: Buffer.byteLength(home), fontBytes, socialBytes: social.length, inventory }, null, 2));
