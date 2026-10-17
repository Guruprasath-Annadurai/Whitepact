# Final integration runtime review

M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Source and counterexamples

Starting candidate: `09f6e4cc132285717d4f3000aac3dd9c7a7ce6df`, tree
`7beeaca79b27fe5d3804dc0a113575f8af13a022`, parent
`6774ff8099981ffa2b09287b91b1f549e1626890`. Clean before this review.
Canonical remote fetched again. TITAN-1 remains
`e1a9f1235d6b46b7423c21815ff27ebebf6887c6`; TITAN-2 remains
`6b604bf12ac07508c5b584b85ed48df8a983e5af`.

The TITAN-2 runtime reproducer is copied unchanged as
`tests/test_runtime_resilience_adversarial.py`, Git blob
`36e573778362910615ea9c04e1cb227c224dc214` in both owner and candidate.
Against explicitly pinned original APEX source/configuration it produced
**3 FAIL in 15.21 seconds**: missing tenant admitted on SQLite, raw integrity
failure on PostgreSQL, and EPERM tracking removed as if the process had exited.

An earlier cross-worktree invocation produced 3 PASS but loaded the owner's
pytest `pythonpath` configuration. It is excluded from APEX evidence. A mixed
cross-checkout regression invocation then failed collection on conflicting
`tests.conftest` imports; no assertions ran in that invocation. The integrated
run uses the byte-identical copied reproducer and APEX configuration throughout.

Integrated reproducer plus unchanged `test_in_flight_revocation.py` and
`test_revocation_kernel.py`: **31 PASS in 26.94 seconds**, zero skips. Scoped
Ruff and `git diff --check` pass. Exact-head CI remains pending; this is local
regression evidence, not final security acceptance.

## Selective implementation, pending acceptance

Only two reviewed owner changes are selected: require an explicitly ACTIVE
organization at nonce admission; retain remote process tracking when signal-zero
returns EPERM. These do not grant authority to missing tenants. The EPERM test
patches `os.kill`; it proves exception handling, not native cross-user Linux
enforcement. No whole branch merge and no root architecture change is included.
The independent CI workflow adds these regressions to both Python versions,
retaining its strict zero-skip receipt requirement and all existing suites.

## Container cleanup remains pending

The owner change delays unregister until after `_remove_containers_uninterruptible`.
However `_remove_containers` catches inspection exceptions and sets `exists=False`,
and can return after an inspection failure or exhausted deadline without a
positive absence result. Moving unregister alone does not qualify the advertised
confirmed-containment contract. Do not integrate this change as accepted cleanup.
TITAN-2 must supply failure-path evidence and an authoritative absence contract.

## Other mandatory gates

No newer TITAN-1 principal-binding correction exists on the fetched branch.
The preserved genuine customer receipt remains **10 PASS / 1 FAIL /
14 NOT_EXECUTED**, with the canonical-principal FK failure at root completion.
Do not seed a principal or bypass consent/passkey requirements to advance it.
Nonempty PostgreSQL rollback still loses the passkey requirement; native Linux
coverage for these new runtime cases is pending exact-head CI.

The full unchanged Ruff gate still reports **101 findings** across 13 files,
including four immutable original reproducer files and security-owned authority
implementation/tests. Removing assertions or modifying original reproducers is
not an acceptable cleanup. Security owners must supply reviewed source fixes;
founder review must explicitly disposition the immutable-test policy conflict.
DCO requires an authentic author/maintainer remediation accepted by the existing
policy for unsigned ancestor `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`;
no forged signoff or protected history rewrite is authorized. Historical Gitleaks
findings require owner classification and any real credential rotation followed
by founder-approved historical remediation. Do not weaken or suppress gates.

Next: qualify the integrated runtime changes on exact-head CI; obtain TITAN-1's
canonical principal binding correction and repeat the genuine journey; return
container absence and PostgreSQL rollback contracts to TITAN-2 for correction.
