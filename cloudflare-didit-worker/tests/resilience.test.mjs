/**
 * Neon txn atomicity, suspension, connection failure, rate limits,
 * timeout recovery, Didit retry budget, reconciliation — local simulation only.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { simulateDiditRetryBudget } from "../src/handler.js";
import {
  InMemoryIdentityStore,
  OutOfOrderError,
  RateLimitedError,
  StoreUnavailableError,
} from "../src/store.js";
import { payloadHashHex } from "../src/verify.js";
import { baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";

test("Neon txn atomicity: mid-commit abort rolls back event + leaves identity unchanged", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.abortCommitAfterEventInsert = true;
  const before = store.verifications.get(event.session_id).status;
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 503);
  assert.equal(store.events.has("event:" + event.event_id), false);
  assert.equal(store.verifications.get(event.session_id).status, before);
  assert.ok(store.txnLog.some((t) => t.rolledBack === true));
  // Recovery commit succeeds after abort flag cleared.
  store.abortCommitAfterEventInsert = false;
  const ok = await postWebhook({
    event: { ...event, timestamp: event.timestamp + 1 },
    store,
  });
  assert.equal(ok.status, 200);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
  assert.equal(
    store.verifications.get(event.session_id).provider_proofing_status,
    "PROVIDER_APPROVED",
  );
});

test("DB suspension (quota / Free CU exhausted) → 503, no ACK, deadletter after retries", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateSuspension(true);
  const budget = await simulateDiditRetryBudget(async (attempt) => {
    const res = await postWebhook({
      event: { ...event, timestamp: event.timestamp + attempt },
      store,
    });
    if (res.status === 503) {
      store.recordDeadletter({
        eventId: event.event_id,
        sessionId: event.session_id,
        reason: "suspended",
        payloadHash: payloadHashHex(event),
      });
    }
    return res;
  });
  assert.equal(budget.outcome, "exhausted");
  assert.equal(budget.attempts.length, 3);
  assert.ok(budget.attempts.every((a) => a.status === 503));
  assert.equal(store.events.has("event:" + event.event_id), false);
  assert.equal(store.committedAcks.length, 0);
  assert.ok(store.deadletters.length >= 3);
  // Unsuspend + signed retry succeeds (operator / next billing window).
  store.simulateSuspension(false);
  const recovered = await postWebhook({
    event: { ...event, timestamp: event.timestamp + 120 },
    store,
  });
  assert.equal(recovered.status, 200);
});

test("connection failure then recovery on Didit retry", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateUnavailable(1);
  const first = await postWebhook({ event, store });
  assert.equal(first.status, 503);
  assert.equal((await first.json()).reason, "connection_failure");
  const second = await postWebhook({
    event: { ...event, timestamp: event.timestamp + 60 },
    store,
  });
  assert.equal(second.status, 200);
});

test("connection timeout (Neon cold wake beyond Didit client timeout) → 503", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  // Didit docs: ~5s timeout; Neon cold wake can exceed → treat as unavailable.
  store.simulateConnectLatency(6_000);
  store.connectTimeoutMs = 5_000;
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 503);
  assert.equal((await res.json()).reason, "timeout");
  assert.equal(store.events.size, 0);
});

test("rate limit exhaustion → 503 retryable", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateRateLimit(0);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 503);
  assert.equal((await res.json()).error, "IDENTITY_STORE_RATE_LIMITED");
});

test("out-of-order created_at for same session fails closed", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  const first = baseEvent({
    session_id: sessionId,
    timestamp: ts,
    created_at: ts - 20,
    status: "In Review",
  });
  const firstRes = await postWebhook({ event: first, store });
  assert.equal(firstRes.status, 200, await firstRes.text());
  const older = baseEvent({
    session_id: sessionId,
    created_at: ts - 40,
    status: "Approved",
    timestamp: ts + 5,
  });
  const res = await postWebhook({ event: older, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_EVENT_OUT_OF_ORDER");
  // Must not elevate from out-of-order Approved.
  assert.notEqual(store.verifications.get(sessionId).status, "IDENTITY_VERIFIED");
});

test("newer in-order status update after review is admitted", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  const review = baseEvent({
    session_id: sessionId,
    timestamp: ts,
    created_at: ts - 30,
    status: "In Review",
  });
  assert.equal((await postWebhook({ event: review, store })).status, 200);
  const approved = baseEvent({
    session_id: sessionId,
    created_at: ts - 10,
    status: "Approved",
    timestamp: ts + 10,
  });
  const res = await postWebhook({ event: approved, store });
  assert.equal(res.status, 200, await res.text());
  assert.equal(store.verifications.get(sessionId).status, "REVIEW_REQUIRED");
  assert.equal(
    store.verifications.get(sessionId).provider_proofing_status,
    "PROVIDER_APPROVED",
  );
});

test("concurrent duplicate delivery: single winner under lock", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const results = await Promise.all([
    store.withLock(() =>
      Promise.resolve(store.commitIdentityEvent(event)),
    ),
    store.withLock(() =>
      Promise.resolve(store.commitIdentityEvent({ ...event, timestamp: event.timestamp + 1 })),
    ),
  ]);
  const winners = results.filter((r) => !r.duplicate);
  const dups = results.filter((r) => r.duplicate);
  assert.equal(winners.length, 1);
  assert.equal(dups.length, 1);
  assert.equal(
    [...store.events.keys()].filter((k) => k.startsWith("event:")).length,
    1,
  );
});

test("reconciliation is read-only and never elevates", async () => {
  const event = baseEvent({ status: "In Review" });
  const store = storeWithBinding(event.session_id);
  await postWebhook({ event, store });
  const snap = store.reconcileSession(event.session_id, {
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.elevates, false);
  assert.equal(snap.verification_status, "REVIEW_REQUIRED");
  // Cross-tenant reconcile denied.
  assert.throws(
    () => store.reconcileSession(event.session_id, { userId: "other", orgId: "org-1" }),
  );
});

test("Didit 4xx (non-404) is not retried by simulateDiditRetryBudget", async () => {
  const event = baseEvent({ vendor_data: "intruder" });
  const store = storeWithBinding(event.session_id);
  const budget = await simulateDiditRetryBudget(async () =>
    postWebhook({ event, store }),
  );
  assert.equal(budget.outcome, "no_retry");
  assert.equal(budget.attempts.length, 1);
  assert.equal(budget.attempts[0].status, 403);
});

test("RateLimitedError surfaces as retryable 503 from gate", () => {
  const store = new InMemoryIdentityStore({ rateLimitRemaining: 0 });
  assert.throws(() => store._gate(), RateLimitedError);
  store.simulateSuspension(true);
  assert.throws(() => store._gate(), StoreUnavailableError);
  store.simulateSuspension(false);
  store.simulateUnavailable(0);
  store.simulateConnectLatency(9999);
  assert.throws(() => store._gate(), /timed out|StoreUnavailable/);
});

test("OutOfOrderError code matches #244 PROVIDER_EVENT_OUT_OF_ORDER", () => {
  const err = new OutOfOrderError();
  assert.equal(err.code, "PROVIDER_EVENT_OUT_OF_ORDER");
  assert.equal(err.httpStatus, 403);
});
