# Container image scan evidence

Scanner: Trivy 0.58.1 (`aquasec/trivy@sha256:ab70a02200597efa04748f210f793936eb647cbcdb0ea69cc30b226d6f5a22c7`),
run locally on 2026-10-11 against images built from this branch; the same command is now a CI job
(`container-scan`, not yet a required check). Vulnerability database as of the scan day.

| Image | Before | After |
|---|---|---|
| `Dockerfile` (hosted service) — Debian 13.7 | 0 fixable HIGH/CRITICAL | unchanged |
| `Dockerfile.isolation` (isolated tool runtime) — Debian 13.6 | **3 CRITICAL + 17 HIGH fixable** (perl-base, libpcre2, openssl 3.5.6, gzip, sqlite) | **0** after adding `apt-get upgrade` before the privilege drop |

The isolation image is the one that runs governed tools; it previously had no OS update step, unlike the main
image. The runtime still has no network and no credentials, and the image still imports `responsibleai` as
uid 65534 with `--network none`.

## What the gate does and does not claim
* CI fails on any HIGH/CRITICAL vulnerability **that has a fixed version available** (`--ignore-unfixed`).
* **Unfixed** findings are not gated. The hosted image reports 54 unfixed HIGH OS-package findings in Debian 13.7
  (no upstream fix at scan time). No reachability analysis was performed; they are *known and unassessed*, not
  "not exploitable".
* A scan is a point-in-time result: a clean scan today says nothing about next week's advisories. The scan
  runs on pull requests and pushes only; there is **no scheduled rescan** of published images.
* `apt-get upgrade` at build time means the image is not bit-for-bit reproducible; the reproducible-build check
  covers the wheel/sdist, not the images.
* The images are scanned for vulnerabilities only (no secret/misconfiguration scan, no SBOM-based re-scan).

## npm
`npm audit --audit-level=high` for `sdk/typescript` and `web`: 0 vulnerabilities on 2026-10-11; now a CI step.
