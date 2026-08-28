# Phase 0 — Enterprise Neural: Repository Reality Audit

STATUS: Audit complete. No code changed by this phase. This document is
evidence, not a plan — every claim below is anchored to a file, doc, or
grep result observed on 2026-08-28 against `main` @ commit `9dcdc1b`.

## 0. Relationship to the in-progress Production Integration initiative

**Critical finding first, because it changes how everything below should be
read.** A separate, already-approved 20-phase initiative — "Heart →
WhitePact Production Integration" (`docs/heart-production/`) — is
mid-execution: Phase 0 (audit) and Phase 1 (`AuthorityGrant`) and Phase 2
(`identity_authority_adapter.py`) are merged; Phase 3 (Authority
Persistence) is next. That initiative's own Phase 6 ("wire Heart into the
live decision path") and its later phases (MCP integration, execution
permits, revocation, evidence) are **the same work** this new directive
calls Phase 9 ("Heart Authority Production Integration") and parts of
Phases 10 and 12.

Recommendation (per your decision to merge): treat
`docs/heart-production/`'s remaining phases (3–20) as the concrete
implementation of this directive's Phase 9, rather than re-deriving Heart
production wiring under a second, parallel doc tree. This audit therefore
scopes this directive's own Phase 0 deliverables to the parts that are
genuinely new: neural/BCI (Phases 4–8, 15), and the security-foundation
phases (1–3, 11–14, 16–18) that apply platform-wide, not just to Heart.

## 1. Current architecture map (what exists today)

- **Governance/Heart core** (`src/responsibleai/governance/`, 40 modules):
  constitution, authority lattice, root authority, consent proof, purpose
  binding, delegation kernel, non-delegable authority, authority lifetime,
  revocation kernel, conflict resolver, heart veto, legitimacy envelope,
  sovereignty kernel (H1–H13); `authority_grant.py`,
  `identity_authority_adapter.py` (Production Integration Phase 1–2).
  `WhitePactRuntimeGateway.evaluate()` is the canonical decision point
  (`governance/gateway.py:169`).
- **Identity/auth**: `auth/oidc.py` (OIDC JWT validation via JWKS),
  `auth/verifiable_credential.py` (VC-JWT bearer), `db/org_repository.py`
  (`authenticate()`, static API-key hash lookup). Three real credential
  sources; no fourth exists.
- **Persistence**: `db/` — 25 repository modules over SQLAlchemy,
  Alembic migrations (`migrations/versions/`, latest `0029`), SQLite
  (self-hosted default) or PostgreSQL (`RAI_DATABASE_URL`, recommended).
- **MCP transports**: stdio, Streamable HTTP `/mcp`, legacy HTTP+SSE —
  `src/responsibleai/mcp/server.py`. OAuth/OIDC resource-server auth on the
  hosted HTTP transports (RFC 9728).
- **Evidence**: hash-chained `EvidenceRecord`
  (`entry_hash = sha256(prev_hash + fields)`), `verify_chain()` recomputes
  and reports the first broken link. No external anchoring — an attacker
  with full DB write access can recompute the whole chain (documented gap,
  `THREAT_MODEL.md` §3, `ENTERPRISE_SECURITY.md` "Audit trail integrity").
- **Crypto in place today**: `cryptography>=50.0.0` (pinned past
  PYSEC-2026-3552), `PyJWT[crypto]>=2.8.0`, `signxml>=3.2.0` (SSO extra).
  One concrete use: `db/encryption.py` — Fernet (AES-128-CBC+HMAC)
  field-level encryption, opt-in via `RAI_FIELD_ENCRYPTION_KEY`, currently
  covers exactly one column (`audit_log.ip_address`). **No KMS/HSM
  abstraction, no key versioning, no rotation mechanism exists** — grep for
  `AES-GCM|ChaCha20|kms|hsm` across `src/` returned nothing.
