/**
 * Disposable real PostgreSQL concurrency + txn rollback evidence.
 * Requires DATABASE_URL (default: local disposable cluster on :54329).
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
import { APP, SECRET, WORKFLOW, baseEvent, env } from "./helpers.mjs";

const DATABASE_URL =
  process.env.DATABASE_URL || "postgres://ubuntu@127.0.0.1:54329/m13_didit";
const __dir = dirname(fileURLToPath(import.meta.url));

let pool;
let store;

test("pg setup", async (t) => {
  pool = createPool(DATABASE_URL);
  try {
    await pool.query("SELECT 1");
  } catch (err) {
    t.skip("PostgreSQL not available: " + err.message);
    return;
  }
  for (const f of [
    "001_identity_events.sql",
    "002_reconciliation_jobs.sql",
    "003_authority_boundary.sql",
    "004_database_hardening.sql",
  ]) {
    await pool.query(readFileSync(join(__dir, "../schema", f), "utf8"));
  }
  await pool.query(
    "TRUNCATE identity_provider_events, identity_session_bindings, identity_verifications, identity_reconciliation_deadletters",
  );
  store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
});

test("PG concurrent webhook delivery: single durable winner", async (t) => {
  if (!store) return t.skip("no pg");
  const event = baseEvent();
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });

  const post = async (tsOffset) => {
    const e = { ...event, timestamp: event.timestamp + tsOffset };
    const { payload, signature, timestamp } = signEvent(e, SECRET);
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
  };

  const results = await Promise.all([post(0), post(1), post(2), post(3)]);
  const statuses = await Promise.all(results.map(async (r) => ({ status: r.status, body: await r.json() })));
  const oks = statuses.filter((s) => s.status === 200);
  assert.ok(oks.length >= 1);
  // Exactly one non-duplicate transition or already_processed mix; event ledger unique.
  const n = await store.countEvents("event:");
  // May include events from prior tests in suite if truncate failed — we truncated once.
  assert.equal(
    oks.filter((s) => s.body.duplicate === false).length,
    1,
    JSON.stringify(statuses),
  );
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
  const row = await store.getVerificationRow(event.session_id);
  assert.equal(row.provider_proofing_status, "PROVIDER_APPROVED");
  assert.ok(n >= 1);
});

test("PG txn rollback on mid-commit abort leaves no event / no elevation", async (t) => {
  if (!store) return t.skip("no pg");
  const event = baseEvent();
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await assert.rejects(
    () => store.commitIdentityEvent(event, { abortAfterInsert: true }),
  );
  const n = await pool.query(
    `SELECT count(*)::int AS n FROM identity_provider_events
     WHERE provider=$1 AND event_id=$2`,
    ["didit-sandbox", "event:" + event.event_id],
  );
  assert.equal(n.rows[0].n, 0);
  assert.equal(await store.getVerificationStatus(event.session_id), "REVIEW_REQUIRED");
});

test("PG out-of-order / terminal reject after provider-approved (no edge elevation)", async (t) => {
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
    created_at: ts - 30,
    status: "Approved",
  });
  const r1 = await store.commitIdentityEvent(approved);
  assert.equal(r1.identity_transition, false);
  assert.equal(r1.provider_proofing_status, "PROVIDER_APPROVED");
  const older = baseEvent({
    session_id: sessionId,
    timestamp: ts + 2,
    created_at: ts - 40,
    status: "Declined",
  });
  await assert.rejects(() => store.commitIdentityEvent(older), /OUT_OF_ORDER|OutOfOrder/);
  const declined = baseEvent({
    session_id: sessionId,
    timestamp: ts + 5,
    created_at: ts - 10,
    status: "Declined",
  });
  await store.commitIdentityEvent(declined);
  assert.equal(await store.getVerificationStatus(sessionId), "REJECTED");
});

test("PG suspension returns retryable StoreUnavailable", async (t) => {
  if (!store) return t.skip("no pg");
  store.simulateSuspension(true);
  const event = baseEvent();
  await assert.rejects(() => store.commitIdentityEvent(event), /suspended|UNAVAILABLE/i);
  store.simulateSuspension(false);
});

test("pg teardown", async () => {
  if (pool) await pool.end();
});
