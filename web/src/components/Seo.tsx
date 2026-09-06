// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { useEffect } from "react";

const origin = "https://whitepact.com";

export function Seo({ title, description, path = "/", noIndex = false }: { title: string; description: string; path?: string; noIndex?: boolean }) {
  useEffect(() => {
    document.title = title;
    const upsert = (selector: string, attr: string, value: string) => {
      let node = document.head.querySelector<HTMLElement>(selector);
      if (!node) {
        node = document.createElement(selector.startsWith("link") ? "link" : "meta");
        const identity = selector.match(/\[(name|property|rel)="([^"]+)"\]/);
        if (identity) node.setAttribute(identity[1], identity[2]);
        document.head.appendChild(node);
      }
      node.setAttribute(attr, value);
    };
    upsert('meta[name="description"]', "content", description);
    upsert('meta[property="og:title"]', "content", title);
    upsert('meta[property="og:description"]', "content", description);
    upsert('meta[property="og:url"]', "content", `${origin}${path}`);
    upsert('meta[name="twitter:title"]', "content", title);
    upsert('meta[name="twitter:description"]', "content", description);
    upsert('link[rel="canonical"]', "href", `${origin}${path}`);
    upsert('meta[name="robots"]', "content", noIndex ? "noindex, nofollow" : "index, follow");
  }, [description, noIndex, path, title]);
  return null;
}
