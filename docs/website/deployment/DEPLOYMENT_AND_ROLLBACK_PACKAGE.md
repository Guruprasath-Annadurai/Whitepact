<!-- Copyright (c) 2026 Guruprasath Annadurai; SPDX-License-Identifier: MIT -->
# Website-side deployment and rollback package

Status: **prepared for owner/infrastructure review; NOT deployed**. This Track B
branch is not a qualified release. Frozen Phase 4 remains
`c9622a2539f20314205e1c30a0f4b8de3927b8f4`, tree
`bf04e0022dd42d0463ec69aa0f942ff5b10c5dea`. PR #148 must remain draft/unmerged.
Do not execute external acceptance or operational instructions without explicit
target and deployment authority. No credentials are needed for the offline checks.

Target routing is **Cloudflare edge → public Hetzner load balancer → private SaaS /
reverse-proxy origin**. These are requirements, not assertions about live setup.
This package owns only public static website delivery. Authentication, billing,
APIs, console, MCP and runtime enforcement retain their product-owned policies.

## 1. Deterministic production build

Use the approved exact commit in a clean detached checkout, a supported pinned
Node/npm environment from release CI, and committed lockfiles. Record Node/npm
versions. Do not build from main implicitly. Do not build on the deployment host
after generating the release manifest. In each of two independent clean checkouts:

```sh
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain
npm ci --ignore-scripts --no-audit --no-fund
npm ci --prefix web --ignore-scripts --no-audit --no-fund
VITE_WHITEPACT_SITE_PROFILE=production VITE_WHITEPACT_SITE_ORIGIN=https://whitepact.com npm --prefix web run build
node web/tooling/launch-contract.mjs audit
git diff --exit-code
git status --porcelain
```

Both status outputs must be empty. Compare every output file digest, not just the
entry HTML. A reproducible build proves bytes under the recorded environment,
not deployment, certification or signed provenance. Public build variables must
never contain server API keys or deployment credentials. No Paddle server key.

## 2. Artifact manifest verification

Retain `src/responsibleai/dashboard/static/whitepact/` with an external manifest
sidecar. Existing Phase 4 manifest generation requires a committed clean checkout:

```sh
node web/tooling/launch-contract.mjs manifest --output /absolute/external/evidence/website-manifest.json
node web/tooling/launch-contract.mjs verify /absolute/external/evidence/website-manifest.json
node web/tooling/deployment/package.mjs verify /absolute/artifact/directory /absolute/external/evidence/website-manifest.json
```

Paths are placeholders supplied by the operator, not pre-existing outputs.
The offline verifier checks exact files, SHA-256, source identity shape, clean
manifest flag, profile, origin and 15-route parity; rejects extra/missing files,
symlinks and unsafe paths. It does **not** authenticate an arbitrary manifest.
Obtain the expected SHA/tree/digests from qualified CI and independent review,
not an untrusted artifact. Compare CI sidecar and downloaded artifact before any
activation. Do not normalize or rewrite bytes during transfer.

## 3. Staging checklist

Separate staging build/manifest, explicit `staging` profile and owner-approved
HTTPS origin; noindex in all public pages and robots disallow all. Do not reuse
the production artifact with wrong canonicals. Before any staging action obtain:
domain control, staging deployment approval, target infrastructure route map,
valid certificates at every TLS hop, origin protection and previous artifact.
Deploy assets first, then HTML atomically; run authorized Track C acceptance
against the exact staging origin. Record staged SHA/tree and all results.
Staging pass never makes production approval implicit.

## 4. Production checklist

- Independent exact-head qualification and all release CI gates complete.
- Approved current-main integration result; Phase 4 alone is not that proof.
- Owner security/legal/support/commercial/package decisions resolved or explicitly
  excluded from promised features; domain and deployment authority recorded.
- Product security/cloud qualification complete for shared infrastructure.
- Exact production manifest verified; immutable prior artifact restorable.
- Staging evidence reviewed; no outstanding blocking acceptance failures.
- Publish asset union, verify dependencies, activate HTML atomically.
- Authorized production acceptance verifies deployed bytes, TLS and routing.
- Observe error rates and confirm rollback recovery; record operator and time.

All live items above remain **NOT EXECUTED** in this workstream. No billing,
package, DNS or cloud activation is authorized by this document.

## 5. Reverse-proxy assumptions

