# WhitePact product design system

Status: implementation specification derived from `design/concepts/01-20`.

## Product idea

WhitePact is the trust layer between an agent's intention and real-world action. The visual
system is built around one mechanically credible object: the WhitePact Trust Core. Its
vertical red Decision Axis connects identity, authority, policy, risk, approval, decision,
and evidence. Red always means active evaluation or enforcement; it is never ambient
decoration.

## Tokens

| Token | Value | Use |
| --- | --- | --- |
| `--wp-bg` | `#050607` | primary true-black canvas |
| `--wp-surface` | `#0b0d10` | app rails and elevated operational regions |
| `--wp-surface-2` | `#111419` | selected rows and drawers |
| `--wp-text` | `#f4f5f6` | primary copy |
| `--wp-muted` | `#9ba1aa` | supporting copy and metadata |
| `--wp-border` | `rgba(255,255,255,.12)` | rules and field borders |
| `--wp-red` | `#f51b2b` | WhitePact enforcement and primary action |
| `--wp-cyan` | `#5ed6e6` | verified identity and evidence |
| `--wp-amber` | `#f2b84b` | authority and caution |
| `--wp-green` | `#5bd17c` | permitted/healthy state |
| `--wp-violet` | `#a984ef` | human approval state |
| `--wp-danger` | `#ff5057` | denied, revoked, destructive |

Surfaces use thin rules and open spacing. Cards are reserved for a real containment need,
not used as the default layout. Radius scale: 0, 4, 8, 12px. Shadow is sparse and dark;
the hero asset uses no colored overlay.

## Typography

- Display: `Sora`, 400-600, tight tracking. Hero desktop clamps between 72-104px.
- Interface and body: `Manrope`, 400-700.
- Evidence, identifiers, code, and labels: `IBM Plex Mono`, 400-600.
- Control text is explicitly sized; browser defaults are prohibited.

## Layout

- Public maximum width: 1440px with 28-72px responsive gutters.
- Dashboard sidebar: 240px; inspector drawer: 380-440px; body uses table-first open regions.
- Desktop hero: 48% editorial copy / 52% unframed Trust Core.
- Mobile is recomposed: copy first, simplified/static Trust Core, touch-first lists, bottom
  navigation, and 44px minimum interactive targets.

## Components

- Brand mark and wordmark: supplied WhitePact artwork, never redrawn approximately.
- Buttons: solid enforcement red primary; transparent ruled secondary; text-link tertiary.
- Forms: square/soft-4px fields, persistent labels, inline validation, error announcement.
- Tables: compact rows, sticky headers where useful, semantic table markup, responsive list
  transformation on small screens.
- Status: text plus icon; color never carries meaning alone.
- Destructive action: named target, consequence, explicit confirmation, audit event.
- API-key reveal: one-time secret, copy action, irreversible warning, then immediate removal
  from client state when dismissed.
- Command palette: keyboard accessible, focus-trapped, navigation/actions only.

## Motion and 3D

- Hero motion is slow and educational: request, identity, authority, policy, risk, approval,
  decision, evidence.
- Pointer rotation is capped at two degrees. Scroll state uses damped progress and no spins.
- `prefers-reduced-motion` receives a static, high-quality Trust Core with all meaning in HTML.
- WebGL failure receives the same static fallback, never a blank canvas.
- Production must record bundle size, frame-time, mobile simplification, and asset provenance.

## Truthfulness locks

- No certification, endorsement, customer, metric, price, payment, or provider-support claim
  appears unless backed by current repository or production evidence.
- Hash chaining is described as tamper-evident, not immutable or tamper-proof.
- Compatibility, tested, submitted, under review, approved, and listed are distinct states.
- Concept sample data is never shipped as real activity. New workspaces receive honest empty
  states.

## Allowed first-viewport copy

- `Platform`, `MCP Gateway`, `Security`, `Developers`, `Pricing`, `Docs`, `GitHub`, `Sign in`
- `Get API Key →`
- `AI agents can act.`
- `WhitePact decides whether they should.`
- `Runtime trust infrastructure for autonomous AI.`
- `Identity, authority, policy, approvals, revocation and verifiable evidence across MCP,
  APIs and agent workflows.`
- `Run WhitePact locally`
- `View on GitHub`

No eyebrow, badge, proof chip, fake status, or extra hero claim is permitted.
