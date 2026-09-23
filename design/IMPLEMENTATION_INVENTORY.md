# WhitePact web implementation inventory

## Surfaces

The coordinated design references are `design/concepts/01-homepage-hero.png` through
`design/concepts/20-mobile-dashboard.png`. Implementation order follows the commercial and
security boundary rather than screenshot order:

1. Shared tokens, brand assets, navigation, responsive shell, accessibility primitives.
2. Public homepage, governance demo, platform, MCP, passport, evidence, pricing, trust, CTA.
3. Human account registration, email verification, login, session, logout, recovery boundary.
4. Organization onboarding and membership.
5. Stripe Checkout, webhook-confirmed subscription, entitlement evaluation, Customer Portal.
6. One-time API-key creation, rotation/revocation, scopes, environment, optional expiry.
7. Dashboard overview, agents, keys, usage, policies, approvals, evidence, MCP, billing,
   organization, members, and settings.
8. Mobile/reduced-motion/WebGL fallback and cross-browser QA.

## Backend security invariants

- Human sessions and machine API keys are separate credential types.
- Passwords use a memory-hard KDF; verification tokens and session tokens are stored hashed.
- Browser sessions use Secure, HttpOnly, SameSite cookies and CSRF protection for mutations.
- Every database lookup derives organization scope from the authenticated principal.
- A browser redirect never activates paid entitlement.
- Only a verified Stripe webhook may update subscription state.
- Raw API keys are generated with a CSPRNG, displayed once, never logged, and never persisted.
- Rotation creates and commits a new unique key while revoking the old key in one transaction.
- Revocation/deletion is permanent; a later key creation always creates a new random secret.
- OWNER/ADMIN human authority is not embedded in service API keys by default.
- Sensitive changes and key lifecycle events create audit records.

## Frontend architecture

- `web/`: React, TypeScript, Vite, router, feature folders, design tokens.
- `web/src/components`: brand, navigation, forms, tables, feedback, 3D/fallback.
- `web/src/features`: marketing, auth, onboarding, billing, api-keys, dashboard domains.
- Production output is copied into the packaged FastAPI static directory by the web build.
- The Python server owns API validation, sessions, entitlement, key generation, and Stripe.

## Hero asset boundary

`design/assets/trust-core-head.png` is the approved transparent visual/fallback. It can be
used on a texture plane with restrained depth/parallax while the scene state machine controls
semantic signal overlays. It is not evidence of a sculpted GLB. A genuine GLB claim requires
an original model file, provenance/licensing record, geometry/texture optimization, and
measured runtime verification.

## Concept copy corrections before shipping

- Remove concept-only or unsupported claims such as end-to-end encrypted browser sessions,
  signed Agent Passports, immutable evidence, and sample customer/production statistics.
- Use runtime API values or empty states; sample data appears only in explicitly labelled
  product demonstrations.
- Prices remain configuration-driven until approved Stripe Price objects exist.
