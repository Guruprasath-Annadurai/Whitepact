import assert from "node:assert/strict";
import test from "node:test";
import {
  assertNoMediaInRecord,
  durableProjection,
  scrubForLogs,
} from "../src/redact.js";
import { baseEvent, postWebhook, storeWithBinding } from "./helpers.mjs";

test("durable projection strips decision / id / liveness / face arrays", () => {
  const event = baseEvent({
    decision: {
      status: "Approved",
      id_verifications: [{ status: "Approved", document_front: "BASE64IMAGE==" }],
      liveness_checks: [{ status: "Approved", liveness_video: "AAAA" }],
      face_matches: [{ status: "Approved", portrait: "BBBB" }],
    },
    id_verifications: [{ document_front: "leak" }],
    metadata: { full_name: "should-not-persist" },
  });
  const proj = durableProjection(event);
  assert.equal("decision" in proj, false);
  assert.equal("id_verifications" in proj, false);
  assert.equal("metadata" in proj, false);
  assertNoMediaInRecord(proj);
});

test("scrubForLogs redacts biometric-ish keys", () => {
  const scrubbed = scrubForLogs({
    event_id: "e",
    decision: { portrait: "abc" },
    selfie_image: "xyz",
    status: "Approved",
  });
  assert.equal(scrubbed.decision, "[redacted]");
  assert.equal(scrubbed.selfie_image, "[redacted]");
  assert.equal(scrubbed.status, "Approved");
});

test("HTTP success path stores no media-bearing fields", async () => {
  const event = baseEvent({
    decision: {
      id_verifications: [{ document_front: "data:image/png;base64,AAAA" }],
      liveness_checks: [{ biometric: true, video: "AAAA" }],
    },
  });
  const store = storeWithBinding(event.session_id);
  const res = await postWebhook({ event, store });
  assert.equal(res.status, 200);
  const record = store.events.get("event:" + event.event_id);
  assertNoMediaInRecord(record);
  const json = JSON.stringify(record);
  assert.equal(json.includes("document_front"), false);
  assert.equal(json.includes("data:image"), false);
  assert.equal(json.includes("biometric"), false);
});

test("assertNoMediaInRecord throws on leak", () => {
  assert.throws(() => assertNoMediaInRecord({ note: "data:image/png;base64,xx" }));
  assert.throws(() => assertNoMediaInRecord({ decision: { status: "Approved" } }));
});
