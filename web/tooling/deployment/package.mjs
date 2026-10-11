// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
/** Offline validation only: no fetch, sockets, shell commands or deployment writes. */
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

function inventory(directory, prefix = "") {
  return fs.readdirSync(directory).sort().flatMap(name => {
    const relative = prefix + name;
    const entry = fs.lstatSync(path.join(directory, name));
    if (entry.isSymbolicLink()) throw new Error("Symlink artifacts are prohibited");
    if (entry.isDirectory()) return inventory(path.join(directory, name), relative + "/");
    if (!entry.isFile()) throw new Error("Non-file artifact prohibited");
    return [relative];
  });
}

export function verifyArtifact(directory, manifest) {
  if (manifest.schema !== 1 || !/^[a-f0-9]{40}$/.test(manifest.candidate ?? "") || !/^[a-f0-9]{40}$/.test(manifest.tree ?? "") || manifest.workingTreeClean !== true) throw new Error("Clean exact-source manifest required");
  if (!["production", "staging"].includes(manifest.profile)) throw new Error("Deployment profile must be explicit");
  let origin;
  try { origin = new URL(manifest.origin); } catch { throw new Error("Invalid manifest origin"); }
  if (origin.protocol !== "https:" || origin.origin !== manifest.origin || origin.username || origin.password) throw new Error("HTTPS origin-only metadata required");
  if (manifest.profile === "production" && origin.origin !== "https://whitepact.com") throw new Error("Noncanonical production metadata");
  if (manifest.profile === "staging" && (!origin.hostname.includes(".") || /(^[\d.]+$|:|\.(local|internal|test|invalid)$)/i.test(origin.hostname))) throw new Error("Staging requires public HTTPS hostname");
  if (!manifest.sha256 || typeof manifest.sha256 !== "object" || Array.isArray(manifest.sha256)) throw new Error("Digest inventory required");
  const names = Object.keys(manifest.sha256).sort();
  if (!names.length || manifest.fileCount !== names.length || names.some(name => !name || name.startsWith("/") || name.includes("\\") || name.split("/").some(part => !part || part === "." || part === "..") || !/^[a-f0-9]{64}$/.test(manifest.sha256[name]))) throw new Error("Invalid digest inventory");
  if (JSON.stringify(inventory(directory)) !== JSON.stringify(names)) throw new Error("Missing or unmanifested artifact");
  for (const name of names) {
    const actual = crypto.createHash("sha256").update(fs.readFileSync(path.join(directory, name))).digest("hex");
    if (actual !== manifest.sha256[name]) throw new Error("Artifact digest mismatch");
  }
  const routes = JSON.parse(fs.readFileSync(path.join(directory, "public-routes.json"), "utf8"));
  if (routes.origin !== manifest.origin || routes.profile !== manifest.profile || routes.routes.length !== 15 || new Set(routes.routes).size !== 15 || manifest.routeCount !== routes.routes.length) throw new Error("Route/profile manifest mismatch");
  if (routes.routes.some(route => !/^\/(?:[a-z0-9-]+)?$/.test(route) || /^\/(api|dashboard|login|signup|admin|onboarding)$/.test(route))) throw new Error("Invalid public route inventory");
  for (const route of routes.routes) {
    const filename = `pages/${route === "/" ? "home" : route.slice(1)}.html`;
    const html = fs.readFileSync(path.join(directory, filename), "utf8");
    if (!html.includes(`rel="canonical" href="${manifest.origin}${route}"`)) throw new Error("Route canonical mismatch");
    if (manifest.profile === "staging" && !html.includes('content="noindex,nofollow"')) throw new Error("Staging indexing allowed");
  }
  return { pass: true, candidate: manifest.candidate, tree: manifest.tree, profile: manifest.profile, fileCount: names.length, routes: routes.routes.length, proof: "OFFLINE BYTE INTEGRITY ONLY; qualification and deployed bytes remain separate" };
}

