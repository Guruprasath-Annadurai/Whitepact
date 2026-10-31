/**
 * Didit reconciliation — mocked API only. Never elevates identity from decision GET.
 * Preserves fail-closed tenant binding + #244 reconcile contract.
 */
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import test from "node:test";
import {
  DiditClient,
  DiditClientError,
  createMockDiditFetch,
  validateDecision,
} from "../src/didit_client.js";
import {
  RECONCILE_STATES,
  REQUIRED_ACTION,
  ReconcileEngine,
  InMemoryReconcileJobStore,
} from "../src/reconcile.js";
import { simulateDiditRetryBudget } from "../src/handler.js";
import { payloadHashHex } from "../src/verify.js";
import { APP, WORKFLOW, baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";

const API_KEY = "test-api-key-not-real";

function approvedDecision(sessionId, overrides = {}) {
  return {
    session_id: sessionId,
    session_kind: "user",
    status: "Approved",
    workflow_id: WORKFLOW,
    application_id: APP,
    environment: "sandbox",
    vendor_data: "user-1",
    id_verifications: [{ status: "Approved", node_id: "n1" }],
    liveness_checks: [{ status: "Approved", node_id: "n2" }],
    face_matches: [{ status: "Approved", node_id: "n3" }],
    // Toxic fields that must never be persisted by reconcile engine:
    id_verifications_media: undefined,
    ...overrides,
  };
}

function decisionUrl(sessionId) {
  return `https://verification.didit.me/v3/session/${sessionId}/decision/`;
}

function clientWith(fetchImpl) {
  return new DiditClient({
    apiKey: API_KEY,
    applicationId: APP,
    workflowId: WORKFLOW,
    environment: "sandbox",
    fetchImpl,
  });
}

function engineFor(store, fetchImpl) {
  return new ReconcileEngine({
    identityStore: store,
    client: clientWith(fetchImpl),
    enrollment: {
      applicationId: APP,
      workflowId: WORKFLOW,
      environment: "sandbox",
    },
  });
}

test("decision client: GET decision success + UUID guard", async () => {
  const sid = randomUUID();
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(sid)}`]: () => ({ body: approvedDecision(sid) }),
  });
  const client = clientWith(fetchImpl);
  const d = await client.retrieveDecision(sid);
  assert.equal(d.status, "Approved");
  await assert.rejects(() => client.retrieveDecision("not-a-uuid"), (e) => {
    assert.equal(e.code, "DIDIT_SESSION_INVALID");
    return true;
  });
});

test("decision client: timeouts / 503 / 401 / 404 / 429 classification", async () => {
  const sid = randomUUID();
  const cases = [
    [
      () => {
        throw Object.assign(new Error("aborted"), { name: "AbortError" });
      },
      "DIDIT_TIMEOUT",
      true,
    ],
    [() => ({ status: 503, body: { detail: "down" } }), "DIDIT_UNAVAILABLE", true],
    [() => ({ status: 401, body: { detail: "no" } }), "DIDIT_CREDENTIALS_INVALID", false],
    [() => ({ status: 404, body: { detail: "Not found." } }), "DIDIT_SESSION_NOT_FOUND", false],
    [() => ({ status: 429, body: { detail: "slow" } }), "DIDIT_RATE_LIMITED", true],
  ];
  for (const [handler, code, retryable] of cases) {
    const fetchImpl = createMockDiditFetch({
      [`GET ${decisionUrl(sid)}`]: handler,
    });
    const client = clientWith(fetchImpl);
    await assert.rejects(() => client.retrieveDecision(sid), (e) => {
      assert.equal(e.code, code);
      assert.equal(e.retryable, retryable);
      return true;
    });
  }
});

test("decision client: malformed / oversized / duplicate-key responses fail closed", async () => {
  const sid = randomUUID();
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(sid)}`]: () => ({
      status: 200,
      body: '{"status":"Approved","status":"Declined"}',
    }),
  });
  await assert.rejects(() => clientWith(fetchImpl).retrieveDecision(sid), (e) => {
    assert.equal(e.code, "DIDIT_RESPONSE_INVALID");
    return true;
  });

  const big = new Uint8Array(2_000_001);
  const fetchOver = async () =>
    new Response(big, { status: 200, headers: { "content-type": "application/json" } });
  await assert.rejects(() => clientWith(fetchOver).retrieveDecision(sid), (e) => {
    assert.equal(e.code, "DIDIT_RESPONSE_OVERSIZED");
    return true;
  });
});

test("validateDecision: Approved requires feature checks; strips media; cross-tenant", () => {
  const sid = randomUUID();
  const ok = validateDecision(approvedDecision(sid), {
    sessionId: sid,
    vendorData: "user-1",
    workflowId: WORKFLOW,
    applicationId: APP,
    environment: "sandbox",
  });
  assert.equal(ok.status, "Approved");
  assert.equal(ok.vendor_data, "user-1");
  assert.equal(ok.id_verifications, undefined);

  assert.throws(
    () =>
      validateDecision(approvedDecision(sid, { id_verifications: [{ status: "Declined" }] }), {
        sessionId: sid,
        vendorData: "user-1",
        workflowId: WORKFLOW,
        applicationId: APP,
        environment: "sandbox",
      }),
    (e) => e.code === "ASSURANCE_NOT_APPROVED",
  );

  assert.throws(
    () =>
      validateDecision(approvedDecision(sid, { vendor_data: "other-user" }), {
        sessionId: sid,
        vendorData: "user-1",
        workflowId: WORKFLOW,
        applicationId: APP,
        environment: "sandbox",
      }),
    (e) => e.code === "CROSS_TENANT",
  );
});

