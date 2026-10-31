/**
 * Cloudflare Workers entry (local package). Do not deploy without founder
 * architecture approval + every mandatory preflight gate.
 *
 * Reconciliation (Didit GET …/decision/) is exported for operator / Linux
 * runners. It never elevates identity; signed webhooks remain the authority.
 */

import { createWorker, handleDiditWebhook } from "./handler.js";
import { InMemoryIdentityStore } from "./store.js";
import {
  DiditClient,
  DiditClientError,
  validateDecision,
  createMockDiditFetch,
} from "./didit_client.js";
import {
  ReconcileEngine,
  InMemoryReconcileJobStore,
  createReconcileEngineFromEnv,
  RECONCILE_STATES,
  REQUIRED_ACTION,
} from "./reconcile.js";

export {
  createWorker,
  handleDiditWebhook,
  InMemoryIdentityStore,
  DiditClient,
  DiditClientError,
  validateDecision,
  createMockDiditFetch,
  ReconcileEngine,
  InMemoryReconcileJobStore,
  createReconcileEngineFromEnv,
  RECONCILE_STATES,
  REQUIRED_ACTION,
};

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
