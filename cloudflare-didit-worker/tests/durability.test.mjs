import assert from "node:assert/strict";
import test from "node:test";
import { InMemoryIdentityStore } from "../src/store.js";
import { payloadHashHex } from "../src/verify.js";
import { baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";

test("ACK 200 only after durable commit; event ledger contains hash", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.ok, true);
  assert.equal(body.duplicate, false);
  assert.equal(body.identity_transition, true);
  assert.ok(store.committedAcks.includes("event:" + event.event_id));
  const row = store.events.get("event:" + event.event_id);
  assert.equal(row.payload_hash, payloadHashHex(event));
  assert.equal(store.verifications.get(event.session_id).status, "IDENTITY_VERIFIED");
});

test("identical retry is idempotent ALREADY_PROCESSED (still 200)", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const first = await postWebhook({ event, store });
  assert.equal(first.status, 200);
  // Didit refreshes timestamp on retry — digest excludes timestamp.
  const retry = { ...event, timestamp: event.timestamp + 5 };
  const second = await postWebhook({ event: retry, store });
  assert.equal(second.status, 200);
  const body = await second.json();
  assert.equal(body.duplicate, true);
  assert.equal(body.status, "ALREADY_PROCESSED");
  assert.equal(
    [...store.events.keys()].filter((k) => k.startsWith("event:")).length,
    1,
  );
});

test("same event_id with mutated body is PROVIDER_REPLAY (403)", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  assert.equal((await postWebhook({ event, store })).status, 200);
  const mutated = { ...event, status: "Declined", timestamp: event.timestamp + 2 };
  const res = await postWebhook({ event: mutated, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_REPLAY");
});

test("Neon unavailable before commit → 503, no success ACK, no ledger row", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateUnavailable(1);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 503);
  const body = await res.json();
  assert.equal(body.error, "IDENTITY_STORE_UNAVAILABLE");
  assert.equal(body.reconcile, true);
  assert.equal(store.events.has("event:" + event.event_id), false);
  assert.equal(store.committedAcks.length, 0);
  // Provider retry after store recovery succeeds.
  const retry = await postWebhook({ event: { ...event, timestamp: event.timestamp + 10 }, store });
  assert.equal(retry.status, 200);
  assert.ok(store.events.has("event:" + event.event_id));
});

test("never ACKs via waitUntil-style deferral: commit is synchronous in handler path", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  let committedBeforeResponse = false;
  const original = store.commitIdentityEvent.bind(store);
  store.commitIdentityEvent = (...args) => {
    const result = original(...args);
    committedBeforeResponse = store.events.has("event:" + event.event_id);
    return result;
  };
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 200);
  assert.equal(committedBeforeResponse, true);
});

test("quota/suspend simulation: repeated 503 until reconcile window", async () => {
  const event = baseEvent();
  const store = new InMemoryIdentityStore();
  store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  store.simulateUnavailable(3); // Didit: initial + 2 retries still fail
  for (let i = 0; i < 3; i++) {
    const res = await postWebhook({
      event: { ...event, timestamp: event.timestamp + i },
      store,
    });
    assert.equal(res.status, 503);
  }
  assert.equal(store.events.size, 0);
  // After monthly reset / operator restore:
  const recovered = await postWebhook({
    event: { ...event, timestamp: event.timestamp + 60 },
    store,
  });
  assert.equal(recovered.status, 200);
});
