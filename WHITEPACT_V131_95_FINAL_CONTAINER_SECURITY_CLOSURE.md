# Final container security closure (Phase 0C)

## BEFORE (`responsibleai:phase0c-candidate`)

| Severity | Count |
|---|---:|
| CRITICAL | 3 |
| HIGH | 65 |
| MEDIUM | 0 |

## AFTER (`responsibleai:phase0c-patched` / tagged `responsibleai:95test`)

| Severity | Count |
|---|---:|
| CRITICAL | 0 |
| HIGH | 52 |
| MEDIUM | 81 |

## All CRITICAL findings (before) and disposition

| CVE | Package | Installed | Fixed | Disposition (after) | Reachability |
|---|---|---|---|---|---|
| CVE-2026-13221 | perl-base | 5.40.1-6 | 5.40.1-6+deb13u1 | **FIXED** | NOT_REACHABLE — perl-base is Debian base metadata; WhitePact runtime is Python/uvicorn and does not execute Perl. Remediated via apt-get upgrade in Dockerfile runtime stage. |
| CVE-2026-42496 | perl-base | 5.40.1-6 | 5.40.1-6+deb13u1 | **FIXED** | NOT_REACHABLE — perl-base is Debian base metadata; WhitePact runtime is Python/uvicorn and does not execute Perl. Remediated via apt-get upgrade in Dockerfile runtime stage. |
| CVE-2026-8376 | perl-base | 5.40.1-6 | 5.40.1-6+deb13u1 | **FIXED** | NOT_REACHABLE — perl-base is Debian base metadata; WhitePact runtime is Python/uvicorn and does not execute Perl. Remediated via apt-get upgrade in Dockerfile runtime stage. |

**Release-freeze rule:** residual CRITICAL count after patch = **0**. Residual HIGH findings documented in `WHITEPACT_V131_95_CONTAINER_SECURITY_REPORT.md`.