Infrastructure owns explicit route precedence: public inventory/discovery/assets
and refund redirect; private product/API routes must never hit a static fallback.
Unknown public route gets readable **404**, never homepage 200. Missing assets
get 404, never HTML 200. GET/HEAD only for public static resources; preserve
product methods/auth/CSRF separately. Preserve status, MIME, redirects, query/path
semantics and cache headers. Never expose private origin address/credentials.
Only allow trusted proxy hops to set forwarded identity/scheme; do not trust
arbitrary client Host/X-Forwarded-* as canonical authority. Infrastructure must
demonstrate private-origin reachability restrictions and LB/edge origin protection.
No deployable proxy config is supplied because approved topology details are absent.

## 6. Cloudflare edge requirements

Full (strict), origin certificate validation, HTTP→HTTPS permanent redirect,
compression with correct Vary handling, no universal cache-everything rule.
Public/private routing and cache separation must be exported as evidence. Do not
apply public CSP to Paddle/auth/product pages; do not mask 401/403/404/5xx with
HTML 200. Use only features approved for the selected plan; no paid-feature
assumption. Cloudflare→LB and LB→private reverse-proxy TLS/trust are separate
evidence gates. No provider setting changed here. See the inherited
[edge contract](../PHASE4_EDGE_AND_RELEASE_CONTRACT.md) for primary references.

## 7. TLS expectations

Public hostname SAN, trusted chain, valid dates, automatic renewal monitoring;
client certificate verification remains on. Verify encryption and hostname
validation at both origin hops according to approved LB design. No self-signed
verification bypass, Flexible mode, insecure curl option or TLS env workaround.
Local fixture tests do not prove TLS, DNS, certificates or private network isolation.

## 8. HSTS staged rollout

After HTTPS/rollback proof, initially `max-age=300`; owner-reviewed progression
to 86400 then 31536000 only after certificate renewal/subdomain risk review.
No includeSubDomains or preload without explicit all-subdomain ownership proof.
Serve HSTS only on HTTPS. HSTS already cached by browsers cannot be immediately
undone by artifact rollback; retain HTTPS during incidents. Do not combine a
short website rollback with a claim of instant transport-policy rollback.

## 9. Cache policy

HTML/error/unversioned resources: no-cache/revalidate. Discovery: public
max-age=300. Private product responses: private,no-store and no shared cache.
Maintenance: 503,no-store,Retry-After. Do not edge-cache personalized HTML,
Set-Cookie or authenticated responses. Verify both origin and edge response
headers and shared-cache behavior after deployment; local header fixtures are
only a contract. Preserve MIME/nosniff and explicit public CSP.

## 10. Immutable asset policy

Hash-named JS/CSS/fonts: public,max-age=31536000,immutable. Retain old/new asset
union before selecting new HTML and throughout rollback/client compatibility
window. Same URL must not acquire different bytes. Unversioned logo/font assets
must remain byte-compatible or become separately versioned before activation.
No asset garbage collection is part of this package. Owner defines retention
duration only after longest cache/open-tab window and rollback requirements.

## 11. Maintenance mode

Existing `maintenance.html` is only a prepared artifact. Operator must serve it
with 503, no-store, Retry-After, noindex and accessible retry guidance, without
claiming effect success or leaking traces. Never redirect private/API failures
to maintenance HTML. Require authorized tests of status/cache/header behavior
and recovery; no actual maintenance toggle or cloud command is implemented here.

## 12. Rollback procedure

Stop activation if any manifest/hash/header/privacy/routing/asset/TLS check fails.
Keep evidence before recovery; select prior qualified HTML/artifact atomically
without deleting either asset generation. Revalidate prior manifest/routes/assets
and private isolation; restore prior discovery metadata where changed. Any edge
cache invalidation/config rollback is a reviewed infrastructure-owner action,
not an assumed provider command. Do not git-reset/rewrite the qualified history,
rebuild an old release with new dependencies, or treat rollback as DB migration.
Record trigger, prior/next SHA/tree, operator, elapsed recovery and residual risk.

### Proposed release directories and atomic-pointer strategy

The following is a **relative contract, not installed infrastructure**. The
infrastructure owner chooses the private-origin base directory and permissions.

```text
website-root/
  releases/<exact-source-sha>/public/   # complete verified website bytes
  releases/<exact-source-sha>/evidence/ # private sidecar/report, not web-served
  shared/assets/                      # verified old/new immutable asset union
  current -> releases/<current-sha>/public
  previous -> releases/<prior-sha>/public
```

Serve `/static/whitepact/assets/` from the approved retained union, public routes
and discovery from `current`, and evidence from **nowhere public**. Keep each
release directory immutable after byte verification. Choose a different
environment root for staging, never a pointer into production. Symlinks here are
an operator-owned routing mechanism; symlinks **inside uploaded artifacts** remain
prohibited by the verifier.

