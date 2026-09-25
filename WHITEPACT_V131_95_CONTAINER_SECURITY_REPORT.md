# Container security scan (Phase 0B)

**Image:** `responsibleai:95test`

**Scanner:** Trivy 0.57.1 (Docker)

**Verdict:** **PARTIAL** — scan complete; majority of HIGH findings are inherited Debian base packages (`curl`, `util-linux`) without fixed versions in the current base image. Assess reachability per deployment (runtime user, attack surface).

| Severity | Count |
|---|---:|
| CRITICAL | 3 |
| HIGH | 65 |
| MEDIUM | 104 |

## Sample CRITICAL/HIGH (not suppressed)

| Sev | CVE | Package | Installed | Fixed | Target |
|---|---|---|---|---|---|
| HIGH | CVE-2026-76642 | bsdutils | 1:2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78408 | bsdutils | 1:2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78409 | bsdutils | 1:2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78410 | bsdutils | 1:2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-12064 | curl | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8286 | curl | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8458 | curl | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8927 | curl | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-41992 | gzip | 1.13-1 | 1.13-1+deb13u1 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-54369 | libacl1 | 2.3.2-2+b1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-76642 | libblkid1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78408 | libblkid1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78409 | libblkid1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78410 | libblkid1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-12064 | libcurl4t64 | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8286 | libcurl4t64 | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8458 | libcurl4t64 | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-8927 | libcurl4t64 | 8.14.1-2+deb13u5 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-76642 | liblastlog2-2 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78408 | liblastlog2-2 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78409 | liblastlog2-2 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78410 | liblastlog2-2 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-76642 | libmount1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78408 | libmount1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78409 | libmount1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78410 | libmount1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2025-69720 | libncursesw6 | 6.5+20250216-2 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-86145 | libpcre2-8-0 | 10.46-1~deb13u1 | 10.46-1~deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-89157 | libpcre2-8-0 | 10.46-1~deb13u1 | 10.46-1~deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-89161 | libpcre2-8-0 | 10.46-1~deb13u1 | 10.46-1~deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-76642 | libsmartcols1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78408 | libsmartcols1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78409 | libsmartcols1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-78410 | libsmartcols1 | 2.41.5-0+deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-11822 | libsqlite3-0 | 3.46.1-7+deb13u1 | 3.46.1-7+deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-11824 | libsqlite3-0 | 3.46.1-7+deb13u1 | 3.46.1-7+deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-14456 | libssl3t64 | 3.5.6-1~deb13u2 | 3.5.7-1~deb13u2 | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-16742 | libsystemd0 | 257.13-1~deb13u1 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2025-69720 | libtinfo6 | 6.5+20250216-2 | — | responsibleai:95test (debian 13.6) |
| HIGH | CVE-2026-16742 | libudev1 | 257.13-1~deb13u1 | — | responsibleai:95test (debian 13.6) |

Full JSON: `/opt/cursor/artifacts/v131_95_phase0b/trivy_responsibleai_95test.json`
