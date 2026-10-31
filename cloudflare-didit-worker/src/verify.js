/**
 * Didit V3 webhook authentication (X-Signature-V2 only).
 *
 * Contract (docs.didit.me/integration/webhooks, fetched 2026-10-31):
 * - X-Signature-V2: HMAC-SHA256 over sorted Unicode-preserved canonical JSON
 *   (ensure_ascii=False). Recommended. This is NOT HMAC(raw body bytes).
 * - X-Signature: HMAC-SHA256 over exact raw request bytes (legacy; fragile).
 * - X-Signature-Simple: envelope-only; MUST NOT authorize identity elevation.
 *
 * We parse from the original raw body Uint8Array, then verify V2 over
 * canonical(parsed). Constant-time compare via crypto.timingSafeEqual.
 * Matches WhitePact #244 DiditProvider.verify_webhook fail-closed rules.
 */

import { createHash, createHmac, timingSafeEqual } from "node:crypto";
import { canonical } from "./canonical.js";
import { parseJsonStrict } from "./parse.js";

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export class ProofInvalidError extends Error {
  constructor(message = "Didit verification proof is invalid.") {
    super(message);
    this.name = "ProofInvalidError";
    this.code = "DIDIT_PROOF_INVALID";
    this.httpStatus = 403;
  }
}

export function hmacHexSha256(secretBytes, messageBytes) {
  return createHmac("sha256", secretBytes).update(messageBytes).digest("hex");
}

/** Web Crypto HMAC for Cloudflare Workers runtime (parity with node:crypto). */
export async function hmacHexSha256Web(secretBytes, messageBytes, subtle) {
  const key = await subtle.importKey(
    "raw",
    secretBytes,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await subtle.sign("HMAC", key, messageBytes);
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function safeEqualHex(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) {
    return false;
  }
  try {
    return timingSafeEqual(Buffer.from(a, "utf8"), Buffer.from(b, "utf8"));
  } catch {
    return false;
  }
}

/**
 * @param {object} opts
 * @param {Uint8Array} opts.payload raw body bytes
 * @param {string} opts.signature X-Signature-V2 hex
 * @param {string} opts.timestamp X-Timestamp unix seconds string
 * @param {Uint8Array|string} opts.webhookSecret
 * @param {string} opts.applicationId enrolled application
 * @param {string} opts.environment "sandbox" | "live"
 * @param {string} opts.workflowId enrolled workflow
 * @param {boolean} [opts.testDelivery]
 * @param {() => number} [opts.now] unix seconds
 * @param {string} [opts.signaturePrevious] X-Signature-V2-Previous (rotation window)
 * @param {string|Uint8Array} [opts.previousWebhookSecret] replaced destination secret
 */
export function verifyWebhook(opts) {
  const {
    payload,
    signature,
    timestamp,
    webhookSecret,
    applicationId,
    environment,
    workflowId,
    testDelivery = false,
    now = () => Math.floor(Date.now() / 1000),
    signaturePrevious = "",
    previousWebhookSecret = "",
  } = opts;

  try {
    const data = parseJsonStrict(payload);
    if (!/^\d+$/.test(String(timestamp))) throw new Error("stale timestamp");
    const stamp = Number(timestamp);
    if (typeof data.timestamp !== "number" || !Number.isInteger(data.timestamp)) {
      throw new Error("stale timestamp");
    }
    if (data.timestamp !== stamp) throw new Error("stale timestamp");
    if (Math.abs(now() - stamp) > 300) throw new Error("stale timestamp");

    const canon = canonical(data);
    const toBytes = (s) =>
      typeof s === "string" ? new TextEncoder().encode(s) : s;

    const currentOk = safeEqualHex(signature, hmacHexSha256(toBytes(webhookSecret), canon));
    let previousOk = false;
    if (!currentOk && previousWebhookSecret && signaturePrevious) {
      // Didit rotation: accept match on V2 OR V2-Previous with replaced secret.
      previousOk =
        safeEqualHex(
          signaturePrevious,
          hmacHexSha256(toBytes(previousWebhookSecret), canon),
        ) ||
        safeEqualHex(signature, hmacHexSha256(toBytes(previousWebhookSecret), canon));
    }
    if (!currentOk && !previousOk) throw new Error("bad signature");

    if (data.application_id !== applicationId || data.environment !== environment) {
      throw new Error("wrong destination scope");
    }
    if (data.webhook_type !== "status.updated" && data.webhook_type !== "data.updated") {
      throw new Error("unsupported event");
    }
    if (!UUID_RE.test(String(data.event_id ?? ""))) throw new Error("event_id");
    if (!testDelivery && data.workflow_id !== workflowId) throw new Error("wrong workflow");
    if (typeof data.created_at !== "number" || !Number.isInteger(data.created_at)) {
      throw new Error("invalid event time");
    }
    if (data.created_at > stamp + 300) throw new Error("invalid event time");

    return data;
  } catch (err) {
    if (err instanceof ProofInvalidError) throw err;
    throw new ProofInvalidError();
  }
}

/**
 * Digest for durable idempotency — excludes refreshed retry timestamp.
 * Matches didit_service.py SHA-256(canonical(event without timestamp)).
 */
export function payloadHashHex(event) {
  const body = { ...event };
  delete body.timestamp;
  return createHash("sha256").update(canonical(body)).digest("hex");
}

/** Sign a fixture event the way Didit V2 does (local tests only). */
export function signEvent(event, secret) {
  const secretBytes = typeof secret === "string" ? Buffer.from(secret, "utf8") : secret;
  const payload = new TextEncoder().encode(JSON.stringify(event));
  const signature = hmacHexSha256(secretBytes, canonical(event));
  return { payload, signature, timestamp: String(event.timestamp) };
}
