// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export const productionOrigin = "https://whitepact.com";
export type SiteProfile = "production" | "staging" | "development" | "test";
export function validatePublicBuildConfig(env: Record<string, string>) {
  const allowed = new Set(["VITE_WHITEPACT_SITE_ORIGIN", "VITE_WHITEPACT_SITE_PROFILE", "VITE_WHITEPACT_PADDLE_ENV", "VITE_WHITEPACT_PADDLE_CLIENT_TOKEN"]);
  for (const [key, value] of Object.entries(env)) {
    if (key.startsWith("VITE_") && !allowed.has(key)) throw new Error("Unreviewed public build variable; website config allowlist required");
    if (key.startsWith("VITE_") && /pdl_(live|sdbx)_apikey_|sk_live_|BEGIN .*PRIVATE KEY/.test(value)) throw new Error("Server credential cannot be exposed through public build config");
  }
}

/** Public metadata only. This is not the authenticated API/server origin. */
export function siteContract(origin = productionOrigin, profile: string = "production") {
  if (!["production", "staging", "development", "test"].includes(profile)) throw new Error("Invalid website profile");
  let url: URL;
  try { url = new URL(origin); } catch { throw new Error("Malformed website origin"); }
  if (url.username || url.password || url.pathname !== "/" || url.search || url.hash) throw new Error("Website origin must be an origin, not a URL path or credential");
  if (!["http:", "https:"].includes(url.protocol)) throw new Error("Invalid website origin protocol");
  if (profile === "production" && url.origin !== productionOrigin) throw new Error("Production metadata origin must be the canonical WhitePact origin");
  if (profile === "staging" && (url.protocol !== "https:" || url.hostname === "localhost" || !url.hostname.includes(".") || /(^[\d.]+$|:|\.(local|internal|test|invalid)$)/i.test(url.hostname))) throw new Error("Staging requires a public HTTPS hostname");
  return { origin: url.origin, profile: profile as SiteProfile, noIndex: profile !== "production" };
}
