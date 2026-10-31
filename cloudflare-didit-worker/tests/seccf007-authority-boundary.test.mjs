/**
 * SEC-CF-007 — Premature Edge Identity Elevation repair.
 * CTO checklist items 1–14 + sovereign mock (Linux undeployed → E2E BLOCKED).
 * Real PG 16 when DATABASE_URL set.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import {
  AuthorityDeniedError,
  PROVIDER_PROOFING,
  SOVEREIGN_ADMISSION,
  SOVEREIGN_STATUS,
  assertExecutionAllowed,
} from "../src/authority_status.js";
import {
  checkExecutionOrDeny,
  recordAuthorityDenialPg,
  sovereignAdmitInMemory,
  sovereignAdmitPg,
} from "../src/sovereign.js";
import { createPool, PgIdentityStore } from "../src/pg_store.js";
import { baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";
import { SOVEREIGN_URL, applyAllSchemas, truncateIdentityTables } from "./pg_roles.mjs";

const DATABASE_URL =
  process.env.DATABASE_URL || "postgres://ubuntu@127.0.0.1:54329/m13_didit";

let pool;
let sovereignPool;
let pgReady = false;

test("SEC-CF-007 PG setup", async (t) => {
  pool = createPool(DATABASE_URL);
  try {
    await pool.query("SELECT 1");
  } catch (err) {
    t.skip("PostgreSQL unavailable: " + err.message);
    return;
  }
  await applyAllSchemas(pool);
  await truncateIdentityTables(pool);
  sovereignPool = createPool(SOVEREIGN_URL);
  pgReady = true;
});

// --- CTO 1–14 (in-memory + PG where noted) ---

test("CTO-1 Approved → PROVIDER_APPROVED not IDENTITY_VERIFIED", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({ event, store });
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.equal(body.provider_proofing_status, PROVIDER_PROOFING.APPROVED);
  assert.equal(body.status, PROVIDER_PROOFING.APPROVED);
  assert.notEqual(body.sovereign_status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
});

test("CTO-2 identity_transition always false on edge ACK", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const body = await (await postWebhook({ event, store })).json();
  assert.equal(body.identity_transition, false);
});

test("CTO-3 elevates always false on edge ACK", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const body = await (await postWebhook({ event, store })).json();
  assert.equal(body.elevates, false);
});

test("CTO-4 sovereign_admission_required true after Approved", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const body = await (await postWebhook({ event, store })).json();
  assert.equal(body.sovereign_admission_required, true);
  assert.equal(body.sovereign_admission, SOVEREIGN_ADMISSION.PENDING);
});

test("CTO-5 ACK only after durable txn (ledger present before 200 semantics)", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 200);
  assert.ok(store.events.has("event:" + event.event_id));
  assert.ok(store.committedAcks.includes("event:" + event.event_id));
});

test("CTO-6 PG: edge cannot UPDATE to IDENTITY_VERIFIED (trigger)", async (t) => {
  if (!pgReady) return t.skip("no pg");
  const sessionId = randomUUID();
  const store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await assert.rejects(
    () =>
      pool.query(
        `UPDATE identity_verifications
            SET status='IDENTITY_VERIFIED', sovereign_admission='ADMITTED'
          WHERE provider='didit-sandbox' AND provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007|42501|permission/i,
  );
  assert.equal(await store.getVerificationStatus(sessionId), "REVIEW_REQUIRED");
});

test("CTO-7 Declined never becomes approval / no silent reopen", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  assert.equal(
    (
      await postWebhook({
        event: baseEvent({
          session_id: sessionId,
          status: "Declined",
          created_at: ts - 20,
          timestamp: ts,
        }),
        store,
      })
    ).status,
    200,
  );
  assert.equal(store.verifications.get(sessionId).status, "REJECTED");
  assert.equal(
    (
      await postWebhook({
        event: baseEvent({
          session_id: sessionId,
          status: "Approved",
          created_at: ts - 10,
          timestamp: ts + 5,
        }),
        store,
      })
    ).status,
    200,
  );
  // Reopen blocked: stays REJECTED despite later Approved evidence.
  assert.equal(store.verifications.get(sessionId).status, "REJECTED");
  assert.equal(
    store.verifications.get(sessionId).provider_proofing_status,
    PROVIDER_PROOFING.APPROVED,
  );
});

test("CTO-8 REJECTED stays fail-closed for execution", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  await postWebhook({
    event: baseEvent({ session_id: sessionId, status: "Declined" }),
    store,
  });
  const denied = checkExecutionOrDeny(store.verifications.get(sessionId));
  assert.equal(denied.execution_granted, false);
  assert.equal(denied.denied, true);
});

test("CTO-9 Sovereign-admitted then Declined → SUSPENDED / revocation pending", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  await postWebhook({
    event: baseEvent({
      session_id: sessionId,
      status: "Approved",
      created_at: ts - 20,
      timestamp: ts,
    }),
    store,
  });
  const adm = sovereignAdmitInMemory(store, sessionId, { admit: true });
  assert.equal(adm.status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  assert.equal(adm.identity_transition, true);
  await postWebhook({
    event: baseEvent({
      session_id: sessionId,
      status: "Declined",
      created_at: ts - 5,
      timestamp: ts + 10,
    }),
    store,
  });
  const v = store.verifications.get(sessionId);
  assert.equal(v.status, SOVEREIGN_STATUS.SUSPENDED);
  assert.equal(v.sovereign_admission, SOVEREIGN_ADMISSION.REVOCATION_PENDING);
  assert.equal(checkExecutionOrDeny(v).execution_granted, false);
});

test("CTO-10 cross-tenant Approved still CROSS_TENANT", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId, "user-A", "org-A");
  const res = await postWebhook({
    event: baseEvent({ session_id: sessionId, vendor_data: "user-B", status: "Approved" }),
    store,
  });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "CROSS_TENANT");
  assert.equal(store.verifications.get(sessionId).status, "REVIEW_REQUIRED");
});

test("CTO-11 replay mutated payload still PROVIDER_REPLAY", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  assert.equal((await postWebhook({ event, store })).status, 200);
  const mutated = { ...event, status: "Declined", timestamp: event.timestamp + 3 };
  const res = await postWebhook({ event: mutated, store });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_REPLAY");
});

test("CTO-12 OOO still PROVIDER_EVENT_OUT_OF_ORDER", async () => {
  const sessionId = randomUUID();
  const store = storeWithBinding(sessionId);
  const ts = Math.floor(Date.now() / 1000);
  await postWebhook({
    event: baseEvent({
      session_id: sessionId,
      status: "In Review",
      created_at: ts - 10,
      timestamp: ts,
    }),
    store,
  });
  const res = await postWebhook({
    event: baseEvent({
      session_id: sessionId,
      status: "Approved",
      created_at: ts - 40,
      timestamp: ts + 5,
    }),
    store,
  });
  assert.equal(res.status, 403);
  assert.equal((await res.json()).error, "PROVIDER_EVENT_OUT_OF_ORDER");
});

test("CTO-13 authority offline / pending → execution denied + denial event (PG)", async (t) => {
  if (!pgReady) return t.skip("no pg");
  const sessionId = randomUUID();
  const store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  const event = baseEvent({ session_id: sessionId, status: "Approved" });
  const r = await store.commitIdentityEvent(event);
  assert.equal(r.provider_proofing_status, "PROVIDER_APPROVED");
  const row = await store.getVerificationRow(sessionId);
  const denied = checkExecutionOrDeny(row);
  assert.equal(denied.execution_granted, false);
  assert.equal(denied.authority_offline_or_pending, true);
  await recordAuthorityDenialPg(pool, {
    provider: "didit-sandbox",
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    reasonCode: denied.code,
  });
  const n = await pool.query(
    `SELECT count(*)::int AS n FROM identity_authority_denials WHERE session_id=$1`,
    [sessionId],
  );
  assert.equal(n.rows[0].n, 1);
});

test("CTO-14 mock sovereign admit then execution allowed; edge still cannot elevate", async (t) => {
  if (!pgReady) return t.skip("no pg");
  const sessionId = randomUUID();
  const store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await store.commitIdentityEvent(
    baseEvent({ session_id: sessionId, status: "Approved" }),
  );
  // 007C: admit must use distinct sovereign_login pool (not superuser GUC).
  const adm = await sovereignAdmitPg(sovereignPool, {
    provider: "didit-sandbox",
    sessionId,
    admit: true,
  });
  assert.equal(adm.status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  assert.equal(adm.elevates, true);
  const row = await store.getVerificationRow(sessionId);
  assert.equal(assertExecutionAllowed(row).execution_granted, true);
  // Edge path still returns elevates:false for a new Approved on another session.
  const other = randomUUID();
  await store.bindSession({
    sessionId: other,
    userId: "user-2",
    orgId: "org-1",
    contextHash: "ctx2",
  });
  const edge = await store.commitIdentityEvent(
    baseEvent({ session_id: other, vendor_data: "user-2", status: "Approved" }),
  );
  assert.equal(edge.elevates, false);
  assert.equal(edge.identity_transition, false);
});

test("SEC-CF-007: Expired / Abandoned → PROVIDER_REJECTED fail-closed", async () => {
  for (const status of ["Expired", "Abandoned"]) {
    const event = baseEvent({ status });
    const store = storeWithBinding(event.session_id);
    const body = await (await postWebhook({ event, store })).json();
    assert.equal(body.provider_proofing_status, PROVIDER_PROOFING.REJECTED);
    assert.equal(store.verifications.get(event.session_id).status, "REJECTED");
    assert.equal(body.execution_granted, false);
  }
});

test("SEC-CF-007: sovereign deny without PROVIDER_APPROVED fails", () => {
  const store = storeWithBinding(randomUUID());
  const sid = [...store.bindings.keys()][0];
  assert.throws(
    () => sovereignAdmitInMemory(store, sid, { admit: true }),
    (e) => e instanceof AuthorityDeniedError && e.code === "PROVIDER_EVIDENCE_REQUIRED",
  );
});

test("SEC-CF-007 PG teardown", async () => {
  if (sovereignPool) await sovereignPool.end();
  if (pool) await pool.end();
});
