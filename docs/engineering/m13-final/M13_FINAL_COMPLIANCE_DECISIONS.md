# M13 final human-controlled decision register

Candidate under qualification: HEAD `bb6e263fc271a07f58484ce1fd1445cc201b24b0`, tree `93f36747cd00610850c8cf0ace13de107b145da5`, parent `2bde48d4abe20312dd6408cf62366d68ca69746e`. [Draft PR223](https://github.com/Guruprasath-Annadurai/Whitepact/pull/223). Reports/evidence are maintained separately from the tested implementation. M13 OPEN. GLOBAL PRODUCTION NO-GO.

Status: OPEN. No decision below is deemed approved. Continue unrelated engineering.

|Decision|Concrete issue/evidence|Options|Safe recommendation / authority|
|---|---|---|---|
|DCO|15 milestone commits lack genuine attestations; introduced-range CI also separately flags39619c4b. Exact SHA/attribution ledger in prior report linked below.|Actual contributor supplies authentic SHA-specific rights attestation and maintainer chooses compliant remediation; otherwise gate remains blocked.|No forged trailers, protected-history rewrite or expanded exceptions. Actual authors+maintainer must act.|
|Whole-tree Ruff/protected tests|Prior141 findings; current full run must recalculate. Source safety changes may legitimately remove findings; protected originals cannot be silently reformatted.|Authorize a separately reviewed protected-evidence formatting/spec update with retained original hashes, or retain failures.|Do not suppress rules or call red gates green.|
|Four data classifications|authority_containment_records,authority_recovery_requests,authority_recovery_votes,authority_step_up_challenges lack approved retention/export/erasure/hold policy.|Approve explicit tenant-scoped classification/lifecycle with privacy/legal review, or keep unknown tables denied.|Prior conservative proposals remain drafts. No runtime policy or legal retention invented.|
|Migration policy|Current0065 protects mandatory passkeys; historical tests expect0063/0064.|Approve current-head invariant counterparts and exact original conflict disposition, or retain mandatory failure.|Never weaken atomic mandatory downgrade refusal or deploy an old binary with live pooled roles.|
|H4 schema status|PostgreSQL migration0049 chk_org_governance_status accepts ACTIVE/SUSPENDED/DISABLED; old SQLite assertion expectsQUARANTINED.|Approve exactDISABLED quarantine representation with audit/authority-denial proof and preserve original failed blob, or retain blocked gate.|Do not broaden to an unsupported status merely for green. RealPG schema/denial counterpart runs separately; original assertion remains unchanged.|
|Tracking and callback specifications|Dead PID/absent file/name alone cannot attest containment. Old mocks may replace the actual cleanup verifier.|Approve precise policy-compatible behavior counterparts with original RED retained, or keep failed mandatory acceptance.|Never erase unknown tracking, NFC-alias tenant IDs or remove a foreign/name-reused container.|
|Strict identity assurance|Prior strict judgment blocks at17 with seven later stages NOT_EXECUTED; account/WebAuthn control is not legal identity.|Authorize/qualify a stronger identity provider/workflow, or explicitly ratify a narrower milestone acceptance scope while retaining strict denial.|Keep sensitive default functionality disabled until security and founder disposition. Prototype25/25 is not strict25/25.|
|NLTK advisory|GHSA-8mgp-746c-j5xp affects locked3.10.3; GitHub reports no fixed version.|Owner accepts scoped opt-in mitigation with explicit residual risk, or authorize supported replacement/removal with consumer tests.|No new pip-audit exclusions or blanket unreachability claim.|
|External qualification/publication|Independent cross-review pending; external OpenSSF/main publication and production are unauthorized.|Obtain actual independent review and separate explicit publication/production authorization if later needed.|No merge/deploy/spend/cloud/packages/M14 under this order.|

[Exact prior DCO15-SHA and four-table draft proposals](https://github.com/Guruprasath-Annadurai/Whitepact/blob/a7c0a357853ddc56687267ac2bf72e0c90969d2f/docs/engineering/m13-ironclad/M13_IRONCLAD_COMPLIANCE_DECISIONS.md).
[Original migration constraint](https://github.com/Guruprasath-Annadurai/Whitepact/blob/bb6e263fc271a07f58484ce1fd1445cc201b24b0/migrations/versions/0049_add_organization_governance_status.py).
[NLTK advisory](https://github.com/advisories/GHSA-8mgp-746c-j5xp).

All-history DCO debt, milestone debt and introduced-range checks are distinct; no convenient range substitutes for another. Git attribution is not proof of legal consent. Contributor attestations require actual authors. All new checkpoints use git -s signoffs without claiming cryptographic signatures.

Independent actual PostgreSQL schema proof:1 PASS10.15s,
`/private/tmp/m13-final-quarantine-schema.xml`; evidence-only reproducer
`scripts/engineering/reproducers/test_m13_final_quarantine_schema.py`.
QUARANTINED update is rejected by chk_org_governance_status and rolls back;
DISABLED commits and ExecutionNonceRepository denies governed admission.
The constructed candidate nonce is negative-only, not a customer grant or
execution receipt. This proves schema/denial behavior, not authorization to
rewrite the original assertion. Founder/maintainer disposition remains required.

