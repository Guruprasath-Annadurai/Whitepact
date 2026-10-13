// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import commerce from "../src/content/commerce.json" with { type: "json" };
import corporate from "../src/content/corporate.json" with { type: "json" };
import information from "../src/content/public-info.json" with { type: "json" };
import { controlChain } from "../src/content/control-chain.ts";

const escape = (text: string) => text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
const links = [["/product", "Product"], ["/architecture", "Architecture"], ["/developers", "Developers"], ["/security", "Security"], ["/enterprise", "Enterprise"], ["/docs", "Docs"], ["/about", "Company"], ["/trust", "Trust"], ["/pricing", "Pricing"], ["/terms", "Terms"], ["/privacy", "Privacy"], ["/refund-policy", "Refund Policy"], ["/contact", "Contact"]];
type Page = { path: string; title: string; heading: string; description: string; sections: string[][] };

function metadata(template: string, page: Page) {
  const url = `https://whitepact.com${page.path}`;
  let html = template.replace(/<title>[^<]*<\/title>/, `<title>${escape(page.title)}</title>`);
  for (const [selector, value] of [['name="description"', page.description], ['property="og:title"', page.title], ['property="og:description"', page.description], ['property="og:url"', url], ['name="twitter:title"', page.title], ['name="twitter:description"', page.description]]) {
    html = html.replace(new RegExp(`<meta ${selector} content="[^"]*"\\s*/?>`), `<meta ${selector} content="${escape(value)}" />`);
  }
  return html.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${url}" />`);
}

/** Static editorial fallbacks and metadata. No remote fetching or request-time SSR. */
export function publicPages(): Plugin {
  let outDir: string;
  return {
    name: "whitepact-public-pages",
    apply: "build",
    configResolved(config) { outDir = resolve(config.root, config.build.outDir); },
    async closeBundle() {
      const template = await readFile(resolve(outDir, "index.html"), "utf8");
      await mkdir(resolve(outDir, "pages"), { recursive: true });
      const pages: Record<string, Page> = { ...commerce, ...information, ...corporate };
      const navigation = links.map(([href, label]) => `<a href="${href}">${label}</a>`).join(" ");
      for (const [key, page] of Object.entries(pages)) {
        let html = metadata(template, page);
        const prices = key === "pricing" || key === "home" ? `<div class="launch-pricing" aria-label="Evaluation options">${commerce.pricing.plans.map(plan => `<article><h3>${escape(plan.name)}</h3><p>${escape(plan.status)}</p><strong>${escape(plan.monthly)}</strong><p>${escape(plan.copy)}</p><a href="${escape(plan.href)}">${escape(plan.cta)}</a></article>`).join("")}</div>` : "";
        const fallback = `<noscript><header><a href="/">WhitePact</a><nav aria-label="Primary navigation">${navigation}</nav></header><main id="static-main" class="editorial-page"><h1>${escape(page.heading)}</h1><p class="page-lead">${escape(page.description)}</p>${page.sections.map(([title, copy]) => `<section><div><h2>${escape(title)}</h2><p>${escape(copy)}</p></div></section>`).join("")}${prices}<p><a href="/contact">Discuss an evaluation</a></p></main><footer><nav aria-label="Public footer">${navigation}</nav></footer></noscript>`;
        const chain = key === "home" || key === "architecture" ? `<section><h2>Conceptual control chain</h2><p>This map does not assert every adapter invokes every subsystem. Isolation depends on configured deployment.</p><ol>${controlChain.map(stage => `<li>${escape(stage)}</li>`).join("")}</ol></section>` : "";
        html = html.replace('<div id="root"></div>', `<div id="root"></div>${fallback.replace("</main>", `${chain}</main>`)}`);
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
        .replace('<div id="root"></div>', '<div id="root"></div><noscript><main><h1>Page not found</h1><p>The requested page does not exist.</p><a href="/">Return home</a></main></noscript>');
      await writeFile(resolve(outDir, "pages", "not-found.html"), notFound);
    },
  };
}
