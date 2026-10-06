// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import { createServer } from "vite";
import react from "@vitejs/plugin-react";
import commerce from "../src/content/commerce.json" with { type: "json" };
import corporate from "../src/content/corporate.json" with { type: "json" };
import information from "../src/content/public-info.json" with { type: "json" };
import { controlChain } from "../src/content/control-chain.ts";
import { siteContract } from "../src/content/site-origin.ts";

const escape = (text: string) => text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
const links = [["/product", "Product"], ["/architecture", "Architecture"], ["/developers", "Developers"], ["/security", "Security"], ["/enterprise", "Enterprise"], ["/docs", "Docs"], ["/about", "Company"], ["/trust", "Trust"], ["/pricing", "Pricing"], ["/terms", "Terms"], ["/privacy", "Privacy"], ["/refund-policy", "Refund Policy"], ["/contact", "Contact"]];
type Page = { path: string; title: string; heading: string; description: string; sections: string[][] };

function metadata(template: string, page: Page, origin: string) {
  const url = `${origin}${page.path}`;
  let html = template.replace(/<title>[^<]*<\/title>/, `<title>${escape(page.title)}</title>`);
  for (const [selector, value] of [['name="description"', page.description], ['property="og:title"', page.title], ['property="og:description"', page.description], ['property="og:url"', url], ['name="twitter:title"', page.title], ['name="twitter:description"', page.description]]) {
    html = html.replace(new RegExp(`<meta ${selector} content="[^"]*"\\s*/?>`), `<meta ${selector} content="${escape(value)}" />`);
  }
  return html.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${url}" />`);
}

/** Static editorial fallbacks and metadata. No remote fetching or request-time SSR. */
export function originMetadata(site = siteContract()): Plugin {
  return {
    name: "whitepact-site-origin",
    transformIndexHtml(html) {
      return html.split("__WHITEPACT_SITE_ORIGIN__").join(site.origin).replace(/<meta name="robots" content="[^"]*"\s*\/?>/, `<meta name="robots" content="${site.noIndex ? "noindex,nofollow" : "index, follow"}" />`);
    },
  };
}

