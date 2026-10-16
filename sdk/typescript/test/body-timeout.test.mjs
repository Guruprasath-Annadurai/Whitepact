import assert from "node:assert/strict";
import http from "node:http";
import { test } from "node:test";
import { RAIClient } from "../dist/index.js";

test("timeout remains active while a successful response body is incomplete", async () => {
  const server = http.createServer((_req, res) => {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.write('{"ok":');
    // Deliberately never finish the body after sending successful headers.
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  let deadline;
  try {
    const client = new RAIClient({
      baseUrl: `http://127.0.0.1:${server.address().port}`,
      timeout: 100,
      maxRetries: 1,
    });
    const result = client.health().then(
      () => "success",
      error => error.name,
    );
    const observed = await Promise.race([
      result,
      new Promise(resolve => { deadline = setTimeout(() => resolve("deadline exceeded"), 1500); }),
    ]);
    assert.equal(observed, "AbortError");
  } finally {
    clearTimeout(deadline);
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
});
