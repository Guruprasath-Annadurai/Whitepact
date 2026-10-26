# IRONCLAD compliance decisions

Reviewed source checkpoint: 47fc55a1591890f18c06333b4f187d091535719d; tree b57b0e46f388cce8a01690e986fde2be6783a967; parent d480e8c87882a7fc5d353961a6fe22048380ab9f. Initial baseline: 7939341fd9d98d0f1fa39ce4421318dbc1dac33e. Draft PR #221 targets codex/whitepact-m13-absolute-convergence. This is an interim engineering record. Completed d9ddf44a CI is historical relative to this successor; new exact-head CI remains pending.

## Immutable evidence and author decisions

Original security reproducers, H4 source/tests and protected branches remain unchanged. New commits have DCO trailers for new work; this is not cryptographic signing. Fifteen inherited commits lack required author attestation. Genuine author/legal confirmation is required; no forged attestations, broad exceptions or protected history rewrite. Original whole Ruff 141 includes91inherited protected findings and50owner-test findings. Editable non-H4 findings must be fixed without suppressions; immutable findings require maintainer disposition. Focused new-code Ruff passes; whole gate remains open.

Gitleaks793 passed after exact reviewed synthetic-fingerprint exceptions; no broadened ignore or history rewrite here. OpenSSF external publication is NOT_EXECUTED, not PASS. New-head compliance CI pending.

## Draft four-table classification (not legal approval)

| Table | Proposed classification / sensitivity | Data, tenant and credential considerations | Proposed conservative lifecycle |
|---|---|---|---|
| authority_containment_records | CANONICAL_SECURITY_EVIDENCE / CRITICAL | org_id, responder user, target IDs, reason free text may contain personal data; security action and epoch. Scope by org; identifiers remain linkable PII | SECURITY_EVIDENCE_DEFAULT, no automated erasure/export expansion until retention/legal approval. Preserve evidence/FKs, redact/minimize free text; backup carries same sensitivity |
| authority_recovery_requests | CANONICAL_SECURITY_EVIDENCE / CRITICAL | requester/executor/target-root IDs, proposed_parameters_json and digest/quorum may contain identity/key material. org-owned; public recovery disabled | Preserve state transitions and audit linkage; no raw recovery parameters in generic export. No automatic deletion; counsel/owner must approve retention and minimization |
| authority_recovery_votes | CANONICAL_SECURITY_EVIDENCE / CRITICAL | voter ID, decision, time, notes free text. Tenant obtained via request_id join, not assumed from vote alone; cascade FK deletion can destroy evidence | Preserve vote history, no automated erasure/export until qualified tenant join/redaction. Explicit retention/hold and request deletion policy required |
| authority_step_up_challenges | SENSITIVE_SECURITY / CRITICAL | user/org/session IDs, operation digest, raw challenge, origin/RPID and expiry/consumption. Non-secret public challenge is still active ceremony material; never export active session linkage | No generic export. Bounded expiry/consumed retention proposed, duration requires approval; evidence can retain redacted hash/outcome. Do not introduce cleanup/deletion without transaction/replay/hold policy |

These draft proposals do not alter TABLE_CLASSIFICATIONS, enable erasure/export, approve legal retention periods or mark the existing classification gate passing. Questions: jurisdictional retention, legal holds, subject access/redaction, requester/voter identity minimization, backup retention/deletion, request→vote FK preservation and session unlinking. Founder/privacy/security owners must approve the final policy.

## Contributor remediation checklist

Each SHA below is Git-attributed to Techezz Infos (Techezzinfos@gmail.com), which is an attribution record, not proof of legal authorship or consent. For **each** commit, the actual contributor must review that exact change and supply an authentic DCO attestation identifying its SHA and the rights to contribute. The maintainer must then choose a repository-policy-compliant remediation without rewriting protected history or forging a trailer. If authorship or rights cannot be established, the gate stays blocked. This agent cannot attest retroactively for another contribution.

| Exact historical commit | Required disposition |
|---|---|
| 5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558 | Contributor attestation and maintainer decision pending |
| 1aa90b5a8d25db4a1c362ecd3c7c79c25bc42bde | Contributor attestation and maintainer decision pending |
| 458fda2ae56340e316ede9590c7f511e81229857 | Contributor attestation and maintainer decision pending |
| 39619c4b46dac5d6e69c9e00ce887c2ed9641cfc | Contributor attestation and maintainer decision pending |
| bb87d76841c1aef7a22e53b20728c646f94c85a5 | Contributor attestation and maintainer decision pending |
| 7fd0fdd19c74cb8b4eab8afcd465eb786ca33817 | Contributor attestation and maintainer decision pending |
| 57c69344961196fd89b40e8ffec65c06a1898fce | Contributor attestation and maintainer decision pending |
| f7bf1729bce2b2a683a959d905282cc5b6d3fb7e | Contributor attestation and maintainer decision pending |
| a0d941c3ac5deb2d5ac8baa9d4fdd58de9d824ef | Contributor attestation and maintainer decision pending |
| 4f383ffe069d6bec5f348ea934388e2a20b184a9 | Contributor attestation and maintainer decision pending |
| 97657ece23229c16c626ceb5f6162c143c924a3b | Contributor attestation and maintainer decision pending |
| 128f988a903bd9cb917e71b4568c583caba885d4 | Contributor attestation and maintainer decision pending |
| 0daa57aac92c97765eb8680a705e40534760bbf5 | Contributor attestation and maintainer decision pending |
| 6062290c3b64e29be977de70ffcc6c6869caa6b1 | Contributor attestation and maintainer decision pending |
| 15e0c62409d83934445f1832e53c2aa6d218137a | Contributor attestation and maintainer decision pending |

These 15 are the previously identified milestone-range debt. The narrower introduced-DCO CI range excludes its base5291cc6d and reports39619c4b. All-history debt is broader; neither range is silently substituted for the other. Existing approved exceptions remain unchanged.

## Optional NLTK risk

Authoritative GitHub advisory GHSA-8mgp-746c-j5xp rechecked via GitHubAPI2026-10-19: updated2026-09-02T14:35:05Z; affected<=3.10.3; first_patched_version=null. No fixed version is reported. Existing opt-in sentiment/VADER preprovisioned-data mitigation is scoped; it does not prove universal package unreachability. Preserve current scan scope and review exact call paths. No new audit exclusions. Source: https://github.com/advisories/GHSA-8mgp-746c-j5xp .

## Exact d9ddf44a compliance outcomes

Independent Integration workflow 39206402102 FAIL. The inherited introduced-DCO job (base5291cc6d) specifically reports missing signoff39619c4b46dac5d6e69c9e00ce887c2ed9641cfc. Original assertion scopes retain migration0064-vs0065 and nine pre-A2 root failures; revocation scope208 PASS/1 FAIL (dead-PID tracking) each interpreter. Mandatory root reproducers3 PASS/3 FAIL/3DESELECTED each (owner setup lacks A2), not six qualified boundaries. Legacy strict customer journeys stop at their actual gates; no invented success.

Full Ruff rechecked on working source:141 findings, entirely in historical and original owner test files. The23 H4-owner findings are explicitly Antigravity-owned. Other original protected security reproducers remain immutable; import/format-only edits would still change evidence blobs. No suppression or broad exclusion added. All newly authored scoped files lint/format clean. Any proposed owner-test cleanup requires verifying that the exact file is editable under the original-producer protection, rather than assuming all 50 are editable.