export function publicPages(site = siteContract()): Plugin {
  let outDir: string;
  let root: string;
  return {
    name: "whitepact-public-pages",
    apply: "build",
    configResolved(config) { root = config.root; outDir = resolve(config.root, config.build.outDir); },
    async closeBundle() {
      const template = await readFile(resolve(outDir, "index.html"), "utf8");
      const renderer = await createServer({ root, base: "/static/whitepact/", configFile: false, plugins: [react()], server: { middlewareMode: true, hmr: false, ws: false }, appType: "custom" });
      let home: string;
      try {
        const module = await renderer.ssrLoadModule("/tooling/prerender-home.tsx");
        home = module.renderHome();
      } finally { await renderer.close(); }
      // Public heading/body fonts otherwise wait for the stylesheet discovery
      // round trip. Keep preloads off private application shells and avoid
      // preloading below-the-fold weights or optional illustration assets.
      const assets = await readdir(resolve(outDir, "assets"));
      const criticalFonts = ["sora-latin-400-normal-", "manrope-latin-400-normal-"]
        .map(prefix => assets.find(name => name.startsWith(prefix) && name.endsWith(".woff2")));
      if (criticalFonts.some(name => !name)) throw new Error("Public critical font missing from build");
      const fontPreloads = criticalFonts.map(name => `<link rel="preload" href="/static/whitepact/assets/${name}" as="font" type="font/woff2" crossorigin />`).join("\n");
      await mkdir(resolve(outDir, "pages"), { recursive: true });
      const pages: Record<string, Page> = { ...commerce, ...information, ...corporate };
      const navigation = links.map(([href, label]) => `<a href="${href}">${label}</a>`).join(" ");
      for (const [key, page] of Object.entries(pages)) {
        let html = metadata(template, page, site.origin).replace("</head>", `${fontPreloads}\n</head>`);
        const prices = key === "pricing" || key === "home" ? `<div class="launch-pricing" aria-label="Evaluation options">${commerce.pricing.plans.map(plan => `<article><h3>${escape(plan.name)}</h3><p>${escape(plan.status)}</p><strong>${escape(plan.monthly)}</strong><p>${escape(plan.copy)}</p><a href="${escape(plan.href)}">${escape(plan.cta)}</a></article>`).join("")}</div>` : "";
        const fallback = `<noscript><header><a href="/">WhitePact</a><nav aria-label="Primary navigation">${navigation}</nav></header><main id="static-main" class="editorial-page"><h1>${escape(page.heading)}</h1><p class="page-lead">${escape(page.description)}</p>${page.sections.map(([title, copy]) => `<section><div><h2>${escape(title)}</h2><p>${escape(copy)}</p></div></section>`).join("")}${prices}<p><a href="/contact">Discuss an evaluation</a></p></main><footer><nav aria-label="Public footer">${navigation}</nav></footer></noscript>`;
        const chain = key === "home" || key === "architecture" ? `<section><h2>Conceptual control chain</h2><p>This map does not assert every adapter invokes every subsystem. Isolation depends on configured deployment.</p><ol>${controlChain.map(stage => `<li>${escape(stage)}</li>`).join("")}</ol></section>` : "";
        const contact = key === "contact" ? '<p><a href="mailto:annaduraiguruprasath7@gmail.com?subject=WhitePact%20evaluation">Start an evaluation inquiry</a></p><p>This published project contact is not a staffed support desk or an SLA-backed service. Do not send credentials or confidential execution data.</p>' : "";
        const disclosure = key === "contact" || key === "security" ? '<p><a href="https://github.com/Guruprasath-Annadurai/Whitepact/blob/main/SECURITY.md">Coordinated security disclosure process</a></p>' : "";
        html = key === "home"
          ? html.replace('<div id="root"></div>', `<div id="root" data-prerendered="home">${home}</div><noscript><p>Interactive demonstration controls require JavaScript. Documentation and evaluation links remain available.</p></noscript>`)
          : html.replace('<div id="root"></div>', `<div id="root">${fallback.replace(/^<noscript>|<\/noscript>$/g, "").replace("</main>", `${chain}${contact}${disclosure}</main>`)}</div>`);
        await writeFile(resolve(outDir, "pages", `${key}.html`), html);
      }
      // Auth, billing returns and product shells never inherit the public home canonical.
      const privateHtml = template
        .replace(/<title>[^<]*<\/title>/, "<title>WhitePact authenticated application</title>")
        .replace(/<meta name="robots" content="[^"]*"\s*\/?>/, '<meta name="robots" content="noindex,nofollow" />')
        .replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, "")
        .replace(/<meta property="og:url" content="[^"]*"\s*\/?>/, "")
        .replace(/<meta (name|property)="(description|og:description|twitter:description)" content="[^"]*"\s*\/?>/g, '<meta $1="$2" content="WhitePact authenticated application. Session and backend authorization are required for protected operations." />')
        .replace(/<meta (name|property)="(og:title|twitter:title)" content="[^"]*"\s*\/?>/g, '<meta $1="$2" content="WhitePact authenticated application" />')
        .replace(/<script type="application\/ld\+json">[\s\S]*?<\/script>/g, "")
        .replace(/[ \t]+$/gm, "");
      await writeFile(resolve(outDir, "pages", "private.html"), privateHtml);
      const notFound = privateHtml.replace(/WhitePact authenticated application/g, "Page not found | WhitePact")
        .replace(/Session and backend authorization are required for protected operations\./g, "The requested page could not be found.")
        .replace('<div id="root"></div>', '<div id="root"><main><h1>Page not found</h1><p>The requested page does not exist.</p><a href="/">Return home</a></main></div>');
      await writeFile(resolve(outDir, "pages", "not-found.html"), notFound);
      // Route truth is the same editorial inventory used to emit public HTML.
      const routes = Object.values(pages).map(page => page.path).sort();
      await writeFile(resolve(outDir, "public-routes.json"), JSON.stringify({ version: 1, origin: site.origin, profile: site.profile, routes, redirects: { "/refunds": "/refund-policy" } }, null, 2) + "\n");
      const productionRobots = await readFile(resolve(root, "public/robots.txt"), "utf8");
      const robots = site.noIndex ? "User-agent: *\nDisallow: /\n" : productionRobots.split("__WHITEPACT_SITE_ORIGIN__").join(site.origin);
      await writeFile(resolve(outDir, "robots.txt"), robots);
      await writeFile(resolve(outDir, "sitemap.xml"), `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${routes.map(route => `  <url><loc>${site.origin}${route}</loc></url>`).join("\n")}\n</urlset>\n`);
      const llms = await readFile(resolve(root, "public/llms.txt"), "utf8");
      await writeFile(resolve(outDir, "llms.txt"), llms.split("__WHITEPACT_SITE_ORIGIN__").join(site.origin));
      await writeFile(resolve(outDir, "maintenance.html"), '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>Temporarily unavailable | WhitePact</title></head><body><main><h1>WhitePact is temporarily unavailable</h1><p>Please try again later. No action completion is implied by this page.</p></main></body></html>\n');
    },
  };
}