- **Supply chain / CI**: `.github/workflows/` — `ci.yml`, `dco.yml`,
  `dependency-review.yml`, `gitleaks.yml`, `publish.yml`, `scorecard.yml`
  (OpenSSF Scorecard), `security-scan.yml`. `compliance/` holds
  `OPENSSF_SECURITY_EVIDENCE.md` and `INTERNAL_SECURITY_REVIEW.md`. This is
  a real, functioning baseline — Phase 1 of this directive is largely
  "verify and extend," not "build from nothing."
- **Existing security documentation**: `SECURITY.md` (disclosure process),
  `THREAT_MODEL.md` (STRIDE, dated 2026-08-11, states real gaps honestly —
  e.g. DNS-rebinding protection off by default, no per-connection SSE
  timeout, direct-library-access bypasses the MCP governance boundary),
  `ENTERPRISE_SECURITY.md` (encryption/residency/SSO facts stated plainly,
  no unfounded compliance claims present).

## 2. Neural/BCI reality: zero existing code

Exhaustive repo-wide search (`grep -ril "neural|BCI|EEG|brain.?computer"`
across all `.py`/`.md`) returned **no matches**. There is no device
adapter, no decoder, no `NeuralIntent`/`NeuralDecision` type, no
attestation object, no capability manifest, no trust-level enum, no
classification system (N0–N5), nothing in SPEC.md, ARCHITECTURE.md, or
ROADMAP.md describing one as a future target either.

**Consequence**: Phases 4–8 and 15 of this directive (data classification,
BCI device adapters, signal integrity, neural intent attestation, action
binding, scientific evidence system) are 100% net-new product surface, not
hardening. This is the single largest scope item in the whole directive and
should be sized and reviewed as its own product initiative, not folded
silently into "enterprise hardening."

## 3. Trust-boundary / identity map (current, real)

```
Human ──(SSO/OIDC or API key)──> WhitePact org identity
Service/agent ──(client-credentials OIDC, or VC-JWT)──> WhitePact org identity
     │
     ▼
IdentityContext / PrincipalClaim (governance/models.py, governance/principal.py)
     │
     ▼
[Production-Integration Phase 2] identity_authority_adapter.py
     │  (kind → RootType, fail-safe non-terminal for ambiguous "oidc" kind)
     ▼
RootAuthorityRecord (Heart H3, root_authority.py)
     │  [Phase 3, next: persisted; today: constructed fresh per call]
     ▼
AuthorityGrant (Production-Integration Phase 1) ──> AuthorityContext
     │
     ▼
WhitePactRuntimeGateway.evaluate()  ◄── canonical decision point, gateway.py:169
     │
     ▼
ALLOW / ALLOW_WITH_REDACTION / REQUIRE_APPROVAL / DENY / QUARANTINE
     │
     ▼
InternalToolExecutor.execute() (governance/execution.py)
     │  (digest match, org match, not expired, not already consumed)
     ▼
dispatch_tool()
```

There is no neural/BCI node in this graph today — it does not exist to map.

## 4. Security-control inventory (already real, not aspirational)

| Control | Status | Evidence |
|---|---|---|
| Hash-chained audit log | Implemented | `ENTERPRISE_SECURITY.md` "Audit trail integrity" |
| OIDC/OAuth resource-server auth | Implemented, hosted transports only | `THREAT_MODEL.md` §2 |
| Field-level encryption (1 column) | Implemented, opt-in | `db/encryption.py`, `RAI_FIELD_ENCRYPTION_KEY` |
| API key storage | SHA-256 hash only, never plaintext | `ENTERPRISE_SECURITY.md` |
| Governance dispatch-bypass prevention | Implemented, tested | `tests/test_executor_bypass_invariant.py` |
| Evidence-write fail-closed | Implemented, tested | `tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed` |
| Trust-check fail-open (deliberate, asymmetric) | Implemented, documented | `THREAT_MODEL.md` §3 |
| Dependency review / secret scan / OpenSSF scorecard | Implemented in CI | `.github/workflows/` |
| KMS/HSM key management | **Not implemented** | grep, no matches |
| Application-layer message signing (MCP transport) | **Not implemented** | `THREAT_MODEL.md` §1, stated gap |
| Per-connection SSE DoS protection | **Not implemented** | `THREAT_MODEL.md` §1, stated gap |
| External evidence-chain anchoring | **Not implemented** | `ENTERPRISE_SECURITY.md`, stated gap |
| Neural data classification (N0–N5) | **Does not exist** | §2 above |
| Device trust levels (BCI) | **Does not exist** | §2 above |
| Execution-permit binding (short-lived, single-use, action-hash-bound) | **Partially implemented** for MCP-mediated tool calls via `ExecutionAuthorization` (digest, expiry, single-consumption) — not yet a general Citadel-style containment boundary | `governance/execution.py` |