test("reconcile applied observation never elevates; signed webhook still required", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const before = store.verifications.get(event.session_id).status;
  assert.equal(before, "REVIEW_REQUIRED");

  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const engine = engineFor(store, fetchImpl);
  const snap = await engine.reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    reason: "missed_webhook",
  });
  assert.equal(snap.state, RECONCILE_STATES.APPLIED);
  assert.equal(snap.identity_transition, false);
  assert.equal(snap.elevates, false);
  assert.equal(snap.recovery_complete, false);
  assert.equal(snap.signed_webhook_required, true);
  assert.equal(snap.required_action, REQUIRED_ACTION);
  assert.equal(snap.provider_status, "Approved");
  assert.ok(snap.decision_hash);
  // Identity unchanged — decision alone is not authority.
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
  assert.equal(store.events.size, 0);

  // Authentic signed webhook still elevates via normal path.
  const admitted = await postWebhook({ event, store });
  assert.equal(admitted.status, 200);
  const body = await admitted.json();
  assert.equal(body.identity_transition, true);
  assert.equal(store.verifications.get(event.session_id).status, "IDENTITY_VERIFIED");
});

test("missed delivery / exhausted retries → deadletter enqueue → reconcile non-elevating", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateSuspension(true);
  await simulateDiditRetryBudget(async (attempt) => {
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
  assert.ok(store.deadletters.length >= 3);
  store.simulateSuspension(false);

  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const engine = engineFor(store, fetchImpl);
  const jobs = engine.enqueueFromDeadletters();
  assert.ok(jobs.length >= 1);
  const snap = await engine.advance(jobs[0].id);
  assert.equal(snap.state, RECONCILE_STATES.APPLIED);
  assert.equal(snap.elevates, false);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
});

test("provider outage then recovery on retryable_failure", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  let calls = 0;
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => {
      calls += 1;
      if (calls === 1) return { status: 503, body: { detail: "outage" } };
      return { body: approvedDecision(event.session_id) };
    },
  });
  const engine = engineFor(store, fetchImpl);
  const { job } = engine.enqueue({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  const first = await engine.advance(job.id);
  assert.equal(first.state, RECONCILE_STATES.RETRYABLE_FAILURE);
  assert.equal(first.last_error_class, "DIDIT_UNAVAILABLE");
  // Force next attempt due.
  const stored = engine.jobStore.getJob(job.id);
  stored.next_attempt_at = 0;
  engine.jobStore.saveJob(stored);
  const second = await engine.advance(job.id);
  assert.equal(second.state, RECONCILE_STATES.APPLIED);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
});

test("expired / invalid credentials → terminal_manual", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({ status: 401, body: { detail: "nope" } }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.TERMINAL_MANUAL);
  assert.equal(snap.last_error_class, "DIDIT_CREDENTIALS_INVALID");
  assert.equal(snap.elevates, false);
});

test("malformed decision / missing Approved features → terminal_manual", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: {
        session_id: event.session_id,
        status: "Approved",
        workflow_id: WORKFLOW,
        application_id: APP,
        environment: "sandbox",
        vendor_data: "user-1",
        id_verifications: [],
        liveness_checks: [{ status: "Approved" }],
        face_matches: [{ status: "Approved" }],
      },
    }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.TERMINAL_MANUAL);
  assert.equal(snap.last_error_class, "ASSURANCE_NOT_APPROVED");
});

test("revoked/rejected session cannot be reopened by decision GET", async () => {
  const event = baseEvent({ status: "Declined" });
  const store = storeWithBinding(event.session_id);
  // Admit declined via signed path first.
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 200);
  assert.equal(store.verifications.get(event.session_id).status, "REJECTED");

  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.TERMINAL_MANUAL);
  assert.equal(snap.last_error_class, "SESSION_REVOKED_OR_REJECTED");
  assert.equal(store.verifications.get(event.session_id).status, "REJECTED");
});

test("conflicting decision after verified: observe conflict, no unsigned suspend", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  assert.equal((await postWebhook({ event, store })).status, 200);
  assert.equal(store.verifications.get(event.session_id).status, "IDENTITY_VERIFIED");

  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: {
        session_id: event.session_id,
        status: "Declined",
        workflow_id: WORKFLOW,
        application_id: APP,
        environment: "sandbox",
        vendor_data: "user-1",
      },
    }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
    reason: "stale_check",
  });
  assert.equal(snap.state, RECONCILE_STATES.APPLIED);
  assert.equal(snap.last_error_class, "CONFLICTING_DECISION_OBSERVED");
  assert.equal(snap.elevates, false);
  // Still verified — only signed Declined webhook may suspend.
  assert.equal(store.verifications.get(event.session_id).status, "IDENTITY_VERIFIED");

  const decline = baseEvent({
    session_id: event.session_id,
    vendor_data: "user-1",
    status: "Declined",
    created_at: event.created_at + 10,
    timestamp: event.timestamp + 10,
  });
  const sus = await postWebhook({ event: decline, store });
  assert.equal(sus.status, 200);
  assert.equal(store.verifications.get(event.session_id).status, "SUSPENDED");
});

