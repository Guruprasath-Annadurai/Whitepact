/**
 * Privacy: never persist raw identity documents, biometric media, or
 * high-entropy document images into Neon / logs.
 *
 * Persist only decision metadata needed for idempotency + tenant binding:
 * event_id, session_id, vendor_data, status, workflow/application/env,
 * created_at, payload_hash. Strip decision feature blobs that may carry PII media.
 */

const FORBIDDEN_KEY_FRAGMENTS = [
  "image",
  "portrait",
  "selfie",
  "biometric",
  "face_image",
  "document_front",
  "document_back",
  "id_front",
  "id_back",
  "raw_document",
  "media_url",
  "base64",
  "photo",
  "video",
  "liveness_video",
  "full_frame",
];

const FORBIDDEN_TOP_LEVEL = new Set([
  "decision", // may embed document/biometric arrays — never store wholesale
  "id_verifications",
  "liveness_checks",
  "face_matches",
  "aml_screenings",
  "metadata", // often contains free-text PII from provider samples
]);

function keyForbidden(key) {
  const k = String(key).toLowerCase();
  return FORBIDDEN_KEY_FRAGMENTS.some((f) => k.includes(f));
}

/**
 * Returns a persistence-safe projection + asserts no forbidden media leaked.
 */
export function durableProjection(event) {
  const out = {
    event_id: event.event_id,
    webhook_type: event.webhook_type,
    session_id: event.session_id,
    vendor_data: event.vendor_data,
    status: event.status,
    workflow_id: event.workflow_id,
    application_id: event.application_id,
    environment: event.environment,
    created_at: event.created_at,
    // timestamp intentionally omitted from durable digest body (retry-refreshed)
  };

  for (const key of Object.keys(event)) {
    if (FORBIDDEN_TOP_LEVEL.has(key)) continue;
    if (keyForbidden(key)) {
      throw new Error(`refusing to project forbidden field: ${key}`);
    }
  }

  // Defense in depth: never copy unknown nested blobs.
  return out;
}

/**
 * Scrub objects before any log emission. Replaces forbidden values with "[redacted]".
 */
export function scrubForLogs(value, depth = 0) {
  if (depth > 8) return "[truncated]";
  if (value == null) return value;
  if (Array.isArray(value)) return value.map((v) => scrubForLogs(v, depth + 1));
  if (typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      if (FORBIDDEN_TOP_LEVEL.has(k) || keyForbidden(k)) {
        out[k] = "[redacted]";
      } else if (typeof v === "string" && v.length > 256 && /^[A-Za-z0-9+/=]+$/.test(v)) {
        out[k] = "[redacted-blob]";
      } else {
        out[k] = scrubForLogs(v, depth + 1);
      }
    }
    return out;
  }
  return value;
}

export function assertNoMediaInRecord(record) {
  const json = JSON.stringify(record);
  for (const frag of ["data:image", "base64,", "biometric", "liveness_video"]) {
    if (json.toLowerCase().includes(frag)) {
      throw new Error(`media leak detected in durable record (${frag})`);
    }
  }
  if ("decision" in record || "id_verifications" in record) {
    throw new Error("media-bearing decision fields must not be stored");
  }
}
