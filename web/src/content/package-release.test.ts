// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { describe, expect, it } from "vitest";
import { packagePublication, publishedPackageContent, type PackagePublication } from "./package-release";

const fixture: PackagePublication = { ownerApproved: true, registryVerified: true, reproducibleInstallVerified: true,
  distribution: "test-distribution", version: "1.2.3", sourceCommit: "a".repeat(40), artifactSha256: "b".repeat(64) };
describe("package editorial release gate", () => {
  it("is closed for the actual website release", () => expect(publishedPackageContent(packagePublication)).toBeNull());
  it.each(["ownerApproved", "registryVerified", "reproducibleInstallVerified"] as const)("requires %s", key =>
    expect(publishedPackageContent({ ...fixture, [key]: false })).toBeNull());
  it.each(["distribution", "version", "sourceCommit", "artifactSha256"] as const)("rejects invalid %s", key =>
    expect(publishedPackageContent({ ...fixture, [key]: "unverified; shell" })).toBeNull());
  it("renders only explicitly approved version-pinned content", () => expect(publishedPackageContent(fixture)?.command).toBe("pip install test-distribution==1.2.3"));
});
