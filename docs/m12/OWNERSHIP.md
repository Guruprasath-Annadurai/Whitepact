# M12 ownership and change contract

Starting Codex head0204a06f8a9a6027837befc118376aa0b9e70cb3,
tree0c5dc6bce965f5179d8cccead13c12ee789ee014; PR203 unchanged.
New worktree `/Users/ag/whitepact-m12-product-integration`;
branch `codex/whitepact-m12-product-integration`.

M10-R reference8eb41911b49e5c39d5d046c35d5d106e3f5c0473,
tree5c209f07f9d59f35aaa95963e104e16e576b5659 matches local Git.
Common ancestor with Codex is6d20545f25561b7b88c503ecde25a5457d59e8b0.
Security worktree has active delegation_repository.py and net/egress.py changes
and new adversarial tests. No security lineage integration is authorized by
this ledger; coordinate stable contracts with Antigravity first.

| Owner | Exclusive write surface |
|---|---|
| Codex coordinator | SDK resource-path validation/tests; scripts/evidence/inspect_loaded_export.py and consumer tests; M12 workflow and overall docs. No cryptographic verification or root issuance implemented in the inspector |
| Feature registry lane | Original175 input, feature-registry.json, scripts/qualification/feature_registry.py, tests/test_m12_feature_registry.py and generated ledger/matrix only |
| Codex benchmark lane | scripts/evaluation/local_authorization_benchmark.py and telemetry/unit tests; unchanged denial-only workload, localhost-only data, no protection reduction |
| Antigravity | Identity/root/consent/authority, policy/risk, delegation/revocation, signing/witnesses, containment/egress, security billing, CodeQL and Cloudflare security routing |

SDK change contract: malformed opaque identifiers must fail locally before any
request; exact server-issued identifiers must remain bound to intended resource
path. No automatic retry, credentials disclosure, tenant assertion or authority
creation. Regression tests must detect old behavior and preserve valid requests.

The original175 numbered titles were initially absent. The founder supplied the
exact conversational inventory on15October2026. Preserve IDs/titles and treat
all historical statuses as unverified input. G1 is OPEN for independent source
mapping and qualification; do not relabel them as175 shipped products.
Root/consent and application/agent lifecycle changes need security-owner contract
review before consequential operations or migrations. Continue independent work.

GLOBAL PRODUCTION NO-GO; unapproved spend0. No main merge, deployment, apply,
cloud/DNS mutation, package publication, tag, rebase, force push, real payments or
customer invitations. Normal isolated commits/draft review PRs only.
