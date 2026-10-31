/**
 * SEC-CF-007A/B/C — Database authority hardening adversarial suite.
 * Mandatory items 1–18 on real PG 16 with distinct non-superuser logins.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import { PgIdentityStore } from "../src/pg_store.js";
import { sovereignAdmitPg } from "../src/sovereign.js";
import { baseEvent } from "./helpers.mjs";
import {
  ADMIN_URL,
  EDGE_URL,
  RECONCILE_URL,
  SOVEREIGN_URL,
  applyAllSchemas,
  assertSessionUser,
  createPool,
  truncateIdentityTables,
} from "./pg_roles.mjs";

let admin;
let edge;
let sovereign;
let reconcile;
let ready = false;

test("007ABC setup: schemas + distinct non-superuser logins", async (t) => {
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
  reconcile = createPool(RECONCILE_URL);

  await assertSessionUser(edge, "whitepact_edge_login");
  await assertSessionUser(sovereign, "whitepact_sovereign_login");
  await assertSessionUser(reconcile, "whitepact_reconcile_login");

  const su = await admin.query(
    `SELECT rolname, rolsuper FROM pg_roles
      WHERE rolname IN ('whitepact_edge_login','whitepact_sovereign_login','whitepact_reconcile_login')`,
  );
  assert.equal(su.rows.length, 3);
  assert.ok(su.rows.every((r) => r.rolsuper === false));
  ready = true;
});

async function edgeSeedApproved(sessionId = randomUUID(), userId = "user-1") {
  const store = new PgIdentityStore(edge, { provider: "didit-sandbox" });
  await store.bindSession({
    sessionId,
    userId,
    orgId: "org-1",
    contextHash: "ctx",
  });
  const event = baseEvent({ session_id: sessionId, vendor_data: userId, status: "Approved" });
  const r = await store.commitIdentityEvent(event);
  return { store, sessionId, event, result: r };
}

// 1. Edge SET GUC cannot elevate
test("1 edge set_config sovereign_admit=on cannot grant IDENTITY_VERIFIED", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  await edge.query(`SELECT set_config('whitepact.sovereign_admit','on', true)`);
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET status='IDENTITY_VERIFIED', sovereign_admission='ADMITTED'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007A|42501/,
  );
  const row = await edge.query(
    `SELECT status, sovereign_admission FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "REVIEW_REQUIRED");
  assert.equal(row.rows[0].sovereign_admission, "PENDING");
});

// 2. Edge SET ROLE to sovereign denied
test("2 edge cannot SET ROLE whitepact_sovereign / sovereign_login", async (t) => {
  if (!ready) return t.skip("no pg");
  await assert.rejects(
    () => edge.query("SET ROLE whitepact_sovereign"),
    /permission denied|42501/i,
  );
  await assert.rejects(
    () => edge.query("SET ROLE whitepact_sovereign_login"),
    /permission denied|42501/i,
  );
});

// 3. Edge cannot EXECUTE admit function
test("3 edge cannot execute whitepact_sovereign_apply_admission", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  await assert.rejects(
    () =>
      edge.query(`SELECT * FROM whitepact_sovereign_apply_admission('didit-sandbox', $1, true)`, [
        sessionId,
      ]),
    /permission denied|42501/i,
  );
});

// 4. Edge cannot DELETE provider events
test("4 edge cannot DELETE identity_provider_events", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId, event } = await edgeSeedApproved();
  await assert.rejects(
    () =>
      edge.query(`DELETE FROM identity_provider_events WHERE session_id=$1`, [sessionId]),
    /permission denied|append-only|42501|SEC-CF-007B/i,
  );
  const n = await edge.query(
    `SELECT count(*)::int AS n FROM identity_provider_events WHERE event_id=$1`,
    ["event:" + event.event_id],
  );
  assert.equal(n.rows[0].n, 1);
});

// 5. Edge cannot UPDATE provider events (append-only)
test("5 edge cannot UPDATE identity_provider_events", async (t) => {
  if (!ready) return t.skip("no pg");
  const { event } = await edgeSeedApproved();
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_provider_events SET payload_hash='tampered' WHERE event_id=$1`,
        ["event:" + event.event_id],
      ),
    /permission denied|append-only|42501|SEC-CF-007B/i,
  );
});

// 6. Edge cannot TRUNCATE sensitive tables
test("6 edge cannot TRUNCATE provider events / verifications", async (t) => {
  if (!ready) return t.skip("no pg");
  await assert.rejects(
    () => edge.query("TRUNCATE identity_provider_events"),
    /permission denied|42501/i,
  );
  await assert.rejects(
    () => edge.query("TRUNCATE identity_verifications"),
    /permission denied|42501/i,
  );
});

// 7. Edge cannot DROP trigger / replace elevation function
test("7 edge cannot DROP trigger or REPLACE elevation function", async (t) => {
  if (!ready) return t.skip("no pg");
  await assert.rejects(
    () => edge.query("DROP TRIGGER trg_prevent_edge_identity_elevation ON identity_verifications"),
    /permission denied|must be owner|42501/i,
  );
  await assert.rejects(
    () =>
      edge.query(`
        CREATE OR REPLACE FUNCTION whitepact_prevent_edge_identity_elevation()
        RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RETURN NEW; END; $$;
      `),
    /permission denied|must be owner|42501/i,
  );
});

// 8. Edge cannot ALTER TABLE ownership / disable trigger
test("8 edge cannot ALTER OWNER or DISABLE TRIGGER", async (t) => {
  if (!ready) return t.skip("no pg");
  await assert.rejects(
    () =>
      edge.query(
        "ALTER TABLE identity_verifications OWNER TO whitepact_edge_login",
      ),
    /permission denied|must be owner|42501/i,
  );
  await assert.rejects(
    () =>
      edge.query(
        "ALTER TABLE identity_verifications DISABLE TRIGGER trg_prevent_edge_identity_elevation",
      ),
    /permission denied|must be owner|42501/i,
  );
});

// 9. Edge INSERT/UPDATE still records PROVIDER_APPROVED (authorized path)
test("9 edge authorized path: bind + Approved → PROVIDER_APPROVED only", async (t) => {
  if (!ready) return t.skip("no pg");
  const { result, sessionId } = await edgeSeedApproved();
  assert.equal(result.provider_proofing_status, "PROVIDER_APPROVED");
  assert.equal(result.identity_transition, false);
  assert.equal(result.elevates, false);
  const row = await edge.query(
    `SELECT status, provider_proofing_status, sovereign_admission
       FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "REVIEW_REQUIRED");
  assert.equal(row.rows[0].provider_proofing_status, "PROVIDER_APPROVED");
  assert.equal(row.rows[0].sovereign_admission, "PENDING");
});

// 10. Sovereign login can admit via DEFINER function
test("10 sovereign_login admits via whitepact_sovereign_apply_admission", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  const adm = await sovereignAdmitPg(sovereign, {
    provider: "didit-sandbox",
    sessionId,
    admit: true,
  });
  assert.equal(adm.status, "IDENTITY_VERIFIED");
  assert.equal(adm.elevates, true);
  const row = await sovereign.query(
    `SELECT status, sovereign_admission FROM identity_verifications WHERE provider_reference_id=$1`,
    [sessionId],
  );
  assert.equal(row.rows[0].status, "IDENTITY_VERIFIED");
  assert.equal(row.rows[0].sovereign_admission, "ADMITTED");
});

// 11. Reconcile cannot elevate / cannot execute admit
test("11 reconcile_login cannot elevate or execute admit", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  await assert.rejects(
    () =>
      reconcile.query(
        `UPDATE identity_verifications SET status='IDENTITY_VERIFIED', sovereign_admission='ADMITTED'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /permission denied|SEC-CF-007A|42501/i,
  );
  await assert.rejects(
    () =>
      reconcile.query(`SELECT * FROM whitepact_sovereign_apply_admission('didit-sandbox', $1, true)`, [
        sessionId,
      ]),
    /permission denied|42501/i,
  );
});

// 12. Reconcile can write jobs only
test("12 reconcile can INSERT jobs; edge cannot", async (t) => {
  if (!ready) return t.skip("no pg");
  const id = randomUUID();
  await reconcile.query(
    `INSERT INTO identity_reconciliation_jobs
       (id, provider, session_id, user_id, org_id, reason, state)
     VALUES ($1,'didit-sandbox',$2,'u','o','missed','pending')`,
    [id, randomUUID()],
  );
  await assert.rejects(
    () =>
      edge.query(
        `INSERT INTO identity_reconciliation_jobs
           (id, provider, session_id, user_id, org_id, reason, state)
         VALUES ($1,'didit-sandbox',$2,'u','o','missed','pending')`,
        [randomUUID(), randomUUID()],
      ),
    /permission denied|42501/i,
  );
});

// 13. Sovereign cannot DELETE/UPDATE provider events
test("13 sovereign_login cannot mutate append-only provider events", async (t) => {
  if (!ready) return t.skip("no pg");
  const { event } = await edgeSeedApproved();
  await assert.rejects(
    () =>
      sovereign.query(
        `DELETE FROM identity_provider_events WHERE event_id=$1`,
        ["event:" + event.event_id],
      ),
    /permission denied|append-only|42501|SEC-CF-007B/i,
  );
  await assert.rejects(
    () =>
      sovereign.query(
        `UPDATE identity_provider_events SET status='x' WHERE event_id=$1`,
        ["event:" + event.event_id],
      ),
    /permission denied|append-only|42501|SEC-CF-007B/i,
  );
});

// 14. Edge GUC + SET ROLE combo still fails
test("14 edge cannot combine GUC spoof with membership tricks", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  await edge.query("SELECT set_config('whitepact.sovereign_admit','on', false)");
  await assert.rejects(() => edge.query("SET ROLE whitepact_sovereign"), /permission/i);
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET status='IDENTITY_VERIFIED', sovereign_admission='ADMITTED'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007A|42501/,
  );
});

// 15. Idempotent edge retry still works without UPDATE on events
test("15 edge idempotent retry (SELECT FOR UPDATE + INSERT) under hardened grants", async (t) => {
  if (!ready) return t.skip("no pg");
  const store = new PgIdentityStore(edge, { provider: "didit-sandbox" });
  const event = baseEvent({ status: "Approved" });
  await store.bindSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    contextHash: "ctx",
  });
  const first = await store.commitIdentityEvent(event);
  assert.equal(first.duplicate, false);
  const second = await store.commitIdentityEvent({
    ...event,
    timestamp: event.timestamp + 10,
  });
  assert.equal(second.duplicate, true);
  assert.equal(second.status, "ALREADY_PROCESSED");
});

// 16. Privilege catalog: edge lacks UPDATE/DELETE on events
test("16 information_schema: edge has no UPDATE/DELETE on provider events", async (t) => {
  if (!ready) return t.skip("no pg");
  const r = await edge.query(
    `SELECT privilege_type FROM information_schema.role_table_grants
      WHERE grantee IN ('whitepact_edge_login','whitepact_edge_webhook')
        AND table_name='identity_provider_events'`,
  );
  const types = new Set(r.rows.map((x) => x.privilege_type));
  assert.ok(types.has("SELECT"));
  assert.ok(types.has("INSERT"));
  assert.ok(!types.has("UPDATE"));
  assert.ok(!types.has("DELETE"));
  assert.ok(!types.has("TRUNCATE"));
});

// 17. session_user proofs are genuine distinct logins (not SET ROLE from superuser)
test("17 connections are distinct LOGIN roles (007C)", async (t) => {
  if (!ready) return t.skip("no pg");
  const e = await edge.query("SELECT session_user AS su, current_setting('role') AS r");
  const s = await sovereign.query("SELECT session_user AS su");
  const c = await reconcile.query("SELECT session_user AS su");
  assert.equal(e.rows[0].su, "whitepact_edge_login");
  assert.equal(s.rows[0].su, "whitepact_sovereign_login");
  assert.equal(c.rows[0].su, "whitepact_reconcile_login");
  assert.notEqual(e.rows[0].su, s.rows[0].su);
  // Not a superuser SET ROLE façade: current_user equals session_user for edge
  const cu = await edge.query("SELECT current_user AS cu");
  assert.equal(cu.rows[0].cu, "whitepact_edge_login");
});

// 18. Deny path: sovereign deny; edge still cannot reopen to IDENTITY_VERIFIED
test("18 sovereign deny + edge cannot reopen to IDENTITY_VERIFIED", async (t) => {
  if (!ready) return t.skip("no pg");
  const { sessionId } = await edgeSeedApproved();
  const denied = await sovereignAdmitPg(sovereign, {
    provider: "didit-sandbox",
    sessionId,
    admit: false,
  });
  assert.equal(denied.status, "REJECTED");
  assert.equal(denied.elevates, false);
  await assert.rejects(
    () =>
      edge.query(
        `UPDATE identity_verifications
            SET status='IDENTITY_VERIFIED', sovereign_admission='ADMITTED'
          WHERE provider_reference_id=$1`,
        [sessionId],
      ),
    /SEC-CF-007A|42501|REOPEN|/,
  );
  // Even sovereign DEFINER refuses reopen after REJECTED
  await assert.rejects(
    () =>
      sovereignAdmitPg(sovereign, {
        provider: "didit-sandbox",
        sessionId,
        admit: true,
      }),
    /REOPEN_FORBIDDEN|42501/,
  );
});

test("007ABC teardown", async () => {
  if (edge) await edge.end();
  if (sovereign) await sovereign.end();
  if (reconcile) await reconcile.end();
  if (admin) await admin.end();
});
