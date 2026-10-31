import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { createHash, createHmac } from "node:crypto";
import { fileURLToPath } from "node:url";
import path from "node:path";
import test from "node:test";
import { canonical, normalize } from "../src/canonical.js";
import { hmacHexSha256 } from "../src/verify.js";

const root = path.dirname(fileURLToPath(import.meta.url));
const pyScript = path.join(root, "..", "scripts", "python_canonical_crosscheck.py");

test("normalize shortens whole floats like Python float.is_integer", () => {
  assert.deepEqual(normalize({ a: 1.0, b: 1.5, c: [2.0] }), {
    a: 1,
    b: 1.5,
    c: [2],
  });
});

test("canonical sorts keys and preserves Unicode (José)", () => {
  const bytes = canonical({ z: 1, a: "José", nested: { b: 2, a: 1 } });
  const text = new TextDecoder().decode(bytes);
  assert.equal(text, '{"a":"José","nested":{"a":1,"b":2},"z":1}');
  assert.ok(text.includes("José"));
  assert.ok(!text.includes("\\u00e9"));
});

test("JS canonical bytes match Python Didit-compatible dumps", () => {
  const samples = [
    { event_id: "e", status: "Approved", metadata: { name: "José" }, n: 1.0 },
    { z: [3, { b: 1, a: 2 }], a: true, u: null },
    { webhook_type: "status.updated", timestamp: 1710000000, created_at: 1709999999 },
  ];

  for (const sample of samples) {
    const jsHex = createHash("sha256").update(canonical(sample)).digest("hex");
    const proc = spawnSync(
      "python3",
      [pyScript, "--digest", JSON.stringify(sample)],
      { encoding: "utf8" },
    );
    assert.equal(proc.status, 0, proc.stderr || proc.stdout);
    const pyHex = proc.stdout.trim();
    assert.equal(jsHex, pyHex, `digest mismatch for ${JSON.stringify(sample)}`);
  }
});

test("HMAC-SHA256 over canonical matches Python hmac", () => {
  const body = { timestamp: 1710000000, session_id: "s", status: "Approved", name: "José" };
  const secret = "local-contract-secret";
  const js = hmacHexSha256(Buffer.from(secret), canonical(body));
  const proc = spawnSync(
    "python3",
    [pyScript, "--hmac", secret, JSON.stringify(body)],
    { encoding: "utf8" },
  );
  assert.equal(proc.status, 0, proc.stderr || proc.stdout);
  assert.equal(js, proc.stdout.trim());
  // Sanity: node crypto same as createHmac directly
  assert.equal(
    js,
    createHmac("sha256", secret).update(canonical(body)).digest("hex"),
  );
});
