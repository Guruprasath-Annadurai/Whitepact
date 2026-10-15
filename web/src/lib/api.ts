// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function csrfToken(): string {
  return document.cookie
    .split("; ")
    .find((item) => item.startsWith("wp_csrf="))
    ?.split("=")[1] ?? "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? "GET").toUpperCase();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) headers.set("X-WP-CSRF", csrfToken());
  // Bound reads only. Aborting an unsafe mutation is not proof it did not occur.
  // Callers own reconciliation; this client never automatically retries.
  const readController = ["GET", "HEAD"].includes(method) ? new AbortController() : null;
  const cancel = () => readController?.abort(init.signal?.reason);
  if (init.signal?.aborted) cancel();
  else init.signal?.addEventListener("abort", cancel, { once: true });
  let timedOut = false;
  const timer = readController ? window.setTimeout(() => {
    timedOut = true; readController.abort();
  }, 15_000) : null;
  try {
    const response = await fetch(path, { ...init, signal: readController?.signal ?? init.signal, headers, credentials: "same-origin" });
    let payload = null;
    if (method !== "HEAD" && ![204, 205].includes(response.status)) {
      try { payload = await response.json(); }
      catch {
        // Preserve status on an HTTP failure, but never accept invalid success JSON.
        // Keep parser diagnostics/private response text out of the user interface.
        if (response.ok) throw new Error("The server response could not be confirmed. Inspect the current state before repeating a change.");
      }
    }
    if (!response.ok) {
      const message = payload?.detail ?? payload?.message ?? `Request failed (${response.status})`;
      throw new ApiError(response.status, typeof message === "string" ? message : "Request failed");
    }
    return payload as T;
  } catch (cause) {
    if (timedOut) throw new Error("Read timed out. Retry the read when the service is available.");
    throw cause;
  } finally {
    if (timer !== null) window.clearTimeout(timer);
    init.signal?.removeEventListener("abort", cancel);
  }
}

export function messageFrom(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
