<!-- Copyright (c) 2026 Guruprasath Annadurai; SPDX-License-Identifier: MIT -->
# Track B local package evidence

Historical Track B checkpoint: branch/commit statements below describe that earlier run. The final successor closeout supersedes candidate status, without converting offline results into live deployment proof.

Worktree: `whitepact-website-deployment-tooling`; branch
`codex/whitepact-website-deployment-tooling`; starting HEAD
`c9622a2539f20314205e1c30a0f4b8de3927b8f4`. New package is uncommitted and
unqualified. Frozen Phase 4 checkout remains clean and unchanged. No PR, commit,
push, deployment, external target call, DNS/provider mutation or production action.

| Fresh check | Result | Boundary |
|---|---|---|
| New offline deployment tests after Phase-1 extension | 13 passed, 0 failed, 0 skipped | Real local filesystem fixtures, no network |
| Node syntax and git diff whitespace | PASS | Tooling only |
| Locked web npm ci and TypeScript/Vite production build | PASS | Own Track B worktree, no new dependency |
| Inherited launch-contract tests after build | 11 passed, 0 failed, 0 skipped | Own built output |
| Own rebuilt output vs frozen Phase 4 output | 58 byte-identical files | Read-only SHA-256 comparison |
| Frozen qualified artifact and clean manifest verification | PASS, 58 files, 15 public routes | Expected exact SHA/tree matched; no independent attestation claim |
| Same-release offline restoration/reference rehearsal | PASS, 35 assets, 212 references | No infrastructure activation; real previous-to-next release exercise remains required |
| Negative fixtures | PASS | Tamper, missing/extra files, symlink, traversal, dirty flag, noncanonical origin, staging/production mix, asset collision, missing HTML dependency, private route |
| Offline evidence generation | PASS | Deterministic canonical manifest digest, proposed release directories/current+previous pointers, failure state plan; external checks all NOT VERIFIED |
| Real TLS/DNS/edge/origin protection | NOT VERIFIED | Future approved infrastructure evidence |
| Real maintenance activation / emergency rollback | NOT VERIFIED | Future authorized staging exercise |

The inherited suite initially reported 6 pass / 5 fail because the fresh worktree
had no generated `public-routes.json` (ignored build outputs are not copied by
git worktree). The required locked install/build supplied that prerequisite;
the fresh own-tree rerun passed all 11. No assertion was weakened and no source
defect was inferred. Existing npm notices concern deprecated build tooling, not
a newly introduced dependency. An exploratory attempt to use the Phase 4
manifest command in a Phase 3 checkout failed because that command did not exist
at Phase 3; no prior-release deployment evidence is claimed from that attempt.

## Coverage of the 15 deliverables

All 15 are explicitly numbered in
[DEPLOYMENT_AND_ROLLBACK_PACKAGE.md](DEPLOYMENT_AND_ROLLBACK_PACKAGE.md).
Artifact verification and emergency asset/reference rehearsal have executable
offline tooling and negative tests. Staging/production, reverse-proxy, Cloudflare,
TLS, HSTS, cache, maintenance and actual rollback remain operator requirements.
Prepared acceptance commands are not executed live. Release evidence template
starts every external/owner field PENDING or NOT VERIFIED.

Phase-1 continuation adds concrete proposed immutable release directories,
same-filesystem atomic symlink replacement, expected-current comparison,
multi-instance convergence requirements, before/after-switch failure recovery,
previous-release byte restoration and deterministic offline JSON evidence.
No operational activation script is created. Fresh tests specifically prove
evidence generation cannot make an external verification/deployment claim and
tampered next-release bytes block generation while prior bytes still verify.

## Remaining authority and dependency gates

Owner-approved domain/deployment target and artifact; legal/security/support/
commercial/package identity decisions; current-main integration reconciliation;
independent review of new tooling; product/security/cloud qualification; approved
LB/reverse-proxy route map; origin-hop TLS and origin protection; final Track C
harness; actual staging acceptance and rollback rehearsal. None is silently
closed by local fixture results. The verifier checks manifest integrity, not
manifest authenticity: operators must use independently qualified expected
identity/digests. Qualified Phase 4 candidate remains unchanged.
