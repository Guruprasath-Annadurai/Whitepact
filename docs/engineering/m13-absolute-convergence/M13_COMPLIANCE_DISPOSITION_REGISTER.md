# M13 compliance disposition register

Tested source HEAD `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`; tree `6bf30ee0d11c8137ec6a77844b1517de50d89edd`; parent `3be566129be44e00e92a07dd9449c957751eeb5d`. Candidate branch `codex/whitepact-m13-absolute-convergence`, [draft PR220](https://github.com/Guruprasath-Annadurai/Whitepact/pull/220). Production `src` subtree `bbd0e5f0b6a7dd02b388ab45d4dc5a7fed9036f1` is unchanged since296ad7ff. Final reports live on documentation-only branch `codex/whitepact-m13-absolute-evidence`. Historical receipts identify their own HEAD and do not substitute for final7939341f evidence.

Mandatory gates remain OPEN. No protected-history rewrite, forged attestation, broad exclusion, live credential rotation or policy waiver.

| Finding | Severity / source | Disposition | Status |
|---|---|---|---|
| DCO historical range | Blocking; original full-suite provenance test | Genuine contributor attestation/approved historical remediation required for15 exact commits below. Existing six exact-SHA owner exceptions remain unchanged. | AWAITING_HUMAN |
| Whole-tree Ruff/format | Blocking;141 findings:91 inherited immutable +50 original owner tests | New editable deltas lint-clean; preserve protected originals. Maintainer must resolve narrow evidence/lint-policy conflict without suppressing assertions. | BLOCKED |
| Historical migration heads | Blocking; old0064/0063/0053 expectations vs required0065 | Preserve original assertions and downgrade refusal; authorize safe specification disposition separately from historical-binary compatibility. | AWAITING_HUMAN |
| PID-only cleanup | Blocking; original dead-worker assertion | Require authoritative container absence; do not remove unresolved authority because PID is gone. | AWAITING_HUMAN |
| Protected root setup | Blocking; missing genuine recent persisted A2 session | Approve specification-compatible real UV fixture supplement/error precedence; no seeded elevated sessions or assurance flags. | AWAITING_HUMAN |
| Gitleaks 10 fingerprints | Exact commit/path/rule/line false-positive review | Ten narrow existing-file fingerprints only; no real credential exposed/rotated. Final 39156458375 SUCCESS. | FIXED |
| Whole-source mypy |385 source files after typed context/display/mapping corrections | Actual final full-matrix log records16 successful mypy steps on the same source, no authentication or assurance relaxation | FIXED / PASS within scope |
| Default-install dependency scan | Bandit/pip-audit39156450500 | PASS within configured scope; does not certify all optional dependencies. | PASS |
| Optional NLTK | GHSA-8mgp-746c-j5xp; no listed upstream fix | Preserve explicit residual risk; no unsupported breaking update or universal unreachability assertion. | BLOCKED |
| Data inventory | Four authority tables unclassified | Security/privacy owner must approve classification and retention; no invented legal policy or evidence deletion. | BLOCKED P1 |
| OpenSSF | Standalone main/schedule workflow publishes externally | NOT_EXECUTED; no publishing/retargeting or policy weakening authorized. | BLOCKED |

## Contributor action package

Full-suite historical range reports these15 unsigned commits (all Git-attributed Techezz Infos), beyond the earlier single39619c4b checkpoint. Supply genuine attestation for each through approved repository remediation; a new Signed-off-by cannot invent historical consent. No history rewrite is performed.

- 5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558
- 1aa90b5a8d25db4a1c362ecd3c7c79c25bc42bde
- 458fda2ae56340e316ede9590c7f511e81229857
- 39619c4b46dac5d6e69c9e00ce887c2ed9641cfc
- bb87d76841c1aef7a22e53b20728c646f94c85a5
- 7fd0fdd19c74cb8b4eab8afcd465eb786ca33817
- 57c69344961196fd89b40e8ffec65c06a1898fce
- f7bf1729bce2b2a683a959d905282cc5b6d3fb7e
- a0d941c3ac5deb2d5ac8baa9d4fdd58de9d824ef
- 4f383ffe069d6bec5f348ea934388e2a20b184a9
- 97657ece23229c16c626ceb5f6162c143c924a3b
- 128f988a903bd9cb917e71b4568c583caba885d4
- 0daa57aac92c97765eb8680a705e40534760bbf5
- 6062290c3b64e29be977de70ffcc6c6869caa6b1
- 15e0c62409d83934445f1832e53c2aa6d218137a

Every convergence commit has the configured contributor signoff. Existing approved exact exceptions are distinct from attestations and are not expanded.

## Exact Gitleaks dispositions

Initial631 run 39131937716 found10 generic-api-key fingerprints. Individual source/AST review:
1.39619c4b docs/security/m13s4/WHITEPACT_M13S4_SECURITY_API_CONTRACT.md:83 — WebAuthn JSON placeholder.
2.adc63598 docs/m11/WHITEPACT_M11_CANONICAL_PRODUCT_INVENTORY.md:45 — Markdown service-account endpoint prose.
3.923aa031 tests/test_security_alert_triage.py:30 — synthetic redaction fixture/fake socket.
4.3dc20935 src/responsibleai/governance/evidence_publication.py:138 — Ed25519PrivateKey type annotation; no serialized key.
5.06bce564 tests/fixtures/global_directory/demo_catalog.json:183 — public demo entity identifier.
6.656213fc src/responsibleai/global_directory/fixtures/demo_catalog.json:55 — public demo entity identifier.
7–10. Historicalfef386131b320c84cfce88358e5b11f7bc6d9e77 and6318439bff2a446ed942dc6d913e03f0333b5788, tests/test_h5_developer_onboarding_acceptance.py:51/56 — synthetic constructor-only SDK literal/assertion; no network method call.

Only exact emitted commit/path/rule/line fingerprints were added to existing .gitleaksignore. Independent reviewer concurred; final Gitleaks 39156458375 PASS. No values printed, broad path/rule exclusion, secret rotation or protected-history rewrite.

## Dependencies and operational decisions

### Migration downgrade safety verdict

Retention metadata alone is UNSAFE: revision0064 code need not enforce a requirement retained only in `_alembic_0065_downgrade_retention`. Current0065 downgrade does not create a metadata-only intermediate state. It acquires PostgreSQL ACCESS EXCLUSIVE on trust_fabric_bootstrap_records, checks every nonzero require_passkey_stepup row, and raises before dropping the column or advancing the revision when mandatory requirements exist. A concurrent writer must serialize with that lock. Empty/nonmandatory rollback remains separately supported. Upgrade retains a compatibility reader for historical retention metadata; that reader is not approval to run0064 while mandatory policy exists.

Final7939341f real-PG migration scope in Independent Integration39156415461:4 PASS per interpreter, including atomic mandatory refusal, nonmandatory historical row survival, failed-DDL transaction rollback and a concurrently committing mandatory writer. Original f4d5731e9b2792b18a69e1fcfd475164ee4f0898 assertion remains unchanged and failed against0065 head; no altered assertion supplies acceptance.

This is a controlled schema-transition verdict, not universal old-binary safety. Current runtime refuses0064/0066/unverified revisions. An already-running old client with active database credentials can still operate: the isolated role test proves CONNECT revocation alone leaves an existing pool connection functional. Its tested operations contract is version-scoped roles, NOLOGIN plus backend termination, rollback of uncommitted old effects, denial of reconnect/SET ROLE, and survival of current-role operation. That uses a disposable effects table, not an actual historical root-authority binary. Historical-binary coexistence and live operator cutover therefore remain BLOCKED/NOT_EXECUTED; no live role retirement was authorized or performed.

Default-branch alerts24 source-map-js,23 Mako,22 multidict list fixes1.2.2/1.4.2/6.9.1; candidate already resolves1.2.2/1.4.3/6.9.1. Alert2 optional NLTK has no listed patched release. Actual application sentiment path uses VADER/preprovisioned lexicon, not automatic runtime download; implicated model-artifact APIs were not observed in that path. This is a bounded reachability observation, not universal safety. Existing full-workflow NLTK audit exceptions remain inherited policy, not a new security approval.

Missing classifications: authority_containment_records, authority_recovery_requests, authority_recovery_votes, authority_step_up_challenges. Owner/qualified privacy review must define categories and retention before complete inventory acceptance. Retention and legal identity are not inferred from SOC2/GDPR labels.

Final CodeQL 39156443678 SUCCESS; security39156450500 SUCCESS; Gitleaks 39156458375 SUCCESS. Framework tests use isolated local providers, no paid calls. No quota denial occurred; any incomplete qualification is reported as such, not attributed to invented usage limits.

Maintainer/founder decisions remain: authentic DCO remediation; protected oracle/specification precedence; data/retention ownership; qualified operator restore and external immutable witness policy; any production B1 activation or live role-retirement/cutover. No production decision is authorized by this report.
