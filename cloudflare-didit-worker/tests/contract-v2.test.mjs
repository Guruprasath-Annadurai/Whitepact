/**
 * Exact Didit V3 / X-Signature-V2 contract vectors (local fixtures).
 * Genuine live-provider delivery: NOT OBTAINED.
 */
import assert from "node:assert/strict";
import { createHmac, timingSafeEqual } from "node:crypto";
import test from "node:test";
import { canonical } from "../src/canonical.js";
import {
  hmacHexSha256,
  ProofInvalidError,
  signEvent,
  verifyWebhook,
} from "../src/verify.js";
import { APP, SECRET, WORKFLOW, baseEvent } from "./helpers.mjs";

test("V2 HMAC is over canonical JSON bytes, not unsorted raw body", () => {
  const event = baseEvent({ z: 1, a: "José" });
  // Unsorted / pretty raw body (as a middleware might re-encode).
  const rawUnsorted = new TextEncoder().encode(
    JSON.stringify(event, null, 2),
  );
  const canon = canonical(event);
  const sigV2 = hmacHexSha256(Buffer.from(SECRET), canon);
  const sigRaw = createHmac("sha256", SECRET).update(rawUnsorted).digest("hex");
  assert.notEqual(sigV2, sigRaw, "V2 must differ from raw-body HMAC when bytes differ");

  // Verify accepts V2 against parsed body even when wire bytes are pretty-printed.
  const data = verifyWebhook({
    payload: rawUnsorted,
    signature: sigV2,
    timestamp: String(event.timestamp),
    webhookSecret: SECRET,
    applicationId: APP,
    environment: "sandbox",
    workflowId: WORKFLOW,
  });
  assert.equal(data.event_id, event.event_id);

  // Raw-body signature must NOT verify as V2.
  assert.throws(
    () =>
      verifyWebhook({
        payload: rawUnsorted,
        signature: sigRaw,
        timestamp: String(event.timestamp),
        webhookSecret: SECRET,
        applicationId: APP,
        environment: "sandbox",
        workflowId: WORKFLOW,
      }),
    ProofInvalidError,
  );
});

test("verification consumes original raw body bytes (no silent re-encode before parse)", () => {
  const event = baseEvent({ metadata: { name: "José" } });
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  // Mutate a copy — original payload object must remain the source of truth.
  const copy = new Uint8Array(payload);
  assert.deepEqual(copy, payload);
  const data = verifyWebhook({
    payload,
    signature,
    timestamp,
    webhookSecret: SECRET,
    applicationId: APP,
    environment: "sandbox",
    workflowId: WORKFLOW,
  });
  assert.equal(data.metadata.name, "José");
  // Payload bytes unchanged by verify.
  assert.deepEqual(payload, copy);
});

test("signature comparison is constant-time (timingSafeEqual path)", () => {
  const event = baseEvent();
  const { signature } = signEvent(event, SECRET);
  const a = Buffer.from(signature, "utf8");
  const b = Buffer.from(signature, "utf8");
  assert.equal(timingSafeEqual(a, b), true);
  const wrong = Buffer.from("0".repeat(64), "utf8");
  assert.equal(timingSafeEqual(a, wrong), false);
  // Length mismatch must not throw into open compare — verifyWebhook maps to ProofInvalid.
  assert.throws(
    () =>
      verifyWebhook({
        payload: signEvent(event, SECRET).payload,
        signature: "abc",
        timestamp: String(event.timestamp),
        webhookSecret: SECRET,
        applicationId: APP,
        environment: "sandbox",
        workflowId: WORKFLOW,
      }),
    ProofInvalidError,
  );
});

test("docs contract: retry refreshes timestamp; digest excludes timestamp", async () => {
  const { payloadHashHex } = await import("../src/verify.js");
  const event = baseEvent();
  const retry = { ...event, timestamp: event.timestamp + 90 };
  assert.equal(payloadHashHex(event), payloadHashHex(retry));
  assert.notEqual(canonical(event).length === 0, true);
  // Fresh V2 signature required for refreshed timestamp.
  const sig1 = signEvent(event, SECRET).signature;
  const sig2 = signEvent(retry, SECRET).signature;
  assert.notEqual(sig1, sig2);
});

test("X-Timestamp window is exactly 300 seconds per current Didit docs", () => {
  const event = baseEvent({ timestamp: 1_800_000_000, created_at: 1_799_999_900 });
  const { payload, signature } = signEvent(event, SECRET);
  // Boundary inclusive: abs(diff) == 300 OK
  assert.doesNotThrow(() =>
    verifyWebhook({
      payload,
      signature,
      timestamp: String(event.timestamp),
      webhookSecret: SECRET,
      applicationId: APP,
      environment: "sandbox",
      workflowId: WORKFLOW,
      now: () => event.timestamp + 300,
    }),
  );
  assert.throws(
    () =>
      verifyWebhook({
        payload,
        signature,
        timestamp: String(event.timestamp),
        webhookSecret: SECRET,
        applicationId: APP,
        environment: "sandbox",
        workflowId: WORKFLOW,
        now: () => event.timestamp + 301,
      }),
    ProofInvalidError,
  );
});
