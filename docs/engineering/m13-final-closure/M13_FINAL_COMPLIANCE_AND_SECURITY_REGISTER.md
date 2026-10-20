# M13 compliance and security register — OPEN

No legal or contributor decision is fabricated. No production access is enabled.

- Inherited Ruff141 diagnostics remain distinct from clean scoped new-code checks.
  Protected original assertions are preserved; no lint exclusion was introduced.
- Seven full-directory scan findings in six unchanged files still need independent
  classification. A green configured hosted scan does not close the broader findings.
  Never reproduce actual credentials; rotate only with the authorized owner if real.
- Historical39619c4b requires genuine author/maintainer DCO disposition; no forged
  signature, amendment of another author or rewritten history is authorized.
- Four authority tables remain without approved retention/export/erasure/hold
  treatment. Proposed runtime_containment_records adds a fifth required classification.
- Recommendation for journal records: tenant-restricted operational/audit access,
  no raw arguments/secrets, no deletion while nonterminal or under legal hold,
  tenant-scoped export of nonsecret associations, and reviewed post-terminal retention.
  Duration, erasure exceptions and legal basis require the responsible owner.
- Optional NLTK residual risk is not accepted merely because comments were corrected.
- MCP1.30.0 requirement is unchanged. No unrelated dependency upgrade or new platform.

Fresh exact-source scans, full lint/types, license/action pins and package gates
remain required. Scope passes and historical records do not constitute FULL PASS.

## Broader Gitleaks findings — independently triaged

The seven redacted findings were inspected against unchanged baseline source,
including the full reported line range. No credential value is reproduced.

| Location | Classification | Evidence |
| --- | --- | --- |
| docs/security/m13s4/WHITEPACT_M13S4_SECURITY_API_CONTRACT.md:83 | FALSE POSITIVE | authenticatorData JSON contract placeholder; not a real assertion or secret |
| docs/m11/WHITEPACT_M11_CANONICAL_PRODUCT_INVENTORY.md:46 | FALSE POSITIVE | prose table describing credential endpoints; no credential value |
| src/responsibleai/governance/evidence_publication.py:209 | FALSE POSITIVE | typed optional Ed25519PrivateKey parameter declaration, not embedded key bytes |
| tests/test_h5_developer_onboarding_acceptance.py:51 | NONSECRET TEST FIXTURE | fixed SDK initialization input; no provider-issued credential |
| tests/test_h5_developer_onboarding_acceptance.py:56 | NONSECRET TEST FIXTURE | assertion of the same synthetic initialization input |
| tests/test_security_alert_triage.py:30 | NONSECRET TEST FIXTURE | deliberately recognizable synthetic value for log-redaction assertions |
| tests/test_step_up_forged_proofs_http.py:122 | NONSECRET TEST FIXTURE | deliberately unsigned JWT shape, alg none and empty signature, used for rejection |

No confirmed exposed live credential was established in these seven findings.
No broad allowlist, scanner exclusion, credential rotation or false clean
full-directory scan is claimed. The raw scanner still reports them; this table
is the explicit disposition of that broader result, not a substituted CI pass.

## Mandatory framework dependency conflict — reproduced

Resolution of the declared consumer/framework requirements alongside current
Core fails: crewai1.15.28 requires mcp>=1.28.1,<1.29.dev0, while Core requires
mcp>=1.30.0,<2.0.0. The dry-run resolver returned unsatisfiable requirements.
No package was installed or downgraded. Do not "fix" mandatory consumer skips by
quietly replacing the patched Core MCP floor. A compatible upstream release or
reviewed isolated-consumer security disposition is required. Other SDK/product
qualification can continue independently. This is not a test PASS or a waiver.
