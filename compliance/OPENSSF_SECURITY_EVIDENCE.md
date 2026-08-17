# OpenSSF Best Practices — Security Criteria Evidence

**Date**: 2026-08-17
**Scope**: the 16 OpenSSF Best Practices Badge security criteria this remediation pass was asked to make truthfully eligible, plus `dynamic_analysis` (added the same day after a review correctly flagged that the coverage number initially cited for it was blended statement+branch coverage, not pure branch coverage — see `compliance/OPENSSF_DYNAMIC_ANALYSIS.md`). Each status below reflects real code/tests/documentation inspected during this pass — see `compliance/OPENSSF_SECRET_SCAN.md` for the full secret-scan methodology and results referenced in `no_leaked_credentials`.

---

### know_secure_design
**STATUS: MET**
**EVIDENCE**:
- `THREAT_MODEL.md` — STRIDE-structured attack-surface analysis of the whole system.
- `ENFORCEMENT_BOUNDARY.md` — precisely states where each governance primitive's authority stops (inline enforcement vs. voluntary chokepoint), so security claims aren't overstated.
- `DETERMINISTIC_VS_PROBABILISTIC.md` — documents why every governance decision is deterministic code, never an LLM call, as a deliberate security design choice.
- `MACHINE_AUTHORITY_V1.md` — documents the authority-attenuation, delegation-graph, and org-ceiling invariants as designed security controls, with their own scope limits stated.

### know_common_errors
**STATUS: MET** (closed during this pass)
**EVIDENCE**:
- `CONTRIBUTING.md`, new "Common vulnerability classes to avoid" section (this pass) — SQL injection, SSRF, authz bypass, weak-key acceptance, secret timing/logging, each with the specific in-repo control a contributor should reuse.
- Previously existing but not centrally documented: SSRF guard (`webhooks/manager.py::validate_webhook_url`), parameterized SQLAlchemy queries throughout `db/`, `Depends(require_role(...))` on every authenticated endpoint.

### crypto_published
**STATUS: MET**
**EVIDENCE**: Every cryptographic primitive in this codebase is a standard, published algorithm via an established library — Fernet (AES-128-CBC+HMAC, `cryptography`), RSA/EC signature verification (`PyJWT[crypto]`), HMAC-SHA256 (stdlib `hmac`+`hashlib`), TOTP/RFC 6238 (`pyotp`). No bespoke/homegrown cryptographic construction exists anywhere in `src/`.

### crypto_call
**STATUS: MET**
**EVIDENCE**: All cryptographic operations are calls into `cryptography`, `PyJWT`, `pyotp`, or stdlib `hmac`/`hashlib`/`secrets` — verified by the `crypto_weaknesses` grep sweep below finding zero hand-rolled cryptographic code (no custom cipher, no custom PRNG, no custom hash construction).

### crypto_floss
**STATUS: MET**
**EVIDENCE**: `cryptography`, `PyJWT`, `pyotp` are all FLOSS (BSD/MIT/Apache-2.0-family licensed, source-available on PyPI/GitHub) — no proprietary or closed-source cryptographic dependency.

### crypto_keylength
**STATUS: MET** (real gaps closed during this pass)
**EVIDENCE**:
- **WhitePact-generated secrets** (already correct by construction, audited, unchanged): API keys via `secrets.token_urlsafe(32)` (256 bits, `db/org_repository.py::_generate_raw_key`); TOTP seeds via `pyotp.random_base32()` (`auth/mfa.py`); Fernet keys via `cryptography.fernet.Fernet.generate_key()`, whose constructor itself rejects any malformed/wrong-length key (`db/encryption.py`).
- **Real gap found and closed**: `WebhookCreateRequest.secret` (`dashboard/app.py`) previously had `max_length=256` but **no minimum**, meaning a 1-character HMAC-SHA256 signing secret was silently accepted. Fixed with `auth/crypto_policy.py::validate_webhook_secret()` (32-character floor, NIST SP 800-107-derived, empty string still allowed as an explicit "unsigned" choice) wired in via a Pydantic `field_validator`.
- **Real gap found and closed**: `auth/oidc.py::OIDCProvider.validate_token()` accepted any RSA key size from a JWKS endpoint with no floor. Fixed with `auth/crypto_policy.py::validate_rsa_key_size()` (2048-bit NIST floor), called immediately after the existing private-key-rejection check.
- **Tests**: `tests/test_crypto_policy.py` — 12 tests, including two end-to-end tests (`TestOIDCProviderRejectsWeakJWKSKey`) that sign a real JWT with a real 1024-bit RSA key, serve it through a mocked JWKS response, and confirm `validate_token()` itself rejects it (not just the standalone policy function in isolation) — and a matching test proving a real 2048-bit key still passes and verifies correctly. `tests/test_dashboard_api.py::TestWebhooksAPI` — 3 new tests covering weak/empty/strong webhook secrets through the real HTTP endpoint.

