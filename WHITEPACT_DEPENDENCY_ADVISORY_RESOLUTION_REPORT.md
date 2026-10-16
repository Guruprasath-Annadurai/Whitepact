# WHITEPACT — DEPENDENCY & SUPPLY CHAIN ADVISORY RESOLUTION REPORT

**Document ID:** WP-M12S-SUPPLY-012  
**Classification:** SUPPLY CHAIN SECURITY & VULNERABILITY AUDIT  
**Date:** 2026-10-15  
**Audience:** Security Architects, Release Engineers, Compliance Auditors  
**Status:** **AUDITED, MITIGATED, AND QUALIFIED**

---

## 1. BACKGROUND & SCOPE

During prior milestone reviews and GitHub security scanning, four specific dependency advisories were identified for independent review:
1. `Mako`
2. `multidict`
3. `source-map-js`
4. `nltk`

This document details the exact version verification, reachability analysis, and formal security disposition for each item.

---

## 2. DETAILED ADVISORY AUDIT & DISPOSITION

### 2.1 Mako (Python Template Engine)
- **Reported Advisory:** Alert #23 (GHSA-advisory regarding template sandbox bypass in Mako $\le 1.4.2$).
- **Installed Version:** `1.4.3` (`uv pip list` confirms `mako==1.4.3`).
- **Reachability Analysis:** Mako is utilized by Alembic for generating database migration scripts during development. It is never exposed to untrusted user input or network-facing template rendering.
- **Disposition:** **RESOLVED.** Version 1.4.3 contains the official upstream vendor fix. Zero residual exposure.

---

### 2.2 multidict (Async Key-Value MultiDict)
- **Reported Advisory:** Alert #22 (Historical buffer / denial-of-service advisory in older releases).
- **Installed Version:** `6.9.1` (`uv pip list` confirms `multidict==6.9.1`).
- **Reachability Analysis:** Utilized by `aiohttp` / `httpx` underlying transports.
- **Disposition:** **RESOLVED.** Version 6.9.1 is a modern, actively supported release free from open advisories.

---

### 2.3 source-map-js (Web Frontend JavaScript Library)
- **Reported Advisory:** Alert #24 (Vulnerability in `source-map-js` $\le 1.2.1$).
- **Resolved Package Version:** `1.2.2` (Verified in `web/package-lock.json` lines 3823-3825: `source-map-js-1.2.2.tgz`).
- **Audit Execution:** Production `npm audit` reports zero vulnerabilities for `source-map-js`.
- **Disposition:** **RESOLVED.** Upgraded to patched release 1.2.2.

---

### 2.4 NLTK (Natural Language Toolkit)
- **Reported Advisories:**
  - Alert #2 (GHSA-8mgp-746c-j5xp / CVE-2026-12243 / PYSEC-2026-597)
  - CVE-2026-81726 / PYSEC-2026-3740
- **Upstream Status:** As of October 2026, certain path-traversal / model-path loading vulnerabilities remain unpatched upstream in NLTK when loading untrusted custom models.
- **WhitePact Architecture & Reachability:**
  1. **Not Installed in Default Environment:** NLTK is declared exclusively under the optional `sentiment` extra in `pyproject.toml` (`sentiment = ["nltk>=3.10.0"]`). The core WhitePact platform, control plane, and API runtime do not install or import NLTK.
  2. **Isolated Callsite:** The only callsite in the entire codebase is inside `src/biasbuster/core/scoring.py` for VADER sentiment scoring. It passes a hardcoded string literal `"vader_lexicon"` to `nltk.download()`. It never invokes the vulnerable model-artifact import/export or `data.load()` APIs with user-supplied paths.
  3. **Zero Runtime Downloads:** Production scoring utilizes bundled static lexicons; runtime downloads are disabled.
- **Enforced Security Policy:**
  - Production deployments must strictly exclude the optional `[sentiment]` extra (`uv sync --no-extra sentiment` or Docker runtime without sentiment).
  - Any tenant requiring sentiment scoring must run it in an isolated container backend with no filesystem write access.
- **Disposition:** **ISOLATED & CONTROLLED.** Default distributions are completely unexposed.

---

## 3. SUPPLY CHAIN GOVERNANCE INVARIANTS

1. **Deterministic Lockfiles:** All Python dependencies are pinned with exact hashes.
2. **Automated Audit Gates:** Pre-commit and CI/CD pipelines run `pip-audit` and `npm audit` on every PR.
3. **Zero Direct Internet Package Installs in Production:** Production Docker containers are pre-baked; runtime `pip install` or `npm install` is blocked by network egress policy.
