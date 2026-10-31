import assert from "node:assert/strict";
import test from "node:test";
import { parseJsonStrict } from "../src/parse.js";
import { ProofInvalidError, signEvent, verifyWebhook } from "../src/verify.js";
import {
  APP,
  SECRET,
  WORKFLOW,
  baseEvent,
  env,
  postWebhook,
  storeWithBinding,
} from "./helpers.mjs";

function verify(event, overrides = {}) {
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  return verifyWebhook({
    payload: overrides.payload ?? payload,
    signature: overrides.signature ?? signature,
    timestamp: overrides.timestamp ?? timestamp,
    webhookSecret: SECRET,
    applicationId: APP,
    environment: "sandbox",
    workflowId: WORKFLOW,
    now: overrides.now,
    testDelivery: overrides.testDelivery,
  });
}

test("accepts valid V2 signed event with Unicode name in body", () => {
  const event = baseEvent({ metadata: { name: "José" } });
  const data = verify(event);
  assert.equal(data.event_id, event.event_id);
});

test("rejects payload mutation under same signature", () => {
  const event = baseEvent();
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const tampered = new TextEncoder().encode(
    new TextDecoder().decode(payload).replace("Approved", "Declined"),
  );
  assert.throws(
    () =>
      verifyWebhook({
        payload: tampered,
        signature,
        timestamp,
        webhookSecret: SECRET,
        applicationId: APP,
        environment: "sandbox",
        workflowId: WORKFLOW,
      }),
    ProofInvalidError,
  );
});

test("rejects timestamp header mismatch vs body timestamp", () => {
  const event = baseEvent();
  assert.throws(() => verify(event, { timestamp: String(event.timestamp + 1) }), ProofInvalidError);
});

test("rejects stale timestamp outside 300s window", () => {
  const event = baseEvent({ timestamp: 1_700_000_000, created_at: 1_699_999_999 });
  assert.throws(
    () => verify(event, { now: () => 1_700_000_000 + 301 }),
    ProofInvalidError,
  );
});

test("rejects wrong application / environment / workflow", () => {
  for (const change of [
    { application_id: "other" },
    { environment: "live" },
    { workflow_id: "other" },
  ]) {
    assert.throws(() => verify(baseEvent(change)), ProofInvalidError);
  }
});

test("rejects unsupported webhook_type and empty event_id", () => {
  assert.throws(() => verify(baseEvent({ webhook_type: "auth.login" })), ProofInvalidError);
  assert.throws(() => verify(baseEvent({ event_id: "" })), ProofInvalidError);
});

test("rejects duplicate JSON keys (fail closed)", () => {
  const raw = '{"a":1,"a":2,"timestamp":1}';
  assert.throws(() => parseJsonStrict(new TextEncoder().encode(raw)), /duplicate/);
});

test("rejects X-Signature-Simple as sole authority at HTTP edge", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const { payload, timestamp } = signEvent(event, SECRET);
  const req = new Request("https://idv.example/webhooks/didit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Signature-Simple": "ab".repeat(32),
      "X-Timestamp": timestamp,
    },
    body: payload,
  });
  const { handleDiditWebhook } = await import("../src/handler.js");
  const res = await handleDiditWebhook(req, { store, env: env() });
  assert.equal(res.status, 403);
  const body = await res.json();
  assert.equal(body.error, "DIDIT_PROOF_INVALID");
});

test("cross-tenant vendor_data mismatch is denied after proof", async () => {
  const event = baseEvent({ vendor_data: "intruder" });
  const store = storeWithBinding(event.session_id, "user-1", "org-1");
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "CROSS_TENANT");
});

test("unknown session fails closed", async () => {
  const event = baseEvent();
  const store = storeWithBinding("00000000-0000-4000-8000-000000000099");
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "VERIFICATION_SESSION_UNKNOWN");
});

test("production env rejects sandbox enrollment", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({
    event,
    store,
    envOverrides: { WHITEPACT_RUNTIME_MODE: "production" },
  });
  assert.equal(res.status, 403);
});