### crypto_working
**STATUS: MET**
**EVIDENCE**: All 2035 tests pass (`python3 -m pytest`), including the pre-existing hash-chain integrity tests (`EvidenceRepository`, `AuditRepository`), signature verification tests, and the new key-size/secret-strength tests above — proving the cryptographic code paths function correctly, not just exist.

### crypto_weaknesses
**STATUS: MET**
**EVIDENCE**: Full-repository grep sweep for `MD4|MD5|SHA1|SHA-1|DES|3DES|RC4|ECB|Dual_EC_DRBG` in `src/responsibleai/` found **zero** literal usages of any weakened primitive in application code.
- **One real, documented, justified exception**: `auth/mfa.py`'s TOTP implementation uses `pyotp`'s default digest, HMAC-SHA1 — classified **PROTOCOL/INTEROPERABILITY_REQUIREMENT**, not a weakness. Full rationale added to `auth/mfa.py`'s module docstring (this pass): HMAC-SHA1's security as a keyed PRF is independent of SHA-1's separate, unrelated collision-resistance weakness (NIST SP 800-107 rev. 1 §5.1 still approves HMAC-SHA1 as a MAC construction); RFC 6238 mandates SHA1 as the default and the large majority of real-world authenticator apps (Google Authenticator among them) never implemented the optional SHA256/SHA512 algorithm parameter, so changing the default would silently lock out existing enrolled users. Scope-limited: every *other* keyed/signing use in this codebase (webhook delivery signing) already uses HMAC-SHA256.
- **Regression tests added** (`tests/test_mfa.py::TestDigestAlgorithm`, 3 tests): lock in that TOTP deliberately uses SHA1 (not a digest-agnostic accident) — a code computed with SHA256 is proven to *not* verify against a SHA1-enrolled secret, and vice versa.

### crypto_pfs
**STATUS: MET** (closed during this pass)
**EVIDENCE**:
- **Production, verified empirically, not assumed**: connected directly to `whitepact.com:443` with Python's `ssl` module during this review — negotiated **TLS 1.3**, cipher `TLS_AES_256_GCM_SHA384`. TLS 1.3 removed static (non-ephemeral) key exchange from the protocol entirely, so this is PFS by construction, not a configuration choice that could silently regress.
- **Outbound calls this codebase makes** (`auth/oidc.py`'s JWKS fetch, `webhooks/manager.py`'s delivery POSTs) use Python's default `ssl` context, whose `minimum_version` was confirmed (`ssl.create_default_context().minimum_version`) to already exclude TLS 1.0/1.1 — no non-PFS legacy protocol is reachable via this codebase's own HTTP client configuration.
- **Self-hosted deployer guidance, previously silent, now explicit**: `DEPLOYMENT.md`'s nginx example now states `ssl_protocols TLSv1.2 TLSv1.3;` and an explicit PFS-only (`ECDHE-*`) cipher list, rather than relying on whatever a given nginx/OpenSSL build happens to default to. `ENTERPRISE_SECURITY.md`'s encryption-in-transit section cross-references both the verified production evidence and this explicit deployer requirement.

### crypto_password_storage
**STATUS: N/A**
**EVIDENCE**: This codebase stores no human-memorized passwords anywhere — confirmed by a full grep for `bcrypt|argon2|scrypt|pbkdf2|password_hash` across `src/responsibleai/`, all zero matches. Authentication is exclusively via high-entropy API keys (256-bit, `secrets.token_urlsafe(32)`) hashed with a single SHA-256 pass (`db/org_repository.py::_hash_key`) — correct and sufficient specifically *because* the input already carries 256 bits of CSPRNG entropy; a slow/salted KDF (bcrypt/argon2) is the requirement for low-entropy human-memorized passwords, which this system does not have.

### crypto_random
**STATUS: MET**
**EVIDENCE**: Full grep sweep for `import random`/`from random import`/`random.random()`/`random.choice()`/etc. across `src/responsibleai/` returned **zero** matches. Every secret-generation call site uses a CSPRNG: `secrets.token_urlsafe()` (API keys, backup codes), `secrets.choice()` (backup code alphabet), `pyotp.random_base32()` (internally `os.urandom`-backed), `Fernet.generate_key()` (internally `os.urandom`-backed). The one `random.random()` usage found in the whole repository is in `examples/05_cost_intelligence.py`, a non-security demo weighting a synthetic model-mix distribution — pre-existing, unrelated, confirmed `NON_SECURITY_USE`.

