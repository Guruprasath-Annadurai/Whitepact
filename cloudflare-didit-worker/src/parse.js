/**
 * Fail-closed JSON parse: reject duplicate keys (matches Python object_pairs_hook).
 *
 * Single-pass recursive descent (builds value + rejects duplicate keys) —
 * avoids prior scan-then-JSON.parse double walk (SEC-CF-001 CPU risk).
 *
 * Size policy (documented for live ops):
 * - SOFT_WARN_BYTES: expected Didit envelopes stay under this (ops telemetry).
 * - OPERATING_ENVELOPE_BYTES: safe headroom for Workers Free 10ms CPU (local evidence).
 * - MAX_BYTES: hard cap. Oversized → OversizedPayloadError → handler maps to
 *   HTTP 503 (retryable) + reconcile, NOT 403. Never silently ACK/drop.
 */

export const SOFT_WARN_BYTES = 64 * 1024;
/** Local evidence envelope with headroom under Workers Free 10ms (see cpu report). */
export const OPERATING_ENVELOPE_BYTES = 128 * 1024;
export const MAX_BYTES = 2_000_000;

export class OversizedPayloadError extends Error {
  constructor(byteLength, limit = MAX_BYTES) {
    super(`oversized payload: ${byteLength} > ${limit}`);
    this.name = "OversizedPayloadError";
    this.code = "PAYLOAD_TOO_LARGE";
    this.httpStatus = 503; // Didit retries 5xx; do not use 403 (non-retry)
    this.byteLength = byteLength;
    this.limit = limit;
    this.reconcile = true;
  }
}

/**
 * Single-pass parse: returns JS value. Rejects duplicate keys / nonfinite / trailing junk.
 */
export function parseJsonStrict(bytes) {
  if (!(bytes instanceof Uint8Array)) {
    throw new Error("payload must be bytes");
  }
  if (bytes.byteLength > MAX_BYTES) {
    throw new OversizedPayloadError(bytes.byteLength, MAX_BYTES);
  }
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  let i = 0;

  const skipWs = () => {
    while (i < text.length) {
      const c = text.charCodeAt(i);
      if (c === 32 || c === 10 || c === 13 || c === 9) i += 1;
      else break;
    }
  };

  const readString = () => {
    if (text.charCodeAt(i) !== 34) throw new Error("string");
    i += 1;
    let out = "";
    while (i < text.length) {
      const ch = text[i];
      if (ch === '"') {
        i += 1;
        return out;
      }
      if (ch === "\\") {
        const n = text[i + 1];
        if (n === "u") {
          const hex = text.slice(i + 2, i + 6);
          if (!/^[0-9a-fA-F]{4}$/.test(hex)) throw new Error("unicode");
          out += String.fromCharCode(parseInt(hex, 16));
          i += 6;
          continue;
        }
        const map = { '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t" };
        if (!(n in map)) throw new Error("escape");
        out += map[n];
        i += 2;
        continue;
      }
      out += ch;
      i += 1;
    }
    throw new Error("string");
  };

  const parseValue = () => {
    skipWs();
    if (i >= text.length) throw new Error("truncated");
    const c = text[i];
    if (c === "{") {
      i += 1;
      const obj = Object.create(null);
      const seen = new Set();
      skipWs();
      if (text[i] === "}") {
        i += 1;
        return Object.assign({}, obj);
      }
      while (true) {
        skipWs();
        const key = readString();
        if (seen.has(key)) throw new Error("duplicate JSON key");
        seen.add(key);
        skipWs();
        if (text[i] !== ":") throw new Error("colon");
        i += 1;
        obj[key] = parseValue();
        skipWs();
        if (text[i] === "}") {
          i += 1;
          return Object.assign({}, obj);
        }
        if (text[i] !== ",") throw new Error("comma");
        i += 1;
      }
    }
    if (c === "[") {
      i += 1;
      const arr = [];
      skipWs();
      if (text[i] === "]") {
        i += 1;
        return arr;
      }
      while (true) {
        arr.push(parseValue());
        skipWs();
        if (text[i] === "]") {
          i += 1;
          return arr;
        }
        if (text[i] !== ",") throw new Error("comma");
        i += 1;
      }
    }
    if (c === '"') return readString();
    if (c === "-" || (c >= "0" && c <= "9")) {
      const m = text.slice(i).match(/^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/);
      if (!m) throw new Error("number");
      const num = Number(m[0]);
      if (!Number.isFinite(num)) throw new Error("nonfinite");
      i += m[0].length;
      return num;
    }
    if (text.startsWith("true", i)) {
      i += 4;
      return true;
    }
    if (text.startsWith("false", i)) {
      i += 5;
      return false;
    }
    if (text.startsWith("null", i)) {
      i += 4;
      return null;
    }
    throw new Error("lex");
  };

  const value = parseValue();
  skipWs();
  if (i !== text.length) throw new Error("trailing");
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("invalid payload");
  }
  return value;
}

/** Classify body size for telemetry / operating envelope checks (no mutation). */
export function classifyPayloadSize(byteLength) {
  if (byteLength > MAX_BYTES) return "hard_reject_retryable";
  if (byteLength > OPERATING_ENVELOPE_BYTES) return "above_operating_envelope";
  if (byteLength > SOFT_WARN_BYTES) return "soft_warn";
  return "within_soft";
}
