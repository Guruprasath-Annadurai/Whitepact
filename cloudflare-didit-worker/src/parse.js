/**
 * Fail-closed JSON parse: reject duplicate keys (matches Python object_pairs_hook).
 * Caps payload size before parse.
 */

export const MAX_BYTES = 2_000_000;

function assertNoDuplicateKeys(text) {
  let i = 0;
  const stack = []; // each frame: Set of keys in current object

  const skipWs = () => {
    while (i < text.length && " \n\r\t".includes(text[i])) i += 1;
  };

  const readString = () => {
    if (text[i] !== '"') throw new Error("string");
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
        if (!'"\\/bfnrt'.includes(n)) throw new Error("escape");
        out += n;
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
    const c = text[i];
    if (c === "{") {
      i += 1;
      const keys = new Set();
      stack.push(keys);
      skipWs();
      if (text[i] === "}") {
        i += 1;
        stack.pop();
        return;
      }
      while (true) {
        skipWs();
        const key = readString();
        if (keys.has(key)) throw new Error("duplicate JSON key");
        keys.add(key);
        skipWs();
        if (text[i] !== ":") throw new Error("colon");
        i += 1;
        parseValue();
        skipWs();
        if (text[i] === "}") {
          i += 1;
          stack.pop();
          return;
        }
        if (text[i] !== ",") throw new Error("comma");
        i += 1;
      }
    }
    if (c === "[") {
      i += 1;
      skipWs();
      if (text[i] === "]") {
        i += 1;
        return;
      }
      while (true) {
        parseValue();
        skipWs();
        if (text[i] === "]") {
          i += 1;
          return;
        }
        if (text[i] !== ",") throw new Error("comma");
        i += 1;
      }
    }
    if (c === '"') {
      readString();
      return;
    }
    if (c === "-" || (c >= "0" && c <= "9")) {
      const m = text.slice(i).match(/^-?(0|[1-9]\d*)(\.\d+)?([eE][+-]?\d+)?/);
      if (!m) throw new Error("number");
      i += m[0].length;
      return;
    }
    if (text.startsWith("true", i)) {
      i += 4;
      return;
    }
    if (text.startsWith("false", i)) {
      i += 5;
      return;
    }
    if (text.startsWith("null", i)) {
      i += 4;
      return;
    }
    throw new Error("lex");
  };

  parseValue();
  skipWs();
  if (i !== text.length) throw new Error("trailing");
}

export function parseJsonStrict(bytes) {
  if (!(bytes instanceof Uint8Array)) {
    throw new Error("payload must be bytes");
  }
  if (bytes.byteLength > MAX_BYTES) {
    throw new Error("oversized payload");
  }
  const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  assertNoDuplicateKeys(text);
  let value;
  try {
    value = JSON.parse(text);
  } catch {
    throw new Error("invalid JSON");
  }
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("invalid payload");
  }
  return value;
}
