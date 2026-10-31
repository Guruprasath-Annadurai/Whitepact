import { randomUUID } from "node:crypto";
import { signEvent } from "../src/verify.js";
import { InMemoryIdentityStore } from "../src/store.js";
import { handleDiditWebhook } from "../src/handler.js";

export const SECRET = "local-contract-secret";
export const APP = "app-11111111-1111-4111-8111-111111111111";
export const WORKFLOW = "wf-11111111-1111-4111-8111-111111111111";

export function baseEvent(changes = {}) {
  const now = Math.floor(Date.now() / 1000);
  return {
    event_id: randomUUID(),
    webhook_type: "status.updated",
    timestamp: now,
    created_at: now - 1,
    application_id: APP,
    environment: "sandbox",
    workflow_id: WORKFLOW,
    session_id: randomUUID(),
    vendor_data: "user-1",
    status: "Approved",
    ...changes,
  };
}

export function env() {
  return {
    WHITEPACT_DIDIT_WEBHOOK_SECRET: SECRET,
    WHITEPACT_DIDIT_WORKFLOW_ID: WORKFLOW,
    WHITEPACT_DIDIT_APPLICATION_ID: APP,
    WHITEPACT_DIDIT_ENVIRONMENT: "sandbox",
  };
}

export function storeWithBinding(sessionId, userId = "user-1", orgId = "org-1") {
  const store = new InMemoryIdentityStore({ provider: "didit-sandbox" });
  store.bindSession({
    sessionId,
    userId,
    orgId,
    contextHash: "ctx",
  });
  return store;
}

export async function postWebhook({ event, store, headers = {}, envOverrides = {}, now }) {
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const req = new Request("https://idv.example/webhooks/didit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Signature-V2": signature,
      "X-Timestamp": timestamp,
      ...headers,
    },
    body: payload,
  });
  return handleDiditWebhook(req, {
    store,
    env: { ...env(), ...envOverrides },
    now,
  });
}
