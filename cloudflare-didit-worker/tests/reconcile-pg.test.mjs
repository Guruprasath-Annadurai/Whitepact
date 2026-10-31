/**
 * Disposable PostgreSQL — reconciliation job durability only.
 * Uses DATABASE_URL. Never talks to real Didit.
 * Run under --test-concurrency=1 when sharing PG with other suite files.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";
import { DiditClient, createMockDiditFetch } from "../src/didit_client.js";
import { RECONCILE_STATES, ReconcileEngine } from "../src/reconcile.js";
import { createPool, PgIdentityStore } from "../src/pg_store.js";
import { APP, WORKFLOW } from "./helpers.mjs";

const DATABASE_URL =
  process.env.DATABASE_URL || "postgres://ubuntu@127.0.0.1:54329/m13_didit";
const __dir = dirname(fileURLToPath(import.meta.url));

let pool;
let ready = false;

function approvedDecision(sessionId) {
  return {
    session_id: sessionId,
    status: "Approved",
    workflow_id: WORKFLOW,
    application_id: APP,
    environment: "sandbox",
    vendor_data: "user-1",
    id_verifications: [{ status: "Approved" }],
    liveness_checks: [{ status: "Approved" }],
    face_matches: [{ status: "Approved" }],
  };
}

test("reconcile-pg setup", async (t) => {
  pool = createPool(DATABASE_URL);
  try {
    await pool.query("SELECT 1");
  } catch (err) {
    t.skip("PostgreSQL unavailable: " + err.message);
    return;
  }
  const schema1 = readFileSync(join(__dir, "../schema/001_identity_events.sql"), "utf8");
  const schema2 = readFileSync(join(__dir, "../schema/002_reconciliation_jobs.sql"), "utf8");
  await pool.query(schema1);
  await pool.query(schema2);
  await pool.query(
    `TRUNCATE identity_reconciliation_jobs, identity_webhook_delivery_ops,
              identity_reconciliation_deadletters, identity_provider_events,
              identity_verifications, identity_session_bindings`,
  );
  ready = true;
});

test("PG: reconcile job CHECK forbids elevates/identity_transition true", async (t) => {
  if (!ready) return t.skip("no pg");
  await assert.rejects(
    () =>
      pool.query(
        `INSERT INTO identity_reconciliation_jobs
           (id, provider, session_id, user_id, org_id, reason, state, identity_transition, elevates)
         VALUES ($1,'didit-sandbox',$2,'u','o','t','applied', TRUE, FALSE)`,
        [randomUUID(), randomUUID()],
      ),
    /identity_reconciliation_jobs_no_elevate|check constraint/i,
  );
});

test("PG: bind + reconcile observation persists non-elevating job; verification unchanged", async (t) => {
  if (!ready) return t.skip("no pg");
  const sessionId = randomUUID();
  const store = new PgIdentityStore(pool, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });

  const fetchImpl = createMockDiditFetch({
    [`GET https://verification.didit.me/v3/session/${sessionId}/decision/`]: () => ({
      body: approvedDecision(sessionId),
    }),
  });

  const facade = {
    provider: "didit-sandbox",
    bindings: new Map([
      [sessionId, { user_id: "user-1", org_id: "org-1", context_hash: "ctx" }],
    ]),
    verifications: new Map([
      [sessionId, { status: "REVIEW_REQUIRED", user_id: "user-1", org_id: "org-1" }],
    ]),
    deadletters: [],
    events: new Map(),
    reconcileSession(sid, { userId, orgId }) {
      const b = this.bindings.get(sid);
      if (!b || b.user_id !== userId || b.org_id !== orgId) {
        const err = new Error("CROSS_TENANT");
        err.code = "CROSS_TENANT";
        throw err;
      }
      return {
        session_id: sid,
        elevates: false,
        verification_status: this.verifications.get(sid).status,
      };
    },
    _gate() {},
  };

  const engine = new ReconcileEngine({
    identityStore: facade,
    client: new DiditClient({
      apiKey: "k",
      applicationId: APP,
      workflowId: WORKFLOW,
      environment: "sandbox",
      fetchImpl,
    }),
    enrollment: { applicationId: APP, workflowId: WORKFLOW, environment: "sandbox" },
  });

  const snap = await engine.reconcileSession({
    sessionId,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.APPLIED);
  assert.equal(snap.elevates, false);
  assert.equal(snap.identity_transition, false);
  assert.equal(snap.recovery_complete, false);

  await pool.query(
    `INSERT INTO identity_reconciliation_jobs
       (id, provider, session_id, user_id, org_id, reason, state,
        provider_status, decision_hash, workflow_id, application_id, environment)
     VALUES ($1,'didit-sandbox',$2,'user-1','org-1','missed',$3,$4,$5,$6,$7,$8)`,
    [
      snap.job_id,
      sessionId,
      RECONCILE_STATES.APPLIED,
      snap.provider_status,
      snap.decision_hash,
      WORKFLOW,
      APP,
      "sandbox",
    ],
  );

  const row = (
    await pool.query(
      `SELECT elevates, identity_transition, state, provider_status
         FROM identity_reconciliation_jobs WHERE id=$1`,
      [snap.job_id],
    )
  ).rows[0];
  assert.equal(row.elevates, false);
  assert.equal(row.identity_transition, false);
  assert.equal(row.state, "applied");
  assert.equal(row.provider_status, "Approved");

  const v = (
    await pool.query(
      `SELECT status FROM identity_verifications
        WHERE provider='didit-sandbox' AND provider_reference_id=$1`,
      [sessionId],
    )
  ).rows[0];
  assert.equal(v.status, "REVIEW_REQUIRED");
});

test("reconcile-pg teardown", async () => {
  if (pool) await pool.end();
});
