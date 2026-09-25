# WhitePact v1.3.1 — immutable release baseline

| Field | Value |
|-------|-------|
| **Release tag** | `v1.3.1` (annotated, pushed to `origin`) |
| **Tag message** | WhitePact v1.3.1 — Enterprise Hardened Release |
| **Tag verification** | `git rev-parse v1.3.1^{}` → `894efe30514553f7e0d047a1569a80d36c53a236` (must match merge commit) |
| **Tag object type** | Annotated (`git cat-file -t v1.3.1` → `tag`) |
| **Cryptographic tag signature** | **Not present** (`git tag -v v1.3.1` → `no signature found`) |
| **Approved release signer** | **Not verified** — tagger `Cursor Agent <cursoragent@cursor.com>`; see `security/release-signers.allowed` + `docs/VERIFY_RELEASE.md` § signed Git tag |
| **SHA immutability anchor** | Annotated tag `v1.3.1` on merge commit `894efe3`; do not move or overwrite |
| **Main merge commit** | `894efe30514553f7e0d047a1569a80d36c53a236` |
| **Main tree SHA** | `06ac20f6f0f88585770437e23d2d329ead104fab` |
| **PR** | [#114](https://github.com/Guruprasath-Annadurai/Whitepact/pull/114) — **MERGED** |
| **PR source HEAD (verified RC)** | `c85c9d1e3a4d9f393af490215e7080941f977d8d` |
| **Merge timestamp (UTC)** | 2026-09-25T12:00:20Z |
| **Merge strategy** | GitHub **merge commit** (`--merge`) |
| **Version (`pyproject.toml`)** | **1.3.1** |

## Release-freeze decision

| Item | Status |
|------|--------|
| PM release-freeze | **GO** |
| Phase 0C verdict | **WHITEPACT PHASE 0C PASS — READY FOR RELEASE FREEZE** |
| Exact-head PR #114 CI | **PASS** (pre-merge, SHA `c85c9d1`) |
| Exact merge-commit `main` CI | **PASS** (workflow `36132481255`, SHA `894efe3`) |

## Governance invariants (unchanged)

| Invariant | Value |
|-----------|--------|
| `PRODUCTION_GATE_B_OPEN` | **False** |
| Phase7A dispatcher default | **off** (`phase7a_dispatcher_enabled` default `False`) |
| MCP production tools | **30** |
| Alembic migration head | **0061** (`0061_sovereign_shadow_observations`) |

## Container security (Phase 0C)

| Metric | Post-remediation image |
|--------|-------------------------|
| CRITICAL | **0** (runtime `apt-get upgrade` in `Dockerfile`) |
| HIGH / MEDIUM | Documented residual inherited OS findings — see `WHITEPACT_V131_95_FINAL_CONTAINER_SECURITY_CLOSURE.md` |

## Test / evidence (release candidate)

- Phase 0B/0C operational evidence on branch through `c85c9d1` / `ff3f127`
- 30m instrumented soak: 11517 requests, 0 errors (`WHITEPACT_V131_95_FINAL_INSTRUMENTED_SOAK.md`)
- HTTP replica + concurrency: `test_v1_two_process_replicas.py` PASS; harness reports on branch
- MCP Streamable HTTP + STDIO interop evidence on branch
- Full regression: **main merge-commit CI green** (Python 3.11/3.12, frontend, Helm, a11y, i18n, CodeQL, OpenSSF, reproducible build, Bandit, etc.)

## Tag provenance (consumer verification)

```bash
git fetch origin tag v1.3.1
git rev-parse v1.3.1^{}          # expect 894efe30514553f7e0d047a1569a80d36c53a236
git cat-file -t v1.3.1           # expect tag (annotated)
git tag -v v1.3.1                # expect: no signature found (unsigned annotated tag)
```

Per `compliance/SIGNED_VERSION_TAGS.md`, **signed** annotated tags from an approved maintainer are required for full release-intent verification. This freeze used an **unsigned** annotated tag created in the cloud release path. Artifact attestation (Sigstore / reusable builder), when published for `v1.3.1`, remains the independent supply-chain check documented in `docs/VERIFY_RELEASE.md`.

## Known non-blocking external limitations

Carried forward from Phase 0B/0C (not software defects on this baseline):

- **Tag signing / approved-signer gate** — `v1.3.1` is annotated but unsigned; maintainers may add a separately signed release-intent record without moving the tag SHA (policy follow-up per `RELEASING.md`)
- Paddle sandbox E2E (no final credentials in closure environment)
- Live Kubernetes multi-replica certification
- Mailpit/MailHog email capture E2E
- External customer pilots and production regional DR history

## Formula Ω∞

**WHITEPACT FORMULA Ω∞ IMPLEMENTATION UNBLOCKED** — V1.3.1 is merged, tagged, and baselined. Formula work must use a **new** branch from this `main` / `v1.3.1` baseline (`feature/whitepact-formula-omega-v0.1`), not PR #114.
