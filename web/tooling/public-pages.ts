// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Plugin } from "vite";
import pages from "../src/content/commerce.json" with { type: "json" };

const escape = (text: string) => text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]!);
const links = [["/pricing", "Pricing"], ["/terms", "Terms"], ["/privacy", "Privacy"], ["/refund-policy", "Refund Policy"], ["/contact", "Contact"]];

/** Build from the same content as React. No request-time SSR or remote fetches. */
export function publicPages(): Plugin {
  let outDir: string;
  return {
    name: "whitepact-public-commerce-pages",
    apply: "build",
    configResolved(config) { outDir = resolve(config.root, config.build.outDir); },
    async closeBundle() {
      const template = await readFile(resolve(outDir, "index.html"), "utf8");
      await mkdir(resolve(outDir, "pages"), { recursive: true });
      for (const [key, page] of Object.entries(pages)) {
        const url = `https://whitepact.com${page.path}`;
        let html = template.replace(/<title>[^<]*<\/title>/, `<title>${escape(page.title)}</title>`);
        for (const [selector, value] of [["name=\"description\"", page.description], ["property=\"og:title\"", page.title], ["property=\"og:description\"", page.description], ["property=\"og:url\"", url], ["name=\"twitter:title\"", page.title], ["name=\"twitter:description\"", page.description]]) {
          html = html.replace(new RegExp(`<meta ${selector} content="[^"]*"\\s*/?>`), `<meta ${selector} content="${escape(value)}" />`);
        }
        html = html.replace(/<link rel="canonical" href="[^"]*"\s*\/?>/, `<link rel="canonical" href="${url}" />`);
        const footer = `<footer class="subpage-footer"><nav aria-label="Public footer">${links.map(([href, label]) => `<a href="${href}">${label}</a>`).join(" ")}</nav></footer>`;
        const fallback = `<noscript><header class="subpage-nav"><a href="/">WhitePact</a></header><main class="editorial-page"><h1>${escape(page.heading)}</h1><p class="page-lead">${escape(page.description)}</p>${page.sections.map(([title, copy], i) => `<section><span>${i + 1}</span><div><h2>${escape(title)}</h2><p>${escape(copy)}</p></div></section>`).join("")}<p><a href="mailto:annaduraiguruprasath7@gmail.com">Contact WhitePact</a></p></main>${footer}</noscript>`;
        html = html.replace('<div id="root"></div>', `<div id="root"></div>${fallback}`);
        await writeFile(resolve(outDir, "pages", `${key}.html`), html);
      }
    },
  };
}
