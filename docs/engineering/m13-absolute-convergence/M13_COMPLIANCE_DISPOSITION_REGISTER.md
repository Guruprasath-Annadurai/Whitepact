# M13 compliance disposition register

Status: mandatory gates remain OPEN. No waiver or protected-history rewrite.

|Identifier|Severity|Evidence / affected source|Disposition|Status|
|---|---|---|---|---|
|DCO-39619c4b|Blocking compliance|39619c4b46dac5d6e69c9e00ce887c2ed9641cfc lacks Signed-off-by; TechezzInfos attribution|Contributor must supply genuine attestation using repository-approved remediation; no new commit can invent historical consent|AWAITING_HUMAN|
|RUFF-HISTORICAL|Blocking compliance|91 immutable test findings on38f3ceb0; whole formatting also fails|Preserve evidence; fix editable new source separately; maintainer must resolve narrow evidence/lint policy conflict|BLOCKED|
|MIGRATION-0064-0065|Blocking specification|Original migration blob f4d5731e9b2792b18a69e1fcfd475164ee4f0898 expects0064, required security head0065|Do not weaken downgrade refusal or edit assertion; historical-binary/role-retirement qualification remains separate|AWAITING_HUMAN|
|RUNTIME-DEAD-WORKER|Blocking specification|Original PID-only unlink assertion|Retain unresolved container tracking; require authoritative absence instead|AWAITING_HUMAN|
|MYpy-WHOLE|Blocking CI|38f3ceb0 remote7 errors/2 files; local controlled baseline8/2,0 normalized delta|Final-head assessment pending; focused new modules passed historically|FAILED|
|GITLEAKS-1|Blocking secret review|docs/security/m13s4/WHITEPACT_M13S4_SECURITY_API_CONTRACT.md:83 at39619c4b|Classification unresolved; no secret printed/rotation performed|AWAITING_HUMAN|
|GITLEAKS-2|Blocking secret review|docs/m11/WHITEPACT_M11_CANONICAL_PRODUCT_INVENTORY.md:45 atadc63598|Classification unresolved|AWAITING_HUMAN|
|GITLEAKS-3|Blocking secret review|tests/test_security_alert_triage.py:30 at923aa031|Test-literal candidate; not accepted without fingerprint review|BLOCKED|
|GITLEAKS-4|Blocking secret review|src/responsibleai/governance/evidence_publication.py:138 at3dc20935|Typed parameter false-positive candidate; scanner disposition needs exact evidence|BLOCKED|
|GITLEAKS-5|Blocking secret review|tests/fixtures/global_directory/demo_catalog.json:183 at06bce564|Fixture candidate; not a waiver|BLOCKED|
|GITLEAKS-6|Blocking secret review|src/responsibleai/global_directory/fixtures/demo_catalog.json:55 at656213fc|Fixture candidate; not a waiver|BLOCKED|
|DEPENDENCIES|Blocking applicable scan|Historical final-head Bandit/pip-audit pass within configured dependency scope|New exact-head scans pending; optional upstream alerts require individual reachability classification|BLOCKED|
|OPENSSF|External gate|Standalone workflow main/schedule-only, externally publishing|NOT_EXECUTED; no retargeting or policy weakening|BLOCKED|

No live rotation, role retirement, blanket Gitleaks exclusion, forged signoff, paid credit purchase or production cutover is authorized.

## Independent fingerprint dispositions (2026-10-18)

Exact-head Gitleaks39131937716 found10 generic-api-key matches, including4 H5 synthetic constructor literals in historicalfef386131b320c84cfce88358e5b11f7bc6d9e77 and6318439b. Actual source review classifies all10 as non-credentials:
- GITLEAKS-1: WebAuthn request example placeholder; not actual authenticator material.
- GITLEAKS-2: Markdown table prose describing service-account credential endpoints; no credential value.
- GITLEAKS-3: fixed synthetic key in a ConnectionManager redaction test using a fake socket; assertions require no raw key/prefix/suffix in logs.
- GITLEAKS-4: Python type annotation Ed25519PrivateKey | None, with a newly generated key in the body; no serialized private key.
- GITLEAKS-5/6: public demo directory entity_key values in JSON, not authentication credentials.
- H5 four fingerprints: same fixed synthetic SDK constructor-only literal/assertion; AST confirms no method/network call in that case.

Only the10 exact commit/path/rule/line fingerprints emitted by this run are appended to the existing .gitleaksignore. No directory/rule/global exclusion, secret value, history rewrite, credential rotation or broader waiver. Scanner requalification is pending; earlier unresolved classifications above are superseded by this review, not a claimed passing gate.

Actual Dependabot alerts24(source-map-js),23(Mako),22(multidict) remain open on the default branch, but this candidate already pins1.2.2,1.4.3,6.9.1 respectively, meeting the advisory's listed fixes1.2.2,1.4.2,6.9.1. No gratuitous dependency update is needed. Alert2 NLTK GHSA-8mgp-746c-j5xp has no listed patched release; opt-in sentiment dependency and actual reachability remain a separately documented residual risk. Default-install security scan39131935301 PASS; it does not certify optional dependency absence.

Whole-source mypy corrective result: Success, no issues in385 source files locally. Explicit missing MCP contexts are denied401, optional actor display-name formatting is typed safely, and the existing nonnullable policy field is read from its persisted mapping. No assurance flag, verification prerequisite or policy is relaxed. Final remote requalification remains required. Formula full local domain suite:148 PASS in5.27sec. Corrective credential-backed MCP HTTP + import-order scope:13 PASS in11.10sec.

de9c2d1e exact-head Gitleaks39132851578 PASS after the10 specific non-credential fingerprint dispositions. CodeQL39132846867 and security scan39132849222 PASS; Go/default+dashboard wheels39132839557 PASS. These are predecessor-checkpoint results after subsequent runtime corrections, not final-source qualification. Final scans remain required. No contributor DCO attestation or protected evidence/lint conflict is waived.
