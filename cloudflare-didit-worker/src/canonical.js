/**
 * Didit X-Signature-V2 canonical JSON.
 * Must stay byte-compatible with WhitePact Python:
 *   json.dumps(_normalize(value), sort_keys=True, separators=(",", ":"),
 *              ensure_ascii=False, allow_nan=False).encode("utf-8")
 * and with Didit docs (sort keys, compact separators, Unicode preserved,
 * whole floats shortened to ints).
 */

export function normalize(value) {
  if (value === null) return null;
  if (Array.isArray(value)) return value.map(normalize);
  if (typeof value === "object") {
    const out = {};
    for (const key of Object.keys(value).sort()) {
      out[key] = normalize(value[key]);
    }
    return out;
  }
  if (typeof value === "number") {
    if (!Number.isFinite(value)) {
      throw new Error("nonfinite JSON");
    }
    // Match Python float.is_integer() → int for whole floats.
    if (Number.isInteger(value)) return value;
    // JS JSON may already be int; also catch 1.0-style numbers that survive parse.
    if (Object.is(value, Math.trunc(value))) return Math.trunc(value);
    return value;
  }
  return value;
}

/**
 * Produce canonical UTF-8 bytes for HMAC-SHA256.
 * JSON.stringify with sorted keys already applied via normalize().
 * ensure_ascii=False equivalent: do not escape non-ASCII.
 */
export function canonical(value) {
  const normalized = normalize(value);
  // JSON.stringify escapes U+2028/U+2029 in some engines; Node preserves Unicode
  // for BMP letters. We use the same compact separators as Python/Didit.
  return new TextEncoder().encode(JSON.stringify(normalized));
}

export function canonicalHexDigest(value, cryptoImpl) {
  // Helper for tests; production uses Web Crypto HMAC separately.
  return canonical(value);
}
