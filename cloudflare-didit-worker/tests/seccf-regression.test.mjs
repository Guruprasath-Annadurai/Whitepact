/**
 * SEC-CF-001..006 regression suite (mandatory vectors).
 * Antigravity finding text was UNVERIFIED in Project store; IDs mapped from
 * qualification adversarial pack + CTO mandatory test list.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { parseJsonStrict } from "../src/parse.js";
import { ProofInvalidError, signEvent, verifyWebhook } from "../src/verify.js";
import { handleDiditWebhook, simulateDiditRetryBudget } from "../src/handler.js";
import {
  APP,
  SECRET,
  WORKFLOW,
  baseEvent,
  env,
  postWebhook,
  storeWithBinding,
} from "./helpers.mjs";

const PREV = "local-previous-secret";

test("SEC-CF-001 duplicate JSON keys rejected fail-closed", () => {
  assert.throws(
    () => parseJsonStrict(new TextEncoder().encode('{"a":1,"a":2,"timestamp":1}')),
    /duplicate/,
  );
});

test("SEC-CF-002 signature tampering denied", () => {
  const event = baseEvent();
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const bad = new TextEncoder().encode(
    new TextDecoder().decode(payload).replace("Approved", "Declined"),
  );
  assert.throws(
    () =>
      verifyWebhook({
        payload: bad,
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

test("SEC-CF-003 secret rotation accepts V2-Previous with previous secret", async () => {
  const event = baseEvent();
  const { payload, signature, timestamp } = signEvent(event, PREV);
  const store = storeWithBinding(event.session_id);
  const req = new Request("https://idv.example/webhooks/didit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Signature-V2": "0".repeat(64), // current secret does not match
      "X-Signature-V2-Previous": signature,
      "X-Timestamp": timestamp,
    },
    body: payload,
  });
  const res = await handleDiditWebhook(req, {
    store,
    env: { ...env(), WHITEPACT_DIDIT_WEBHOOK_SECRET_PREVIOUS: PREV },
  });
  assert.equal(res.status, 200, await res.text());
});

test("SEC-CF-003 rotation rejects when previous secret absent", async () => {
  const event = baseEvent();
  const { payload, signature, timestamp } = signEvent(event, PREV);
  const store = storeWithBinding(event.session_id);
  const req = new Request("https://idv.example/webhooks/didit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Signature-V2": signature,
      "X-Signature-V2-Previous": signature,
      "X-Timestamp": timestamp,
    },
    body: payload,
  });
  const res = await handleDiditWebhook(req, { store, env: env() });
  assert.equal(res.status, 403);
});

test("SEC-CF-004 tenant mismatch CROSS_TENANT", async () => {
  const event = baseEvent({ vendor_data: "intruder" });
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "CROSS_TENANT");
});

test("SEC-CF-005 replay mutated payload PROVIDER_REPLAY", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  assert.equal((await postWebhook({ event, store })).status, 200);
  const mutated = { ...event, status: "Declined", timestamp: event.timestamp + 2 };
  const res = await postWebhook({ event: mutated, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_REPLAY");
});

test("SEC-CF-006 durable-before-ACK + suspension 503 + 404 retryable in budget", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateSuspension(true);
  const budget = await simulateDiditRetryBudget(async (attempt) => {
    if (attempt === 2) {
      // Didit also retries 404
      return new Response("missing", { status: 404 });
    }
    return postWebhook({
      event: { ...event, timestamp: event.timestamp + attempt },
      store,
    });
  });
  assert.equal(budget.outcome, "exhausted");
  assert.ok(budget.attempts.some((a) => a.status === 503));
  assert.ok(budget.attempts.some((a) => a.status === 404));
});

test("SEC-CF-006 sensitive-data redaction on durable path", async () => {
  const event = baseEvent({
    decision: {
      id_verifications: [{ document_front: "data:image/png;base64,AAAA" }],
    },
  });
  const store = storeWithBinding(event.session_id);
  assert.equal((await postWebhook({ event, store })).status, 200);
  const row = store.events.get("event:" + event.event_id);
  assert.equal(JSON.stringify(row).includes("document_front"), false);
});

test("SEC-CF-006 terminal-state: provider-approved then declined rejects (no edge elevation)", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  const approved = baseEvent({
    session_id: sessionId,
    timestamp: ts,
    created_at: ts - 20,
    status: "Approved",
  });
  assert.equal((await postWebhook({ event: approved, store })).status, 200);
  // SEC-CF-007: edge stops at PROVIDER_APPROVED / REVIEW_REQUIRED.
  assert.equal(store.verifications.get(sessionId).status, "REVIEW_REQUIRED");
  assert.equal(
    store.verifications.get(sessionId).provider_proofing_status,
    "PROVIDER_APPROVED",
  );
  const declined = baseEvent({
    session_id: sessionId,
    timestamp: ts + 5,
    created_at: ts - 5,
    status: "Declined",
  });
  assert.equal((await postWebhook({ event: declined, store })).status, 200);
  assert.equal(store.verifications.get(sessionId).status, "REJECTED");
  assert.equal(
    store.verifications.get(sessionId).provider_proofing_status,
    "PROVIDER_REJECTED",
  );
});
