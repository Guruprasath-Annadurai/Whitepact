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
