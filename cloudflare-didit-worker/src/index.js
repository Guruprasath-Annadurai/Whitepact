/**
 * Cloudflare Workers entry (local package). Do not deploy without founder
 * architecture approval + every mandatory preflight gate.
 */

import { createWorker, handleDiditWebhook } from "./handler.js";
import { InMemoryIdentityStore } from "./store.js";

export { createWorker, handleDiditWebhook, InMemoryIdentityStore };

// Default export for wrangler `main` once founder authorizes deploy.
export default {
  async fetch() {
    return new Response(
      JSON.stringify({
        error: "NOT_PROVISIONED",
        message: "Live Cloudflare Worker deploy is unauthorized until founder preflight PASS.",
      }),
      { status: 503, headers: { "content-type": "application/json" } },
    );
  },
};
