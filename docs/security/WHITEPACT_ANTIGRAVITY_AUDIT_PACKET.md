# Antigravity audit packet

Cursor implemented this tree. This file is not an independent qualification. A previous audit of another SHA does not qualify this one. Green CI would not replace this review.

Reject the packet if the pull-request body records a different `git rev-parse HEAD` or `git rev-parse 'HEAD^{tree}'` than the commit under review.

## Ancestry

| Ref | HEAD | Role |
| --- | --- | --- |
| `origin/main` | `38f927229b4ea53d19a9107c78653307f5263629` | Ancestor. Not the release candidate. |
| PR #171 | `6801d4ad0047d15a196ab9caeffacf54f9ce557e` | Ancestor of the integration base. |
| PR #172 | `7a0852899afd997264c384a9ff5ca5f99a65c7ca` | Not an ancestor. Docs-only tip past `6fefece7b7620ae2f1fa7c307f6720e4bbde709f`. |
| PR #173 | `4d77c8e7290940e883479e2c49fbd231df2ff2da` | Ancestor. Staging preflight base. |
| PR #174 | `5c9c74787903d96d74b3789a40caa94ca3d73c52` | Not merged. Five remediation commits were cherry-picked onto PR #173 as PR #175. |
| PR #175 | `8aea364ac586e6498fefc4fa37de55a7e25c1bf7` | Parent of the two fixes below. Tree `10b814e2800685446d0deb88afe972cf64eccee6`. |

Fixes on this candidate:

- `1e75790f68902f01f9a16bf04d904f2ac732045d` tenant binding
- `1b974d5f83c875891322884530baef6e5fe0cbc7` trust-gate claims

## What to retest

1. A VC from a configured trusted issuer with a missing `orgId`, or an `orgId` that `OrgRepository.get_org` does not return, receives HTTP 401 on `/mcp` and does not insert `verified_principals`.
2. The same VC with an existing organization still lists tools.
3. Dashboard `_resolve_oidc_context` and `_resolve_saml_context` return `None` when the organization is missing or the claim has no org id. A SAML session token without `org_id` receives HTTP 401 on `/api/auth/session`. A token whose `org_id` exists returns that organization.
4. `A2ATrustGate` denies a `TrustCheckResult` with `error` set, and the reason contains `trust lookup unavailable`. A known high score with a benign message still allows.
5. FH-01 through FH-07 from `docs/security/WHITEPACT_FOUNDATION_HARDENING_REPORT.md` still hold on this tip. Live evidence publication remains `EXTERNAL_BLOCKER`.
6. Authority nftables output still has no unrestricted `tcp dport 443 accept`.

## Local evidence

Python 3.12.3, 59 passed:

`pytest tests/test_mcp_verified_principal.py tests/test_saml_app_routes.py tests/test_final_coverage_batch13.py::TestIdentityResolutionBatch13 tests/test_a2a_adapter.py tests/test_langchain_middleware.py`

Python 3.11 was not executed in this session. Full-repository coverage, soak, and load tests were not executed. No Terraform apply. No production deploy. No merge to `main`.

## Known limits

- IdP-asserted roles are still taken from the verified token after the organization exists. This change checks that the tenant row exists. It does not add a second membership directory.
- Community stdio remains ungoverned. Enterprise mode still refuses it.
- Direct imports of governance engines are outside the hosted boundary.
- Staging remains NO-GO until the owner authorizes provisioning and the origin material exists.
