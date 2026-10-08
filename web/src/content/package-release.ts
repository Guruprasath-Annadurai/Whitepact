// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

/** Editorial release evidence, not runtime authorization or an entitlement. */
export const qualifiedPlatformCommit = "c1d7803fce0787f9183e18bb38134f73a6c0f57d";
export const qualifiedPlatformSource = `https://github.com/Guruprasath-Annadurai/Whitepact/blob/${qualifiedPlatformCommit}/`;

export type PackagePublication = {
  ownerApproved: boolean;
  registryVerified: boolean;
  reproducibleInstallVerified: boolean;
  distribution: string;
  version: string;
  sourceCommit: string;
  artifactSha256: string;
};

// No final package publication has been approved for this website release.
export const packagePublication: PackagePublication | null = null;

export function publishedPackageContent(evidence: PackagePublication | null) {
  if (!evidence?.ownerApproved || !evidence.registryVerified || !evidence.reproducibleInstallVerified) return null;
  if (!/^[a-z][a-z0-9-]*$/.test(evidence.distribution) || !/^\d+\.\d+\.\d+$/.test(evidence.version)
    || !/^[a-f0-9]{40}$/.test(evidence.sourceCommit) || !/^[a-f0-9]{64}$/.test(evidence.artifactSha256)) return null;
  return {
    command: `pip install ${evidence.distribution}==${evidence.version}`,
    url: `https://pypi.org/project/${evidence.distribution}/${evidence.version}/`,
  };
}
