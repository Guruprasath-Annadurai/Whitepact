# Architecture & Package-Boundary Decision Record — A005

**Date:** 3 November 2026 (Asia/Calcutta)  
**Status:** Accepted for internal Community Core prototype  
**Package name:** `whitepact-community` (`0.1.0a1`)  
**Baseline OSS candidate SHA:** `19f8d4b6b570d03baa87845867e5f9b268b6d6e6`  
**Private repo access:** `whitepact-internal` was not reachable from this agent environment (404); engineering proceeds from the verified public OSS candidate head matching Public PR #2.

## Decision

Ship Community Core as a **new, small, independently functional package** under `packages/whitepact-community/`, rather than exporting a provisional subset of the monolithic `rai-governance-platform` tree.

### Why

Independent reproduction of the OSS candidate confirmed:

1. Hatch packages the entire `src/responsibleai` tree (dashboard, billing, db, auth) into the public wheel.
2. Eager `responsibleai/__init__.py` couples trust imports to sklearn/ML stacks.
3. Empty subpackage `__init__.py` files break advertised public imports.
4. MCP governance integration imports dashboard Prometheus metrics.
5. CLI depends on undeclared `rich`.
6. Shared tests require dashboard/db/auth/stripe.

Wholesale subsetting of the 612-file tree cannot produce a clean import closure without invasive breaks to the enterprise tree. A005 prefers a small standalone package with explicit interfaces.

### Naming

| Candidate | PyPI | Choice |
| --- | --- | --- |
| `whitepact` | available | Reserved; avoid colliding with future product rename |
| `whitepact-core` | available | Ambiguous vs enterprise core |
| `whitepact-community` | available | **Selected** — explicit edition boundary |
| `rai-governance-platform` | exists 1.2.6 | Remains the broad/historical distribution |

### Boundaries

**Community Core includes**

- Local SDK (`GovernanceClient`)
- MCP stdio (4 local tools)
- CLI (`wpc` / `whitepact-community`)
- Deny-by-default policy + authority grants
- Local evidence hash chain
- Revocation epochs, expiry, single-use execution authorizations
- Default-deny release exporter (synthetic trust roots only)

**Private Enterprise remains**

- SaaS dashboard and hosted APIs
- Billing/Stripe/subscriptions
- Enterprise identity (OIDC/SAML/MFA/VC)
- Production tenant controllers
- Commercial entitlements and connectors
- Signed cross-host execution permits
- Hosted MCP HTTP + licensing

When ownership is uncertain, classification stays **PRIVATE**.

### Compatibility

The existing `rai-governance-platform` tree is **not** gutted. Community Core does not import it. Private enterprise may later adapt via explicit interfaces; no enterprise modules were deleted or rewritten for cosmetic package cleanliness.

### Non-goals

- Public PyPI upload of `whitepact-community`
- Expanding the protected publication allowlist
- Weakening deny-by-default governance
- Configuring live Founder release identity
