// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { afterEach, describe, expect, it, vi } from "vitest";
import { passkeysSupported, requestPasskey } from "../features/authority/passkeyClient";

afterEach(() => vi.unstubAllGlobals());
const options: PublicKeyCredentialRequestOptions = { challenge: new Uint8Array([1, 2, 3]), userVerification: "required" };
function browser() {
  class CredentialResponse {}
  const get = vi.fn();
  const create = vi.fn();
  vi.stubGlobal("PublicKeyCredential", CredentialResponse);
  vi.stubGlobal("isSecureContext", true);
  vi.stubGlobal("navigator", { credentials: { get, create } });
  return { get, create, credential: new CredentialResponse() };
}

describe("native WebAuthn browser seam — not server verification", () => {
  it("fails closed on unsupported or insecure browsers", async () => {
    browser(); vi.stubGlobal("isSecureContext", false);
    expect(passkeysSupported()).toBe(false);
    await expect(requestPasskey({ kind: "step-up", options }, new AbortController().signal)).rejects.toMatchObject({ kind: "unsupported" });
  });
  it("passes the exact server options and cancellation signal to the browser", async () => {
    const b = browser(); b.get.mockResolvedValue(b.credential);
    const signal = new AbortController().signal;
    expect(await requestPasskey({ kind: "step-up", options }, signal)).toBe(b.credential);
    expect(b.get).toHaveBeenCalledExactlyOnceWith({ publicKey: options, signal });
    expect(b.create).not.toHaveBeenCalled();
  });
  it("uses native create for enrollment without creating its own challenge", async () => {
    const b = browser(); b.create.mockResolvedValue(b.credential);
    const creation: PublicKeyCredentialCreationOptions = { challenge: options.challenge, rp: { name: "Test server" }, user: { id: new Uint8Array([4]), name: "test", displayName: "Test" }, pubKeyCredParams: [{ type: "public-key", alg: -7 }] };
    const signal = new AbortController().signal;
    await requestPasskey({ kind: "enroll", options: creation }, signal);
    expect(b.create).toHaveBeenCalledExactlyOnceWith({ publicKey: creation, signal });
    expect(b.get).not.toHaveBeenCalled();
  });
  it.each(["NotAllowedError", "AbortError"])("does not retry %s or expose diagnostics", async (name) => {
    const b = browser(); b.get.mockRejectedValue(new DOMException("private authenticator diagnostic", name));
    await expect(requestPasskey({ kind: "step-up", options }, new AbortController().signal)).rejects.toMatchObject({ kind: "cancelled-or-expired", message: expect.not.stringContaining("private") });
    expect(b.get).toHaveBeenCalledTimes(1);
  });
  it.each([null, {}, { verified: true }])("rejects missing or fabricated credential %s", async (value) => {
    const b = browser(); b.get.mockResolvedValue(value);
    await expect(requestPasskey({ kind: "step-up", options }, new AbortController().signal)).rejects.toMatchObject({ kind: "unavailable" });
  });
  it("does not return a late credential after cancellation", async () => {
    const b = browser(); const controller = new AbortController();
    b.get.mockImplementation(async () => { controller.abort(); return b.credential; });
    await expect(requestPasskey({ kind: "step-up", options }, controller.signal)).rejects.toMatchObject({ kind: "cancelled-or-expired" });
  });
  it("redacts unexpected browser errors", async () => {
    const b = browser(); b.get.mockRejectedValue(new Error("sensitive diagnostic"));
    await expect(requestPasskey({ kind: "step-up", options }, new AbortController().signal)).rejects.toMatchObject({ kind: "unavailable", message: expect.not.stringContaining("sensitive") });
  });
});
