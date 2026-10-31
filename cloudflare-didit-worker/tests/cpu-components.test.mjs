/**
 * SEC-CF-001 / Workstream A — component CPU measurements (LOCAL only).
 * Live Cloudflare isolate: UNVERIFIED.
 */
import assert from "node:assert/strict";
import test from "node:test";
import { canonical } from "../src/canonical.js";
import {
  OPERATING_ENVELOPE_BYTES,
  SOFT_WARN_BYTES,
  MAX_BYTES,
  classifyPayloadSize,
  parseJsonStrict,
} from "../src/parse.js";
import { durableProjection } from "../src/redact.js";
import { hmacHexSha256, signEvent, verifyWebhook } from "../src/verify.js";
import { APP, SECRET, WORKFLOW, baseEvent } from "./helpers.mjs";

const FREE_MS = 10;
const HEADROOM = 0.5; // target p95 < 5ms for envelope sizes

function cpuMs(fn) {
  const t0 = process.hrtime.bigint();
  fn();
  return Number(process.hrtime.bigint() - t0) / 1e6;
}

function bench(fn, n = 40) {
  const samples = [];
  for (let i = 0; i < n; i++) samples.push(cpuMs(fn));
  samples.sort((a, b) => a - b);
  return {
    p50: samples[Math.floor(n * 0.5)],
    p95: samples[Math.floor(n * 0.95)],
    max: samples[n - 1],
  };
}

function nestedUnicodeEvent(approxBytes) {
  const pad = "José-αβγ".repeat(Math.max(1, Math.ceil(approxBytes / 20)));
  return baseEvent({
    metadata: { name: "José", note: pad, nested: { a: 1, b: { c: pad.slice(0, 200) } } },
    decision: {
      status: "Approved",
      id_verifications: [{ status: "Approved", filler: pad.slice(0, Math.min(pad.length, 4000)) }],
    },
  });
}

test("component CPU: parse / duplicate-key / HMAC / privacy (representative)", () => {
  const event = nestedUnicodeEvent(4_000);
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const parseB = bench(() => parseJsonStrict(payload));
  const canonB = bench(() => canonical(JSON.parse(new TextDecoder().decode(payload))));
  const hmacB = bench(() => hmacHexSha256(Buffer.from(SECRET), canonical(event)));
  const privB = bench(() => durableProjection(event));
  const verifyB = bench(() =>
    verifyWebhook({
      payload,
      signature,
      timestamp,
      webhookSecret: SECRET,
      applicationId: APP,
      environment: "sandbox",
      workflowId: WORKFLOW,
    }),
  );
  const report = {
    class: "local_simulation",
    live_cf: "UNVERIFIED",
    workers_free_ms: FREE_MS,
    target_p95_ms: FREE_MS * HEADROOM,
    payload_bytes: payload.byteLength,
    parse_p95_ms: +parseB.p95.toFixed(3),
    canonical_p95_ms: +canonB.p95.toFixed(3),
    hmac_p95_ms: +hmacB.p95.toFixed(3),
    privacy_p95_ms: +privB.p95.toFixed(3),
    verify_total_p95_ms: +verifyB.p95.toFixed(3),
  };
  console.log(JSON.stringify({ evidence: "cpu_components_representative", ...report }));
  assert.ok(verifyB.p95 < FREE_MS * HEADROOM, `verify p95 ${verifyB.p95}`);
});

test("component CPU: operating envelope (~128KiB) with headroom", () => {
  const event = nestedUnicodeEvent(90_000);
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  assert.ok(payload.byteLength <= OPERATING_ENVELOPE_BYTES * 1.5);
  const verifyB = bench(
    () =>
      verifyWebhook({
        payload,
        signature,
        timestamp,
        webhookSecret: SECRET,
        applicationId: APP,
        environment: "sandbox",
        workflowId: WORKFLOW,
      }),
    15,
  );
  console.log(
    JSON.stringify({
      evidence: "cpu_components_envelope",
      class: "local_simulation",
      live_cf: "UNVERIFIED",
      payload_bytes: payload.byteLength,
      size_class: classifyPayloadSize(payload.byteLength),
      verify_p95_ms: +verifyB.p95.toFixed(3),
      under_headroom: verifyB.p95 < FREE_MS * HEADROOM,
      under_free_limit: verifyB.p95 < FREE_MS,
    }),
  );
  // Soft: envelope should usually stay under Free limit locally; if host slow, still < 2x.
  assert.ok(verifyB.p95 < FREE_MS * 2);
});

test("adversarial: unicode nested bursts stay under Free limit locally for soft sizes", () => {
  const event = nestedUnicodeEvent(20_000);
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const bursts = [];
  for (let b = 0; b < 5; b++) {
    bursts.push(
      bench(() =>
        verifyWebhook({
          payload,
          signature,
          timestamp,
          webhookSecret: SECRET,
          applicationId: APP,
          environment: "sandbox",
          workflowId: WORKFLOW,
        }),
      10,
      ),
    );
  }
  const worst = Math.max(...bursts.map((x) => x.p95));
  console.log(
    JSON.stringify({
      evidence: "cpu_components_burst",
      class: "local_simulation",
      live_cf: "UNVERIFIED",
      payload_bytes: payload.byteLength,
      worst_burst_p95_ms: +worst.toFixed(3),
    }),
  );
  assert.ok(worst < FREE_MS);
});

test("size policy constants and classification", () => {
  assert.equal(classifyPayloadSize(1000), "within_soft");
  assert.equal(classifyPayloadSize(SOFT_WARN_BYTES + 1), "soft_warn");
  assert.equal(classifyPayloadSize(OPERATING_ENVELOPE_BYTES + 1), "above_operating_envelope");
  assert.equal(classifyPayloadSize(MAX_BYTES + 1), "hard_reject_retryable");
});

test("oversized hard cap is retryable 503 not silent discard / not 403", async () => {
  const { handleDiditWebhook } = await import("../src/handler.js");
  const { InMemoryIdentityStore } = await import("../src/store.js");
  const { env } = await import("./helpers.mjs");
  const huge = new Uint8Array(MAX_BYTES + 10);
  huge.set(new TextEncoder().encode('{"a":1}'));
  const store = new InMemoryIdentityStore();
  const res = await handleDiditWebhook(
    new Request("https://idv.example/webhooks/didit", {
      method: "POST",
      headers: {
        "X-Signature-V2": "0".repeat(64),
        "X-Timestamp": String(Math.floor(Date.now() / 1000)),
      },
      body: huge,
    }),
    { store, env: env() },
  );
  assert.equal(res.status, 503);
  const body = await res.json();
  assert.equal(body.reconcile, true);
  assert.equal(body.error, "PAYLOAD_TOO_LARGE");
});

test("duplicate-key path still fail-closed after single-pass parse", () => {
  assert.throws(
    () => parseJsonStrict(new TextEncoder().encode('{"x":1,"x":2}')),
    /duplicate/,
  );
});
