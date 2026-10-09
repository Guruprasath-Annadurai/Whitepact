# WHITEPACT — unified security integration candidate

This candidate is for independent qualification. It is not a FULL PASS, not a staging GO, and not production readiness. Live staging remains NO-GO. Existing pull requests were not merged. This tree does not apply Terraform, change DNS, activate billing, or publish a release.

The pull-request body records `git rev-parse HEAD` and `git rev-parse 'HEAD^{tree}'` after the tip commit. Reject the packet if those values differ.

## Verified remote heads before integration

| PR | Branch | HEAD | Ancestry against the integration base |
| --- | --- | --- | --- |
| #171 | `cursor/whitepact-canonical-reconcile-d20d` | `6801d4ad0047d15a196ab9caeffacf54f9ce557e` | Ancestor of the base. Not modified. |
| #172 | `cursor/whitepact-phase3-preflight-b6a9` | `7a0852899afd997264c384a9ff5ca5f99a65c7ca` | Not an ancestor. Parent is `6fefece7b7620ae2f1fa7c307f6720e4bbde709f`. |
| #173 | `cursor/whitepact-phase34-staging-preflight-00f5` | `4d77c8e7290940e883479e2c49fbd231df2ff2da` | Integration base. That pull request was not modified. |
| #174 | `cursor/whitepact-foundation-hardening-934e` | `5c9c74787903d96d74b3789a40caa94ca3d73c52` | Not merged. |

`origin/main` at verification was `38f927229b4ea53d19a9107c78653307f5263629`. The merge base of PR #173 and PR #174 is `6fefece7b7620ae2f1fa7c307f6720e4bbde709f` (tree `043b5f14f63b32ea60d3c168d4fcf3bf27800d14`).

## Foundation commits integrated

These are cherry-picks of the five remediation commits. They are not a merge of PR #174.

| Source | Integrated as | Subject |
| --- | --- | --- |
| `cdef4c7ae4ae96c90b28843b11f7cf7a01877fb7` | `db667d8b8e561ecf77b1e1c90231800b9fb38332` | Authority HTTPS stays on the egress allowlist |
| `2bccc8b9af1341f434648b48498deffb05aac426` | `1b6a6abe2cec6a368ff1c53d6bd790582246b58e` | Trust lookup failure requires approval |
| `29f8b245118dec010cbde7df42eaec9dd93bd5f2` | `eb46b23b4942c05c2c827d59a35889d86c247cc8` | Stricter rules hidden by an earlier match are rejected |
| `06093e1cca1fdc5c8bce8a9f1213fb6eebb9898e` | `ebd2e102ee364b6006db4f3fa73a6d0846dd6c53` | Key rotation does not multiply ceilings |
| `bfbd9afb8312181578f889389e57b8d1b3dccd2d` | `7981756e54f74713cc72fcf07c6efd2201c60af2` | A recomputed hash chain is not an external witness |

## Firewall and policy resolution

`locals.tf` and `docs/enterprise/cloud/CLOUD_HOST_FIREWALL_POLICY.md` conflicted on the authority egress wording.

The integrated tree keeps both controls:

- Authority and NAT HTTPS accepts name `authority_egress_cidrs`. There is no unrestricted `tcp dport 443 accept`.
- Each NAT forward accept also names the source subnet that owns that destination allowlist. DNS and NTP are limited to the SaaS, authority, and execution subnets.
- Pinned DNS and NTP remain on the host output chains. They are not a substitute for the HTTPS allowlist.
- Origin client-certificate staging and the execution database role boundary from PR #173 stay in the tree.

## Still unresolved

- Owner approval `APPROVE STAGING CLOUD PROVISIONING` is not granted.
- Cloudflare authenticated origin pulls, the client CA, the origin certificate and key, proxied DNS, and a real hostname are absent. `origin_client_certificate_enforced` stays false.
- The 3595 euro-cent figure remains a Terraform price-book ceiling. It is not a Hetzner billing alert and it excludes VAT and backups.
- Evidence-head publication is an external blocker. The offline witness does not make a live anchor.
- Antigravity qualification of this exact tree is still required.
