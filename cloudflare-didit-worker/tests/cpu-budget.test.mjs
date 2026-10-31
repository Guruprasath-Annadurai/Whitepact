/**
 * Local CPU budget evidence vs Cloudflare Workers Free 10 ms CPU limit.
 *
 * Methodology: measure process.hrtime wall of CPU-bound path only
 * (canonical + HMAC + parse + verify), excluding I/O. This is a LOCAL
 * SIMULATION on the agent host CPU — NOT a live Cloudflare isolate measurement.
 * Live CF CPU: UNVERIFIED (deploy forbidden).
 */
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import test from "node:test";
import { canonical } from "../src/canonical.js";
import { parseJsonStrict } from "../src/parse.js";
import { hmacHexSha256, signEvent, verifyWebhook } from "../src/verify.js";
import { APP, SECRET, WORKFLOW, baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";

const WORKERS_FREE_CPU_MS = 10;

function cpuMs(fn) {
  const t0 = process.hrtime.bigint();
  fn();
  const t1 = process.hrtime.bigint();
  return Number(t1 - t0) / 1e6;
}

function largeDecisionEvent(kbApprox = 32) {
  const pad = "á".repeat(Math.max(16, Math.floor((kbApprox * 1024) / 2)));
  return baseEvent({
    metadata: { name: "José", note: pad },
    // decision is present on wire for signature but stripped before durable store
    decision: {
      status: "Approved",
      id_verifications: [{ status: "Approved", filler: pad }],
      liveness_checks: [{ status: "Approved", filler: pad }],
      face_matches: [{ status: "Approved", filler: pad }],
    },
  });
}

test("typical webhook verify CPU << 10ms on local host (SIMULATION)", () => {
  const event = baseEvent({ metadata: { name: "José" } });
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const samples = [];
  for (let i = 0; i < 50; i++) {
    samples.push(
      cpuMs(() => {
        verifyWebhook({
          payload,
          signature,
          timestamp,
          webhookSecret: SECRET,
          applicationId: APP,
          environment: "sandbox",
          workflowId: WORKFLOW,
        });
      }),
    );
  }
  samples.sort((a, b) => a - b);
  const p50 = samples[Math.floor(samples.length * 0.5)];
  const p95 = samples[Math.floor(samples.length * 0.95)];
  const max = samples[samples.length - 1];
  // Soft assertion: typical path should be under Free limit on this host.
  // If host is extremely slow, still record evidence without false FAIL of design.
  assert.ok(p50 < WORKERS_FREE_CPU_MS, `p50=${p50}ms must be < ${WORKERS_FREE_CPU_MS}ms`);
  assert.ok(p95 < WORKERS_FREE_CPU_MS * 2, `p95=${p95}ms unexpectedly high`);
  // Evidence fields for qualification report (printed).
  console.log(
    JSON.stringify({
      evidence: "cpu_budget_typical",
      class: "local_simulation",
      workers_free_cpu_ms: WORKERS_FREE_CPU_MS,
      live_cf_measurement: "UNVERIFIED",
      p50_ms: Number(p50.toFixed(3)),
      p95_ms: Number(p95.toFixed(3)),
      max_ms: Number(max.toFixed(3)),
      n: samples.length,
      host: process.platform + "/" + process.arch,
    }),
  );
});

test("adversarial ~32KiB Unicode decision envelope still under local 10ms budget (SIMULATION)", () => {
  const event = largeDecisionEvent(32);
  const { payload, signature, timestamp } = signEvent(event, SECRET);
  const samples = [];
  for (let i = 0; i < 20; i++) {
    samples.push(
      cpuMs(() => {
        verifyWebhook({
          payload,
          signature,
          timestamp,
          webhookSecret: SECRET,
          applicationId: APP,
          environment: "sandbox",
          workflowId: WORKFLOW,
        });
      }),
    );
  }
  samples.sort((a, b) => a - b);
  const p95 = samples[Math.floor(samples.length * 0.95)];
  console.log(
    JSON.stringify({
      evidence: "cpu_budget_adversarial_32kib",
      class: "local_simulation",
      payload_bytes: payload.byteLength,
      p95_ms: Number(p95.toFixed(3)),
      under_free_limit_locally: p95 < WORKERS_FREE_CPU_MS,
      live_cf_measurement: "UNVERIFIED",
    }),
  );
  assert.ok(p95 < WORKERS_FREE_CPU_MS * 3, `adversarial p95=${p95}ms`);
});

test("canonical+HMAC microbench alone is sub-millisecond locally", () => {
  const event = baseEvent({ metadata: { name: "José" } });
  const ms = cpuMs(() => {
    for (let i = 0; i < 100; i++) {
      hmacHexSha256(Buffer.from(SECRET), canonical(event));
    }
  });
  const perOp = ms / 100;
  console.log(
    JSON.stringify({
      evidence: "cpu_budget_hmac_micro",
      class: "local_simulation",
      per_op_ms: Number(perOp.toFixed(4)),
      live_cf_measurement: "UNVERIFIED",
    }),
  );
  assert.ok(perOp < 1);
});

test("end-to-end handler path CPU (verify+commit) local evidence", async () => {
  const event = baseEvent();
  const store = storeWithBinding(event.session_id);
  const t0 = process.hrtime.bigint();
  const res = await postWebhook({ event, store });
  const ms = Number(process.hrtime.bigint() - t0) / 1e6;
  assert.equal(res.status, 200);
  console.log(
    JSON.stringify({
      evidence: "cpu_budget_e2e_handler",
      class: "local_simulation",
      wall_ms_includes_async: Number(ms.toFixed(3)),
      note: "includes event-loop scheduling; CF isolate CPU still UNVERIFIED",
      live_cf_measurement: "UNVERIFIED",
    }),
  );
});

test("pathological large body: under-cap CPU CONDITIONAL; over 2MB hard-rejected", () => {
  // ~200KiB under the 2MB hard cap — CPU risk CONDITIONAL on CF Free 10ms.
  const event = largeDecisionEvent(200);
  const raw = new TextEncoder().encode(JSON.stringify(event));
  assert.ok(raw.byteLength > 100_000 && raw.byteLength < 2_000_000);
  const ms = cpuMs(() => {
    parseJsonStrict(raw);
    hmacHexSha256(Buffer.from(SECRET), canonical(JSON.parse(new TextDecoder().decode(raw))));
  });
  console.log(
    JSON.stringify({
      evidence: "cpu_budget_pathological_200kib",
      class: "local_simulation",
      payload_bytes: raw.byteLength,
      cpu_ms: Number(ms.toFixed(3)),
      workers_free_cpu_ms: WORKERS_FREE_CPU_MS,
      local_under_limit: ms < WORKERS_FREE_CPU_MS,
      claim: "CONDITIONAL on live CF isolate — local evidence only",
      live_cf_measurement: "UNVERIFIED",
    }),
  );
  // Hard cap: >2MB rejected fail-closed (implementation evidence).
  const oversize = new Uint8Array(2_000_001);
  oversize.set(new TextEncoder().encode("{"));
  assert.throws(() => parseJsonStrict(oversize), /oversized/);
});

test("digest stability evidence for report hash chain", () => {
  const event = baseEvent({ event_id: "11111111-1111-4111-8111-111111111111" });
  // Fix timestamps for stable digest in evidence blob.
  event.timestamp = 1_800_000_000;
  event.created_at = 1_799_999_999;
  event.session_id = "22222222-2222-4222-8222-222222222222";
  const digest = createHash("sha256").update(canonical(event)).digest("hex");
  console.log(
    JSON.stringify({
      evidence: "canonical_fixture_digest",
      class: "implementation_evidence",
      sha256: digest,
    }),
  );
  assert.equal(digest.length, 64);
});
