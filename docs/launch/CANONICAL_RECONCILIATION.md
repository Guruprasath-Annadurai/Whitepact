# Canonical security reconciliation

PR #169 (`d2f5405e9c31e6b5676c1c327e4c1de2c0379e56`) and PR #170 (`996795adeac0adbad9eec9c9ca51e2f8aa4c80fc`) share parent `47adb948d76746ce7166ae4a49503b671006049d`. Neither commit is an ancestor of the other. This branch merges both without rewriting them.

## What each candidate added

| Area | PR #169 | PR #170 | Canonical choice |
|------|---------|---------|------------------|
| Memory-scope format | Prefix rule from `47adb948`. `org:acme:` and padded segments still matched. | Rejects empty, padded, and empty-segment scopes in `validate_attenuation`. | PR #170. Equal and colon-delimited descendants stay allowed. |
| Delegation repository, API, concurrency | Grant path, HTTP 422, multi-hop, and concurrent tests. | Resolver test after a stored grant is widened in the database. | Union. |
| Gateway | Deny widened child before execution. | Also deny when the request itself stays inside the parent, and deny a cross-tenant read. | Union. |
| Action pins | Policy-gate mutation of the real workflows, including list form. | Unit mutations for tags, branches, short SHAs, and quoted refs. | Union. The checker still requires a 40-hex SHA. |
| Evidence checker | Binds HEAD, TREE, environment, verification authority, `https` URL, and `sha256` digest. Production authorization stays `NO-GO`. | Declares completeness without binding the candidate, and also stays `NO-GO`. | PR #169 bindings. Placeholder, `localhost`, `127.0.0.1`, non-`https`, and whitespace URLs stay incomplete. Self-declared `GO` fields are ignored. |
| CI checkout identity | Compares the synthetic merge tree with the candidate HEAD. | Not present. CI ran because the PR targeted `main`. | Kept. This pull request stays off `main`. |

`DelegationRepository.grant` and `AuthorityResolver` already call `validate_attenuation`. No second enforcement path was added. A denied grant is still not inserted, so it cannot become the parent of a later hop.

Production authorization from `scripts/release_evidence_check.py` remains `NO-GO` until an external verifier fetches the artifact and an owner records approval outside this packet.
