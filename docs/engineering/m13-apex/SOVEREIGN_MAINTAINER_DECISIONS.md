# Mandatory historical gate dispositions — no waiver applied

M13 OPEN. GLOBAL PRODUCTION NO-GO. Original tests/history remain unchanged.

## Migration expectation conflict

Original blobf4d5731e9b2792b18a69e1fcfd475164ee4f0898 calls Alembic upgrade
head and requires version0064. Current head0065 adds mandatory passkey semantics.
Exact99c independent CI on both Pythons records35 PASS/1 FAIL, specifically
`assert '0065' == '0064'`. Separate actual PG mandatory downgrade refusal,
supported optional rollback, concurrent writer and failed-DDL scope4 PASS.
Do not remove0065, alter the historical assertion, stamp a false revision, or
drop mandatory state to pass the old test. Required maintainer action: ratify
which immutable expectation represents historical evidence and define a formal
accepted baseline/versioned acceptance procedure. Until that procedure actually
passes, this gate remains FAILED. This document is not a waiver or CI suppression.

## Dead-worker tracking conflict

Original `test_kill_esrch_unlinks_dead_worker_tracking` requires no unresolved
record and deletion after ESRCH. Additional independent counterexample proves
worker death is not container termination. Exact99c runtime unit CI54 PASS/1 FAIL
on both Pythons retains the historical failure. Additional tracking/startup
scope5 PASS; actual native container scope19 PASS on both Pythons, including
real worker exit with real still-running container and write-denial cleanup.
Do not delete evidence merely because the worker is dead. Safe resolution is
qualified authoritative containment confirmation, followed by ownership-scoped
reconciliation; not automatic PID garbage collection. FORTRESS H2 retains
infrastructure hardening ownership. Required maintainer action: disposition
obsolete semantic expectation through an explicit versioned acceptance process.
No alteration, skip or xfail has been introduced.

## DCO

Ancestor39619c4b46dac5d6e69c9e00ce887c2ed9641cfc lacks Signed-off-by; author
Techezz Infos. All APEX convergence checkpoints carry genuine configured
signoffs. Required original-contributor attestation plus maintainer's accepted
DCO mechanism; current trailer-only gate cannot accept this document as a
signature. No protected history rewrite, forged trailer or invented exemption.

## Immutable test lint

Whole-repository Ruff91 findings are confined to12 original security test files:
four independent_m13r2 files (one each), customer_root_authority_bootstrap11,
delegation_revocation_verification5, m12fs_root_hardening24,
m13r3_security_regression9, m13s_security_regression1,
p0_approval_resume_adversarial16, p0_linux_containment9,
p0_revocation_outage12. Editable changed source Ruff PASS.
Required maintainer policy decision for immutable evidence versus full-tree lint;
no exclusion, blanket ignore or protected test rewrite applied. Gate remains FAIL.

## Historical Gitleaks classification package

Never print candidate secret values. Preserve scanning and full-history evidence.
Fingerprint provenance:

| Commit/path | Classification requiring owner confirmation |
|---|---|
|39619c4b docs/security/m13s4/WHITEPACT_M13S4_SECURITY_API_CONTRACT.md:83|Public contract/example context; owner must establish whether credential is real or illustrative|
|adc63598 docs/m11/WHITEPACT_M11_CANONICAL_PRODUCT_INVENTORY.md:45|Historical inventory/example context; no assumed live-secret clearance|
|923aa031 tests/test_security_alert_triage.py:30|Test literal; confirm nonproduction provenance|
|3dc20935 src/responsibleai/governance/evidence_publication.py:138|Typed private-key parameter name, not demonstrated key material; precise rule disposition needed|
|06bce564 tests/fixtures/global_directory/demo_catalog.json:183|Catalog/entity identifier candidate; owner classification needed|
|656213fc src/responsibleai/global_directory/fixtures/demo_catalog.json:55|Catalog/entity identifier candidate; owner classification needed|

Last two fingerprints can occur in full-history refs outside candidate ancestry;
do not prune history to make scanning green. A real credential requires a
separately authorized rotation/revocation procedure and revalidation. A confirmed
nonsecret requires the scanner's accepted precise reviewed procedure; no blanket
allowlist, scanner shutdown or unsupported PASS claim. Owner classification is
not replaced by inferring harmlessness from a filename.

## Dependencies

Repository API alerts:24 source-map-js patched1.2.2,23 Mako patched1.4.2,
22 multidict patched6.9.1; candidate pins1.2.2/1.4.3/6.9.1 respectively.
Main/default-branch alerts are not closed by a development candidate. Optional
NLTK3.10.3 alert2 has no reported patched version. Existing opt-in/reachability
notes are retained, not described as upstream repair. Maintainer must accept
the bounded optional exposure or wait for/qualify an upstream alternative.
Do not break SDK/framework compatibility to silence an advisory.

## External gate execution

Use finalHEAD workflow dispatch for configured CodeQL/Gitleaks/security scans
when PR base filters do not launch them. Report genuine results, including FAIL.
Do not change branch filters or checks merely to hide a failure. Public Scorecard
publication and actual live credential rotation remain outside this authorization.
