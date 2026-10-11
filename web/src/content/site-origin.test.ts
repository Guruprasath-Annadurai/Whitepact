// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { describe, expect, it } from "vitest";
import { siteContract, validatePublicBuildConfig } from "./site-origin";
describe("website origin and indexing contract", () => {
  it("defaults to canonical production", () => expect(siteContract()).toEqual({ origin: "https://whitepact.com", profile: "production", noIndex: false }));
  it.each(["http://localhost:8765", "https://127.0.0.1", "https://private.internal", "https://staging.whitepact.com", "https://whitepact.com/path", "https://user:password@whitepact.com", "https://whitepact.com?x=1"])("rejects invalid production override %s", origin => expect(() => siteContract(origin)).toThrow());
  it("forces staging noindex", () => expect(siteContract("https://staging.whitepact.com", "staging").noIndex).toBe(true));
  it("allows explicit local test origins", () => expect(siteContract("http://localhost:4173", "test").noIndex).toBe(true));
  it.each(["http://staging.whitepact.com", "https://localhost", "https://127.0.0.1", "https://private.internal"])("rejects nonpublic staging %s", origin => expect(() => siteContract(origin, "staging")).toThrow());
  it("rejects unknown profiles", () => expect(() => siteContract(undefined, "prodution")).toThrow());
  it("rejects unreviewed browser environment variables", () => expect(() => validatePublicBuildConfig({ VITE_SERVER_PASSWORD: "not-a-real-secret" })).toThrow());
  it("does not accept a server key as a client token", () => expect(() => validatePublicBuildConfig({ VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "pdl_sdbx_apikey_fixture" })).toThrow());
  it("accepts documented public configuration", () => expect(() => validatePublicBuildConfig({ VITE_WHITEPACT_SITE_PROFILE: "production" })).not.toThrow());
  it("reports malformed origins without reflecting configuration values", () => expect(() => siteContract("not-a-public-origin")).toThrow("Malformed website origin"));
});
