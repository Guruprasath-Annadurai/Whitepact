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
  const response = await fetch(path, { ...init, headers, credentials: "same-origin" });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const message = payload?.detail ?? payload?.message ?? `Request failed (${response.status})`;
    throw new ApiError(response.status, typeof message === "string" ? message : "Request failed");
  }
  return payload as T;
}

export function messageFrom(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback;
}
