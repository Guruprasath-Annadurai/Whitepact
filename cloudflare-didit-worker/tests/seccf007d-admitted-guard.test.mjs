/**
 * SEC-CF-007D — Edge must not demote / mutate admitted identity sovereign state.
 * Distinguishes: provider proofing evidence vs fail-closed access vs sovereign mutation.
 * Real PG 16 with distinct non-superuser edge/sovereign logins.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import {
  PROVIDER_PROOFING,
  SOVEREIGN_ADMISSION,
  SOVEREIGN_STATUS,
  assertExecutionAllowed,
  applyEdgeProviderOutcome,
} from "../src/authority_status.js";
import { PgIdentityStore } from "../src/pg_store.js";
import { checkExecutionOrDeny, sovereignAdmitPg } from "../src/sovereign.js";
import { baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";
import {
  ADMIN_URL,
  EDGE_URL,
  SOVEREIGN_URL,
  applyAllSchemas,
  assertSessionUser,
  createPool,
  truncateIdentityTables,
} from "./pg_roles.mjs";

let admin;
let edge;
let sovereign;
let ready = false;

test("007D setup: schemas + edge/sovereign logins", async (t) => {
  admin = createPool(ADMIN_URL);
  try {
    await admin.query("SELECT 1");
  } catch (err) {
    t.skip("PostgreSQL unavailable: " + err.message);
    return;
  }
  await applyAllSchemas(admin);
  await truncateIdentityTables(admin);
  edge = createPool(EDGE_URL);
  sovereign = createPool(SOVEREIGN_URL);
  await assertSessionUser(edge, "whitepact_edge_login");
  await assertSessionUser(sovereign, "whitepact_sovereign_login");
  ready = true;
});

async function seedAdmitted(sessionId = randomUUID()) {
  const store = new PgIdentityStore(edge, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await store.commitIdentityEvent(
    baseEvent({ session_id: sessionId, vendor_data: "user-1", status: "Approved" }),
  );
  const adm = await sovereignAdmitPg(sovereign, {
    provider: "didit-sandbox",
    sessionId,
    admit: true,
  });
  assert.equal(adm.status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  return { store, sessionId };
}

test("007D-1 pure: admitted + REJECTED keeps sovereign state; sets proofing hold", () => {
  const r = applyEdgeProviderOutcome({
    currentSovereignStatus: SOVEREIGN_STATUS.IDENTITY_VERIFIED,
    currentAdmission: SOVEREIGN_ADMISSION.ADMITTED,
    providerProofing: PROVIDER_PROOFING.REJECTED,
  });
  assert.equal(r.status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  assert.equal(r.sovereign_admission, SOVEREIGN_ADMISSION.ADMITTED);
  assert.equal(r.provider_proofing_status, PROVIDER_PROOFING.REJECTED);
  assert.equal(r.proofing_hold, true);
  assert.equal(r.elevates, false);
});

test("007D-2 pure: execution gate fails closed on PROVIDER_REJECTED hold", () => {
  assert.throws(
    () =>
      assertExecutionAllowed({
        status: SOVEREIGN_STATUS.IDENTITY_VERIFIED,
        sovereign_admission: SOVEREIGN_ADMISSION.ADMITTED,
        provider_proofing_status: PROVIDER_PROOFING.REJECTED,
      }),
    (e) => e.code === "PROVIDER_PROOFING_HOLD",
  );
});

test("007D-3 pure: execution allowed when admitted + PROVIDER_APPROVED", () => {
  assert.equal(
    assertExecutionAllowed({
      status: SOVEREIGN_STATUS.IDENTITY_VERIFIED,
      sovereign_admission: SOVEREIGN_ADMISSION.ADMITTED,
      provider_proofing_status: PROVIDER_PROOFING.APPROVED,
    }).execution_granted,
    true,
  );
});

test("007D-4 in-memory webhook: Declined after admit records proofing only", async () => {
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
  const { sovereignAdmitInMemory } = await import("../src/sovereign.js");
  sovereignAdmitInMemory(store, sessionId, { admit: true });
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
  assert.equal(v.status, SOVEREIGN_STATUS.IDENTITY_VERIFIED);
  assert.equal(v.sovereign_admission, SOVEREIGN_ADMISSION.ADMITTED);
  assert.equal(v.provider_proofing_status, PROVIDER_PROOFING.REJECTED);
  assert.equal(checkExecutionOrDeny(v).code, "PROVIDER_PROOFING_HOLD");
});

test("007D-5 PG: edge UPDATE demoting IDENTITY_VERIFIED → SUSPENDED denied", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await seedAdmitted();
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET status='SUSPENDED', sovereign_admission='REVOCATION_PENDING'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007D|42501/,
  );
  const row = await edge.query(
    `SELECT status, sovereign_admission, provider_proofing_status
       FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "IDENTITY_VERIFIED");
  assert.equal(row.rows[0].sovereign_admission, "ADMITTED");
});

test("007D-6 PG: edge UPDATE clearing ADMITTED denied", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await seedAdmitted();
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET sovereign_admission='DENIED'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007D|42501/,
  );
});

test("007D-7 PG: edge may update provider_proofing_status on admitted row", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await seedAdmitted();
  await edge.query(
    `UPDATE identity_verifications
        SET provider_proofing_status='PROVIDER_REJECTED', updated_at=now()
      WHERE provider_reference_id=$1`,
    [sessionId],
  );
  const row = await edge.query(
    `SELECT status, sovereign_admission, provider_proofing_status
       FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "IDENTITY_VERIFIED");
  assert.equal(row.rows[0].sovereign_admission, "ADMITTED");
  assert.equal(row.rows[0].provider_proofing_status, "PROVIDER_REJECTED");
  const denied = checkExecutionOrDeny(row.rows[0]);
  assert.equal(denied.execution_granted, false);
  assert.equal(denied.code, "PROVIDER_PROOFING_HOLD");
});

test("007D-8 PG: Declined webhook path after admit — proofing only, no demotion", async (t) => {
  if (!ready) return t.skip("no pg");
  const { store, sessionId } = await seedAdmitted();
  // Approved seed used baseEvent() created_at ≈ now-1; Declined must be newer.
  const ts = Math.floor(Date.now() / 1000) + 120;
  const r = await store.commitIdentityEvent(
    baseEvent({
      session_id: sessionId,
      vendor_data: "user-1",
      status: "Declined",
      created_at: ts,
      timestamp: ts + 1,
    }),
  );
  assert.equal(r.provider_proofing_status, "PROVIDER_REJECTED");
  assert.equal(r.elevates, false);
  const row = await store.getVerificationRow(sessionId);
  assert.equal(row.status, "IDENTITY_VERIFIED");
  assert.equal(row.sovereign_admission, "ADMITTED");
  assert.equal(row.provider_proofing_status, "PROVIDER_REJECTED");
  assert.equal(checkExecutionOrDeny(row).code, "PROVIDER_PROOFING_HOLD");
});

test("007D-9 PG: edge cannot rebind user_id/org_id on admitted row", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await seedAdmitted();
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET user_id='attacker', org_id='evil-org'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007D|42501|permission denied/i,
  );
});

test("007D-10 PG: sovereign_login MAY demote admitted identity", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await seedAdmitted();
  await sovereign.query(
    `UPDATE identity_verifications
        SET status='SUSPENDED', sovereign_admission='REVOCATION_PENDING', updated_at=now()
      WHERE provider_reference_id=$1`,
    [sessionId],
  );
  const row = await sovereign.query(
    `SELECT status, sovereign_admission FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "SUSPENDED");
  assert.equal(row.rows[0].sovereign_admission, "REVOCATION_PENDING");
});

test("007D-11 PG: pre-admit Declined still sets REJECTED/DENIED (edge authorized)", async (t) => {
  if (!ready) return t.skip("no pg");
  const store = new PgIdentityStore(edge, { provider: "didit-sandbox" });
  const sessionId = randomUUID();
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  await store.commitIdentityEvent(
    baseEvent({ session_id: sessionId, vendor_data: "user-1", status: "Declined" }),
  );
  const row = await store.getVerificationRow(sessionId);
  assert.equal(row.status, "REJECTED");
  assert.equal(row.sovereign_admission, "DENIED");
  assert.equal(row.provider_proofing_status, "PROVIDER_REJECTED");
});

test("007D teardown", async () => {
  if (edge) await edge.end();
  if (sovereign) await sovereign.end();
  if (admin) await admin.end();
});
