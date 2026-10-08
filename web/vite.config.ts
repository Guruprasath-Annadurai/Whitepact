// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { originMetadata, publicPages } from "./tooling/public-pages.ts";
import { loadEnv } from "vite";
import { siteContract, validatePublicBuildConfig } from "./src/content/site-origin.ts";

const stripGeneratedTrailingWhitespace = {
  name: "whitepact-strip-generated-trailing-whitespace",
  generateBundle(_options: unknown, bundle: Record<string, { type: string; code?: string }>) {
    for (const output of Object.values(bundle)) {
      if (output.type === "chunk" && output.code) {
        output.code = output.code
          .replace(/[ \t]+$/gm, "")
          .replace(/^ +(?=\t)/gm, "");
      }
    }
  },
};

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  validatePublicBuildConfig(env);
  const site = siteContract(env.VITE_WHITEPACT_SITE_ORIGIN, env.VITE_WHITEPACT_SITE_PROFILE ?? (mode === "development" ? "development" : "production"));
  return {
  base: "/static/whitepact/",
  plugins: [react(), originMetadata(site), stripGeneratedTrailingWhitespace, publicPages(site)],
  define: { "import.meta.env.VITE_WHITEPACT_SITE_ORIGIN": JSON.stringify(site.origin), "import.meta.env.VITE_WHITEPACT_SITE_PROFILE": JSON.stringify(site.profile) },
  build: {
    outDir: "../src/responsibleai/dashboard/static/whitepact",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 4173,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    restoreMocks: true,
  },
  };
});