## 5. Security-debt / documentation-vs-code discrepancy report

No discrepancies found where documentation overstates reality — this
repo's existing security docs (`THREAT_MODEL.md`, `ENTERPRISE_SECURITY.md`)
are unusually disciplined about labeling gaps as gaps rather than implying
mitigation. The one thing to flag: this new directive's own draft language
(§46) warns against phrases like "enterprise grade" / "bank grade" — the
existing docs already avoid these; that discipline should be preserved,
not reset, by whatever this initiative adds.

## 6. Constitutional invariants already enforced (Heart, reusable as-is)

`child_authority ⊆ parent_authority`, fail-closed on ambiguity, LLM/agent
cannot originate authority, authentication ≠ authority — all already
encoded in Heart (H1–H13) and its production adapters. This directive's
Laws 1–7, 12 restate constraints Heart already implements; §17 ("Brain
cannot exceed Heart") and §18 (Citadel containment) describe layers that
partially exist (`WhitePactRuntimeGateway`, `InternalToolExecutor`) under
different names — reuse them, do not rename or reimplement.

## 7. Recommended sequencing (given the merge decision)

1. **Resume `docs/heart-production/` at Phase 3** (Authority Persistence)
   under its existing rigor — this *is* this directive's Phase 9 core.
2. **This directive's Phases 1–3, 11–14, 16–18** (secure SDLC verification,
   real KMS/key-management abstraction, zero-trust identity hardening,
   Citadel-style execution containment generalized beyond MCP, immutable
   evidence anchoring, resilience/fail-closed matrix, release engineering)
   apply to the *existing* platform and can proceed independently of any
   neural decision, each as its own scoped phase with a Phase Report.
3. **Phases 4–8, 15 (Neural/BCI)** are a distinct, large, net-new product
   line. Recommend treating them as their own initiative gated on an
   explicit go-ahead once 1–2 are underway, not started blind alongside
   everything else.

## 8. Exit criteria for next phases (measurable, not aspirational)

- **Phase 1 (SDLC/supply chain)**: PASS requires SBOM generation added to
  CI, artifact signing added to `publish.yml`, and a documented mapping of
  existing `security-scan.yml` coverage to NIST SSDF 1.1 practices — no new
  claim beyond what's verifiably running in CI.
- **Phase 2 (crypto/KMS)**: PASS requires a real key-management module
  (versioned key IDs separate from key material, rotation path, at minimum
  a local/self-hosted provider plus one external-KMS adapter interface)
  with tamper/corruption tests — replacing, not duplicating, `db/encryption.py`.
- **Phase 3 (zero-trust identity)**: PASS requires the revocation/expiry/
  replay test matrix from `docs/heart-production/`'s own Phase 9 (there
  named Phase 9 in the 20-phase doc) executed against the *production*
  (not just library-level) identity paths.
- Neural phases: no exit criteria defined yet — pending the go/no-go in §7.

---

**Phase 0 verdict: READY to begin Phase 1 (Secure SDLC + supply chain
verification) and the resumed `docs/heart-production/` Phase 3, on the
existing platform. NOT READY to begin neural/BCI phases (4–8, 15) without
an explicit, separate go-ahead given their scale (net-new product surface,
no existing code to build from).**