### delivery_mitm
**STATUS: MET**
**EVIDENCE**: Source is delivered exclusively via `git` over HTTPS/SSH (GitHub) and published packages via `pip install` from PyPI over HTTPS with trusted publishing (`RELEASING.md`) — no HTTP-only or unauthenticated delivery channel exists for this project's own artifacts.

### delivery_unsigned
**STATUS: MET**
**EVIDENCE**: `.github/workflows/publish.yml` — PyPI trusted publishing (no long-lived secret token) plus Sigstore-backed, GitHub-attested build provenance via `actions/attest-build-provenance@v2`, verifiable with `gh attestation verify <file> --owner <repo-owner>` per the workflow's own documented instructions.

### vulnerabilities_fixed_60_days
**STATUS: MET**
**EVIDENCE**: `SECURITY.md` commits to acknowledgement within 48 hours and "a resolution timeline within 7 days" for any reported vulnerability — stricter than OpenSSF's 60-day suggestion. Demonstrated in practice during this pass: `cryptography` 49.0.0 (PYSEC-2026-3552) and `nltk` 3.9.4 (PYSEC-2026-3582/3583/3584) were found via `pip-audit`, upgraded to fixed versions (`cryptography>=50.0.0`, `nltk>=3.10.0`), and verified via the full test suite (2035/2035 passing, plus targeted `tests/test_scoring.py`/`tests/test_gender_bias.py` for the nltk-dependent code path) — same day as discovery, not a 60-day gap.

### vulnerabilities_critical_fixed
**STATUS: MET**
**EVIDENCE**: Same evidence as `vulnerabilities_fixed_60_days` above — no distinct "critical" triage tier exists in `SECURITY.md`, but the stated 7-day commitment applies to every report without exception, which necessarily covers critical findings at least as fast.

### dynamic_analysis
**STATUS: NOT YET MET**
**EVIDENCE / GAP**: See `compliance/OPENSSF_DYNAMIC_ANALYSIS.md` in full. This project's automated test suite (2035 tests, `pytest`) is the dynamic-analysis path OpenSSF's criterion accepts (vs. a fuzzer or web scanner) — but the ≥80% bar is specifically **branch** coverage, `covered_branches / num_branches`, isolated from statement coverage. Measured directly via `coverage.json` (not `coverage.py`'s own blended terminal percentage, which reads 84.89% and would have been an overclaim if cited as branch coverage): **72.82%** (1334/1832 branches) — 7.18 points below threshold. Tooling to measure and report this correctly is now permanent (`--cov-branch` in `pyproject.toml`'s `addopts`, `scripts/check_branch_coverage.py`, a CI step printing the real number every run) — the coverage percentage itself has not been artificially inflated to close the gap, and closing it for real requires new tests targeting the specific uncovered conditional branches (concentrated in `dashboard/app.py` and `mcp/tools.py`), not done in this pass.

### no_leaked_credentials
**STATUS: NOT YET MET**
**EVIDENCE**: See `compliance/OPENSSF_SECRET_SCAN.md` in full. **Git history itself is clean** — gitleaks scanned all 294 reachable commits across all branches/tags, found 12 hits, all confirmed documentation placeholders (`your-key-here`, `owner-key`, `abc123def456...`), zero real credentials. **What keeps this NOT YET MET**: a real, live production database password (Supabase Postgres) was pasted into this session's chat transcript and typed into the founder's local shell history during today's live-debugging work — outside git, but a real credential exposure per the honest spirit of this criterion. Rotation was recommended twice during that session but has not been confirmed complete as of this document. This criterion should not be marked MET until the founder confirms the Supabase database password has actually been rotated.

---

## Summary table

| Criterion | Status |
|---|---|
| know_secure_design | MET |
| know_common_errors | MET |
| crypto_published | MET |
| crypto_call | MET |
| crypto_floss | MET |
| crypto_keylength | MET |
| crypto_working | MET |
| crypto_weaknesses | MET |
| crypto_pfs | MET |
| crypto_password_storage | N/A |
| crypto_random | MET |
| delivery_mitm | MET |
| delivery_unsigned | MET |
| vulnerabilities_fixed_60_days | MET |
| vulnerabilities_critical_fixed | MET |
| dynamic_analysis | **NOT YET MET** (72.82% real branch coverage, need 80%) |
| no_leaked_credentials | **NOT YET MET** (pending founder confirmation of DB password rotation) |

**14 MET, 1 N/A, 2 NOT YET MET (of 17 criteria) — 15 of 17 eligible. Remaining two are real, disclosed gaps, not overclaims: `dynamic_analysis` needs genuine additional branch-coverage tests (~7 points, concentrated in `dashboard/app.py`/`mcp/tools.py`); `no_leaked_credentials` needs the founder's confirmation that the Supabase DB password has been rotated.**