test("duplicate recovery is idempotent; no double elevation", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const engine = engineFor(store, fetchImpl);
  const a = await engine.reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  const b = await engine.reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  // Second enqueue may create new job or reuse open — either applied without elevation.
  assert.equal(a.elevates, false);
  assert.equal(b.elevates, false);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
  // Re-advance applied job is idempotent.
  const again = await engine.advance(a.job_id);
  assert.equal(again.state, RECONCILE_STATES.APPLIED);
  assert.equal(again.identity_transition, false);
});

test("cross-tenant reconcile denied", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const engine = engineFor(store, fetchImpl);
  await assert.rejects(
    () =>
      engine.reconcileSession({
        sessionId: event.session_id,
        userId: "other-user",
        orgId: "org-1",
      }),
    (e) => e.code === "CROSS_TENANT",
  );
  // vendor_data mismatch on decision also terminal if somehow bound correctly but decision wrong
  const fetchBad = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id, { vendor_data: "attacker" }),
    }),
  });
  const snap = await engineFor(store, fetchBad).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.TERMINAL_MANUAL);
  assert.equal(snap.last_error_class, "CROSS_TENANT");
});

test("rate limit → retryable_failure", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({ status: 429, body: { detail: "limit" } }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.RETRYABLE_FAILURE);
  assert.equal(snap.last_error_class, "DIDIT_RATE_LIMITED");
});

test("DB unavailable during advance → retryable; identity unchanged", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  const engine = engineFor(store, fetchImpl);
  const { job } = engine.enqueue({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  store.simulateSuspension(true);
  const snap = await engine.advance(job.id);
  assert.equal(snap.state, RECONCILE_STATES.RETRYABLE_FAILURE);
  assert.equal(snap.last_error_class, "IDENTITY_STORE_UNAVAILABLE");
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
});

test("workflow / environment / application mismatch fail closed", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id, { workflow_id: "wf-other" }),
    }),
  });
  const snap = await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  assert.equal(snap.state, RECONCILE_STATES.TERMINAL_MANUAL);
  assert.equal(snap.last_error_class, "DIDIT_DECISION_MISMATCH");
});

test("webhook delivery list/resend client shapes (mocked; entitlement not assumed)", async () => {
  const dest = randomUUID();
  const delivery = randomUUID();
  const fetchImpl = createMockDiditFetch((req) => {
    if (req.method === "GET" && req.url.includes(`/destinations/${dest}/deliveries/`)) {
      return {
        body: {
          results: [
            {
              uuid: delivery,
              session_id: randomUUID(),
              response_status: 503,
              attempt: 3,
            },
          ],
        },
      };
    }
    if (
      req.method === "POST" &&
      req.url.includes(`/deliveries/${delivery}/resend/`)
    ) {
      return {
        body: {
          uuid: randomUUID(),
          response_status: 200,
          attempt: 4,
        },
      };
    }
    return { status: 404, body: { detail: "Not found." } };
  });
  const client = clientWith(fetchImpl);
  const listed = await client.listWebhookDeliveries(dest);
  assert.equal(listed.results[0].uuid, delivery);
  const resent = await client.resendWebhookDelivery(dest, delivery);
  assert.equal(resent.response_status, 200);
  // Resend alone must not touch identity store — no store in this test.
});

test("reconcile:true on 503 is not recovery_complete", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  store.simulateSuspension(true);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 503);
  const body = await res.json();
  assert.equal(body.reconcile, true);
  assert.notEqual(body.recovery_complete, true);
  assert.equal(store.verifications.get(event.session_id).status, "REVIEW_REQUIRED");
});

test("OOO signed events still rejected after reconcile observation", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const fetchImpl = createMockDiditFetch({
    [`GET ${decisionUrl(event.session_id)}`]: () => ({
      body: approvedDecision(event.session_id),
    }),
  });
  await engineFor(store, fetchImpl).reconcileSession({
    sessionId: event.session_id,
    userId: "user-1",
    orgId: "org-1",
  });
  const newer = baseEvent({
    session_id: event.session_id,
    vendor_data: "user-1",
    created_at: event.created_at + 50,
    timestamp: event.timestamp + 50,
    status: "Approved",
  });
  assert.equal((await postWebhook({ event: newer, store })).status, 200);
  const older = baseEvent({
    session_id: event.session_id,
    vendor_data: "user-1",
    created_at: event.created_at,
    timestamp: event.timestamp + 60,
    status: "Approved",
  });
  const ooo = await postWebhook({ event: older, store });
  assert.equal(ooo.status, 403);
  assert.equal((await ooo.json()).error, "PROVIDER_EVENT_OUT_OF_ORDER");
});
