// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, expect, it, vi } from "vitest";
import { api, ApiError } from "../lib/api";
import { mutationAcknowledgementUncertain } from "../lib/approvalOutcome";

afterEach(() => { vi.useRealTimers(); vi.restoreAllMocks(); });

it("bounds a stalled read and permits an explicit fresh retry without automatic requests", async () => {
  vi.useFakeTimers();
  const fetch = vi.spyOn(window, "fetch").mockImplementationOnce((_url, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
  })).mockResolvedValueOnce(Response.json({ status: "returned" }));
  const pending = api("/api/v1/web/evidence");
  const rejected = expect(pending).rejects.toThrow(/Read timed out/);
  await vi.advanceTimersByTimeAsync(15_000);
  await rejected;
  expect(fetch).toHaveBeenCalledTimes(1);
  expect(await api("/api/v1/web/evidence")).toEqual({ status: "returned" });
  expect(fetch).toHaveBeenCalledTimes(2);
});

it("preserves caller read cancellation and releases timers", async () => {
  vi.useFakeTimers(); const controller = new AbortController();
  vi.spyOn(window, "fetch").mockImplementation((_url, init) => new Promise((_resolve, reject) => {
    init?.signal?.addEventListener("abort", () => reject(new DOMException("Cancelled", "AbortError")));
  }));
  const pending = api("/api/v1/web/evidence", { signal: controller.signal });
  const rejected = expect(pending).rejects.toMatchObject({ name: "AbortError" });
  controller.abort(); await rejected;
  expect(vi.getTimerCount()).toBe(0);
});

it("rejects invalid successful JSON as uncertain for mutations, never normal completion", async () => {
  const fetch = vi.spyOn(window, "fetch").mockResolvedValue(new Response("private-invalid-canary", { status: 200 }));
  let failure: unknown;
  try { await api("/api/v1/web/approvals/id/execute", { method: "POST", body: "{}" }); } catch (cause) { failure = cause; }
  expect(failure).toBeInstanceOf(Error);
  expect(String(failure)).not.toContain("private-invalid-canary");
  expect(mutationAcknowledgementUncertain(failure)).toBe(true);
  expect(fetch).toHaveBeenCalledTimes(1);
});

it.each([401, 403, 404, 409, 503])("preserves HTTP %i even for an invalid JSON error body", async (status) => {
  vi.spyOn(window, "fetch").mockResolvedValue(new Response("private-error-canary", { status }));
  await expect(api("/api/v1/web/evidence")).rejects.toMatchObject({ status });
  await expect(api("/api/v1/web/evidence")).rejects.toBeInstanceOf(ApiError);
});

it("does not attach a timer or silently retry a consequential mutation", async () => {
  vi.useFakeTimers(); let finish!: (response: Response) => void;
  const fetch = vi.spyOn(window, "fetch").mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
  const pending = api("/api/v1/web/approvals/id/execute", { method: "POST", body: "{}" });
  expect(vi.getTimerCount()).toBe(0);
  await vi.advanceTimersByTimeAsync(60_000);
  expect(fetch).toHaveBeenCalledTimes(1);
  finish(Response.json({ execution_status: "UNKNOWN" }));
  expect(await pending).toEqual({ execution_status: "UNKNOWN" });
});

it("cleans successful-read timers and accepts explicit no-content responses", async () => {
  vi.useFakeTimers();
  vi.spyOn(window, "fetch").mockResolvedValue(new Response(null, { status: 204 }));
  expect(await api("/api/v1/web/session")).toBeNull();
  expect(vi.getTimerCount()).toBe(0);
});
