# M11 ownership ledger — before implementation

Codex worktree: `/Users/ag/whitepact-m11-product-integration`.
Branch: `codex/whitepact-m11-product-integration`.
Immutable starting parent: `62be9caa70e6c2eb1c4782a64554323646d987e0` (PR #202).
Parent tree: `474e0fd2177dc789893911c987389cfe6c7b1adf`.

Antigravity M10 reference: local commit `c801f33f369e3727360bc55d6df15083025dc754`;
not integrated, not accepted as proof. The named remote branch was not returned
by the initial exact-ref check; publication/current head must be reconciled.

| Owner | Write surface / restrictions |
|---|---|
| Codex coordinator | Customer React/UI client contracts/tests, SDK examples, new M11 CI, generated frontend artifacts, new M11 documentation |
| Codex read-only discovery lane | Product archaeology and source-backed inventory; no existing code, contracts or database changes |
| Codex offline infrastructure lane | New offline tooling/templates/tests only; never shared Cloudflare routing, provider resources, credentials, remote state, plan/apply or paid services |
| Antigravity | Root/consent, identity/security authority, policy/risk kernels, delegation/revocation, containment/egress, signing/witnesses, security-sensitive billing, CodeQL and Cloudflare routing |

Application/agent schema and authority association require a reviewed canonical
contract before migrations or new server-side lifecycle mutations. No browser
registration may mint authority. Proposed contracts are explicitly unsupported
until supplied/approved by the security owner.

Prior PRs #198–202 and M10 remain untouched. Only normal isolated feature-branch
publication and reviewable draft PRs are in scope. GLOBAL PRODUCTION NO-GO;
unapproved expenditure zero. No protected merge, rebase, force push, release tag,
package publication, DNS/cloud mutation, deployment, Terraform apply or live signup.
