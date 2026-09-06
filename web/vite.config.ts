// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

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

export default defineConfig({
  base: "/static/whitepact/",
  plugins: [react(), stripGeneratedTrailingWhitespace],
  build: {
    outDir: "../src/responsibleai/dashboard/static/whitepact",
    emptyOutDir: true,
    sourcemap: false,
  },
  server: {
    port: 4173,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