/** Rehearse asset-first activation and prior HTML restoration without copying/deleting files. */
export function rehearseRollback(previousDirectory, previous, nextDirectory, next) {
  verifyArtifact(previousDirectory, previous);
  verifyArtifact(nextDirectory, next);
  if (previous.profile !== next.profile || previous.origin !== next.origin) throw new Error("Cannot mix profiles/origins in rollback");
  const shared = Object.keys(previous.sha256).filter(name => name.startsWith("assets/") && Object.hasOwn(next.sha256, name));
  if (shared.some(name => previous.sha256[name] !== next.sha256[name])) throw new Error("Asset path collision: version asset before activation");
  const union = new Set([...Object.keys(previous.sha256), ...Object.keys(next.sha256)].filter(name => name.startsWith("assets/")));
  let checkedReferences = 0;
  for (const [directory, manifest] of [[previousDirectory, previous], [nextDirectory, next]]) {
    for (const name of Object.keys(manifest.sha256).filter(name => name.endsWith(".html"))) {
      const html = fs.readFileSync(path.join(directory, name), "utf8");
      for (const match of html.matchAll(/(?:src|href)="\/static\/whitepact\/([^"?#]+)"/g)) {
        if (!union.has(match[1])) throw new Error("Old/new HTML dependency absent from retained asset set");
        checkedReferences += 1;
      }
    }
  }
  return { pass: true, mode: "OFFLINE DRY-RUN", previousCandidate: previous.candidate, nextCandidate: next.candidate, retainedAssetCount: union.size, checkedReferences, phases: ["verify both immutable artifact inventories", "publish union of old/new assets without deleting prior assets", "verify all old/new references", "atomically select new public HTML", "on failure atomically reselect previous public HTML", "retain both asset sets and verify prior routes"], infrastructureRollbackProven: false, networkRequests: 0, filesChanged: 0 };
}

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value !== null && typeof value === "object") return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  return JSON.stringify(value);
}

/** Generates deterministic evidence data only; callers may capture stdout outside checkout. */
export function deploymentEvidence(previousDirectory, previous, nextDirectory, next) {
  const previousVerification = verifyArtifact(previousDirectory, previous);
  const nextVerification = verifyArtifact(nextDirectory, next);
  const rollback = rehearseRollback(previousDirectory, previous, nextDirectory, next);
  const digest = value => crypto.createHash("sha256").update(canonicalJson(value)).digest("hex");
  return {
    schema: 1, mode: "OFFLINE DRY-RUN", deploymentAuthorized: false,
    manifestDigestEncoding: "SHA-256 of recursively key-sorted compact JSON; not raw sidecar bytes",
    previous: { ...previousVerification, manifestDigest: digest(previous) },
    next: { ...nextVerification, manifestDigest: digest(next) },
    layout: {
      scope: "Proposed relative filesystem contract; not provisioned",
      previousRelease: `releases/${previous.candidate}/public`,
      nextRelease: `releases/${next.candidate}/public`,
      evidence: `releases/${next.candidate}/evidence`,
      assets: "shared/assets", currentPointer: "current", previousPointer: "previous",
      pointerStrategy: "Same-filesystem atomic rename of prepared symlink, compare current target first; infrastructure owner must verify each origin instance",
    },
    failureRecovery: {
      beforeActivation: "Leave current unchanged; retain prior release and collect failed-build/upload evidence",
      afterActivation: "Atomically restore prior current target on every serving instance; retain union assets, run prior acceptance, do not rebuild or delete",
      uncertainInfrastructureState: "Stop rollout; operator-approved public-only maintenance, no automatic production mutation",
    },
    rollback,
    externalChecks: Object.fromEntries(["ownerApproval", "manifestAuthenticity", "tls", "dns", "cloudflare", "hetznerLoadBalancer", "privateOriginProtection", "atomicActivation", "maintenance", "postdeploy", "failedDeployRollback", "previousReleaseRestoration"].map(name => [name, "NOT VERIFIED"])),
    networkRequests: 0, filesChanged: 0,
  };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const [command, ...args] = process.argv.slice(2);
  let result;
  try {
    if (command === "verify" && args.length === 2) result = verifyArtifact(args[0], JSON.parse(fs.readFileSync(args[1], "utf8")));
    else if (command === "rehearse" && args.length === 4) result = rehearseRollback(args[0], JSON.parse(fs.readFileSync(args[1], "utf8")), args[2], JSON.parse(fs.readFileSync(args[3], "utf8")));
    else if (command === "evidence" && args.length === 4) result = deploymentEvidence(args[0], JSON.parse(fs.readFileSync(args[1], "utf8")), args[2], JSON.parse(fs.readFileSync(args[3], "utf8")));
    else throw new Error("Use verify <artifact-directory> <manifest> or rehearse/evidence <old-directory> <old-manifest> <new-directory> <new-manifest>");
  } catch (error) {
    // Never reflect manifest contents or an uncontrolled parser error into logs.
    result = { pass: false, mode: "OFFLINE DRY-RUN", cause: error instanceof SyntaxError ? "Malformed JSON input" : error.message, networkRequests: 0 };
    process.exitCode = 1;
  }
  console.log(JSON.stringify(result, null, 2));
}
