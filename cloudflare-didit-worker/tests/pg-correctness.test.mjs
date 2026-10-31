/**
 * Workstream B — extended real PostgreSQL correctness.
 * Requires DATABASE_URL disposable PG (not in-memory).
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { createPool, PgIdentityStore } from "../src/pg_store.js";
import { handleDiditWebhook } from "../src/handler.js";
import { signEvent } from "../src/verify.js";
import { APP, SECRET, baseEvent, env } from "./helpers.mjs";

const DATABASE_URL =
  process.env.DATABASE_URL || "postgres://ubuntu@127.0.0.1:54329/m13_didit";
const __dir = dirname(fileURLToPath(import.meta.url));

let pool;
let store;

async function post(store, event) {
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const req = new Request("https://idv.example/webhooks/didit", {
    method: "POST",
    headers: {
      "content-type": "application/json",
      "X-Signature-V2": signature,
      "X-Timestamp": timestamp,
    },
    body: payload,
  });
  return handleDiditWebhook(req, { store, env: env() });
}

test("pg-correctness setup", async (t) => {
  pool = createPool(DATABASE_URL);
  try {
    await pool.query("SELECT 1");
  } catch (err) {
    t.skip("PostgreSQL unavailable: " + err.message);
    return;
  }
  for (const f of [
    "001_identity_events.sql",
    "002_reconciliation_jobs.sql",
    "003_authority_boundary.sql",
  ]) {
    await pool.query(readFileSync(join(__dir, "../schema", f), "utf8"));
  }
  await pool.query(
    "TRUNCATE identity_provider_events, identity_session_bindings, identity_verifications, identity_reconciliation_deadletters",
  );
  store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
});

test("first-event race: concurrent Approved with same created_at → one provider-proof, others OOO", async (t) => {
  if (!store) return t.skip("no pg");
  const sessionId = randomUUID();
  const ts = Math.floor(Date.now() / 1000);
  const created = ts - 10;
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  // Same created_at: first FOR UPDATE winner admits evidence; others fail out-of-order.
  const mk = (i) =>
    baseEvent({
      session_id: sessionId,
      event_id: randomUUID(),
      timestamp: ts + i,
      created_at: created,
      status: "Approved",
    });
  const events = [mk(0), mk(1), mk(2)];
  const results = await Promise.all(events.map((e) => post(store, e)));
  const bodies = await Promise.all(
    results.map(async (r) => ({ status: r.status, body: await r.json() })),
  );
  const proofs = bodies.filter(
    (b) =>
      b.status === 200 &&
      b.body.duplicate === false &&
      b.body.provider_proofing_status === "PROVIDER_APPROVED",
  );
  const ooo = bodies.filter((b) => b.body?.error === "PROVIDER_EVENT_OUT_OF_ORDER");
  assert.equal(proofs.length, 1, JSON.stringify(bodies));
  assert.equal(ooo.length, 2, JSON.stringify(bodies));
  assert.ok(proofs.every((p) => p.body.identity_transition === false));
  assert.equal(await store.getVerificationStatus(sessionId), "REVIEW_REQUIRED");
  const row = await store.getVerificationRow(sessionId);
  assert.equal(row.provider_proofing_status, "PROVIDER_APPROVED");
});

test("conflicting statuses in-order: Approved then Declined → REJECTED (no prior sovereign); both durable", async (t) => {
  if (!store) return t.skip("no pg");
  const sessionId = randomUUID();
  const ts = Math.floor(Date.now() / 1000);
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  const approved = baseEvent({
    session_id: sessionId,
    timestamp: ts,
    created_at: ts - 20,
    status: "Approved",
  });
  const declined = baseEvent({
    session_id: sessionId,
    timestamp: ts + 1,
    created_at: ts - 15,
    status: "Declined",
  });
  assert.equal((await post(store, approved)).status, 200);
  assert.equal((await post(store, declined)).status, 200);
  assert.equal(await store.getVerificationStatus(sessionId), "REJECTED");
  const n = await pool.query(
    `SELECT count(*)::int AS n FROM identity_provider_events
     WHERE provider=$1 AND session_id=$2 AND event_id LIKE 'event:%'`,
    ["didit-sandbox", sessionId],
  );
  assert.equal(n.rows[0].n, 2);
});

test("conflicting race: Declined-before-Approved (older) → older rejected OOO fail-closed", async (t) => {
  if (!store) return t.skip("no pg");
  const sessionId = randomUUID();
  const ts = Math.floor(Date.now() / 1000);
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  const declined = baseEvent({
    session_id: sessionId,
    timestamp: ts,
    created_at: ts - 10,
    status: "Declined",
  });
  assert.equal((await post(store, declined)).status, 200);
  const approvedOlder = baseEvent({
    session_id: sessionId,
    timestamp: ts + 2,
    created_at: ts - 30,
    status: "Approved",
  });
  const res = await post(store, approvedOlder);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_EVENT_OUT_OF_ORDER");
  // Must not silently elevate from out-of-order Approved
  assert.notEqual(await store.getVerificationStatus(sessionId), "IDENTITY_VERIFIED");
});

test("crash after commit before ACK: retry is ALREADY_PROCESSED — no double elevation", async (t) => {
  if (!store) return t.skip("no pg");
  const event = baseEvent();
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  // Simulate: durable commit succeeded but HTTP ACK never left the process.
  const committed = await store.commitIdentityEvent(event);
  assert.equal(committed.identity_transition, false);
  assert.equal(committed.provider_proofing_status, "PROVIDER_APPROVED");
  // Provider retry with refreshed timestamp
  const retry = { ...event, timestamp: event.timestamp + 30 };
  const res = await post(store, retry);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.duplicate, true);
  assert.equal(body.identity_transition, false);
  assert.equal(body.status, "ALREADY_PROCESSED");
  const n = await pool.query(
    `SELECT count(*)::int AS n FROM identity_provider_events
     WHERE provider=$1 AND event_id=$2`,
    ["didit-sandbox", "event:" + event.event_id],
  );
  assert.equal(n.rows[0].n, 1);
});

test("uncertain txn (abort): no identity authority; later retry can succeed", async (t) => {
  if (!store) return t.skip("no pg");
  const event = baseEvent();
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await assert.rejects(() =>
    store.commitIdentityEvent(event, { abortAfterInsert: true }),
  );
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
  // Retry after recovery
  const ok = await store.commitIdentityEvent({
    ...event,
    timestamp: event.timestamp + 5,
  });
  assert.equal(ok.identity_transition, false);
  assert.equal(ok.provider_proofing_status, "PROVIDER_APPROVED");
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
});

test("cross-tenant isolation: other org/user cannot bind or elevate", async (t) => {
  if (!store) return t.skip("no pg");
  const sessionId = randomUUID();
  await store.bindSession({
    sessionId,
    userId: "user-A",
    orgId: "org-A",
    contextHash: "ctx-A",
  });
  const event = baseEvent({
    session_id: sessionId,
    vendor_data: "user-B",
    status: "Approved",
  });
  const res = await post(store, event);
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "CROSS_TENANT");
  assert.equal(await store.getVerificationStatus(sessionId), "REVIEW_REQUIRED");
});

test("provider retries / missed events cannot silently grant identity without durable commit", async (t) => {
  if (!store) return t.skip("no pg");
  const event = baseEvent();
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  store.simulateSuspension(true);
  const res = await post(store, event);
  assert.equal(res.status, 503);
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
  // Even if attacker replays unsigned — handler still requires V2
  store.simulateSuspension(false);
  const unsigned = await handleDiditWebhook(
    new Request("https://idv.example/webhooks/didit", {
      method: "POST",
      headers: { "X-Timestamp": String(event.timestamp) },
      body: JSON.stringify(event),
    }),
    { store, env: env() },
  );
  assert.equal(unsigned.status, 403);
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
});

test("pg-correctness teardown", async () => {
  if (pool) await pool.end();
});
