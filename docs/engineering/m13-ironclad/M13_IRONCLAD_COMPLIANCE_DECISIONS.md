# IRONCLAD compliance decisions

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Current exact-source evidence

Exact-source full matrix39243226832 FAIL: **67 test failures each**,141 inherited/owner Ruff findings remain; no policy suppression or protected test edits. DCO/Independent39243120600 FAIL;15 milestone attestations still require authentic authors, not forged signoffs or history rewrite. Configured CodeQL39243317567, Bandit/pip-audit39243317317 and historical Gitleaks39243318719 all SUCCESS atcc. These are configured checks, not proof no vulnerabilities. Product39243316986 and SDK/package39243317495 SUCCESS. External OpenSSF/main publication remains NOT_EXECUTED under the no-publication order. Four authority tables still lack approved classification; no runtime/legal data policy invented. New full failures include org-key MFA positive control400 and mocked timeout preempted by org-1 revocation; those assertions remain failing and require independent order/fixture diagnosis. All original negative tenant assertions before MFA positive control were reached. No test failure is silently waived.

Follow-up diagnosis: original mocked-timeout1 FAIL under existing tracking state but1 PASS2.02s under a fresh TMPDIR; latest_revoked_epoch=-1, so the reported revocation can represent unresolved containment admission, not an actual recorded revocation. Original org endpoint file2 PASS locally; Linux400 cause remains unresolved. No retained tracking records or original assertions were deleted.

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