If the platform uses POSIX filesystem pointers, prepare a new symlink in the same
directory/filesystem and atomically rename it over `current`; do not unlink the
existing pointer before replacement. First compare actual current target with
the expected prior release, serialize operator activations and stop on mismatch.
The prepared target must already exist and verify. Record previous target before
activation. This is a strategy, not a shell activation script. The chosen
filesystem/proxy must prove atomic rename semantics and status preservation.
Multiple origin instances are not globally atomic: infrastructure must drain or
coordinate them, prove release convergence, and retain assets valid under mixed
old/new HTML. A single symlink swap does not prove a multi-instance deployment.

### Failed-deployment and previous-release restoration states

| Failure point | Required action | Proof before continuing |
|---|---|---|
| Build/manifest/upload/dependency check before switch | Leave `current` unchanged; no cleanup of prior release/assets | Prior route+digest verification; failed phase record |
| Current target differs from expected prior | Stop; do not overwrite another operator's activation | Actual serving targets and authoritative deployment decision |
| Failure after switch on any instance | Restore the recorded prior pointer using atomic replacement on all serving instances; retain union assets | Prior artifact/route/header checks and convergence across instances |
| State or proxy/cache convergence unknown | Stop rollout; approved public-only maintenance if needed; product/API routes unaffected | Infrastructure owner resolves actual serving state; no optimistic success |

Prior restore uses retained qualified bytes, never a new build of old source.
Record current pointer, prior pointer, immutable release identities and manifest
digests before/after. Actual symlink switch, cache operation or proxy reload is
not performed by this workstream. No cleanup command is supplied.

## 13. Post-deployment smoke test

Commands below are **prepared only** and require separate explicit target approval:

```sh
BASE_URL=https://staging.whitepact.com EXPECTED_SITE_ORIGIN=https://staging.whitepact.com node web/tooling/launch-contract.mjs smoke --staging
BASE_URL=https://whitepact.com EXPECTED_SITE_ORIGIN=https://whitepact.com node web/tooling/launch-contract.mjs smoke
BASE_URL=https://whitepact.com npm run audit:website-postdeploy
```

Run the finalized Track C harness when available in addition to these inherited
checks. It must verify actual deployed release bytes, all 15 routes/404/redirects,
private separation, discovery, headers, TLS, accessibility and degraded modes.
Compare downloaded asset digests to qualified manifest. Do not claim field CWV
or real rollback from local preview/lab checks. No external command above ran here.

## 14. Emergency rollback test

Safe offline rehearsal (no network, activation, copies or deletion):

```sh
node --test tests/js/website-deployment-package.test.mjs
node web/tooling/deployment/package.mjs rehearse /absolute/prior/artifact /absolute/prior/manifest.json /absolute/next/artifact /absolute/next/manifest.json
```

This validates asset union, collision rejection and old/new HTML references.
It deliberately reports `infrastructureRollbackProven:false`. Later authorized
staging rehearsal must introduce a controlled missing-asset or acceptance
failure, restore prior deployment, prove recovery of every route/asset/header
and measure operator recovery. Do not intentionally break production. A fixture
PASS is never a real infrastructure rollback PASS.

## 15. Release evidence template

Use [RELEASE_EVIDENCE_TEMPLATE.md](RELEASE_EVIDENCE_TEMPLATE.md). Every unexecuted
item is PENDING/NOT VERIFIED, never implied PASS. Record external/owner approval
separately from local engineering results; redact infrastructure secrets and
personal information. Independent review is not SOC 2/ISO certification.

Deterministic **offline** evidence generation, with the same verified old/new
inputs as rollback rehearsal:

```sh
node web/tooling/deployment/package.mjs evidence /absolute/prior/artifact /absolute/prior/manifest.json /absolute/next/artifact /absolute/next/manifest.json
```

This emits JSON on stdout only; it performs no writes or network requests.
It contains exact verified identities, canonical-JSON manifest digests, proposed
relative release layout, failure recovery and local reference-check results.
It deliberately marks every external/owner activation check `NOT VERIFIED` and
`deploymentAuthorized:false`. Manifest digest encoding is explicitly named and
must not be mistaken for raw sidecar-byte SHA-256. Operators may retain the
output outside the public artifact after approval; an independent expected
manifest is still required. No wall-clock deployment timestamp is invented.

## Track B verification record

See [LOCAL_PACKAGE_EVIDENCE.md](LOCAL_PACKAGE_EVIDENCE.md) for fresh offline test
results. This package changes no qualified Phase 4 files, cloud state or product
runtime behavior and is not a deployment approval.
