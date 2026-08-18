# Accessibility

**Date established**: 2026-08-18 (OpenSSF Silver `accessibility_best_practices` remediation — see `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` item 14).

## Approach

The governance dashboard's user-facing pages target **WCAG 2.1 AA**. This is
checked with an automated FLOSS scanner ([pa11y](https://pa11y.org/) /
[pa11y-ci](https://github.com/pa11y/pa11y-ci), which itself uses axe-core
and HTML CodeSniffer rules under the hood) on every CI run, against every
public and dashboard page that renders meaningful static content.

## Automated checks

- **Tool**: `pa11y-ci`, configured in `.pa11yci.json` (WCAG2AA standard).
- **Scope**: 29 pages — every public page (`/`, `/signup`, `/status`,
  `/trust`, `/leaderboard`, `/registry`, `/assess`, `/incident-db`,
  `/incident-db/report`) plus every dashboard page served under `/static/`
  (login, settings, billing, audit log, red team, incidents, webhooks,
  organizations, cost, eval, guardrails, hallucination, router, trust
  scores, and the incident-database detail/report pages).
- **CI**: `.github/workflows/ci.yml`'s `accessibility` job starts the
  dashboard locally (auth disabled, in-memory DB — no seed data needed
  since these checks run against a page's real static markup, not
  API-populated content) and runs `npx pa11y-ci --config .pa11yci.json`.
  This is a **hard CI gate** — a new violation fails the build.
- **Local run**: `npm install && npm run a11y` (requires Node 18+; the
  dashboard must already be running on `http://127.0.0.1:8765`, e.g. via
  `RAI_AUTH_ENABLED=false RAI_DB_PATH=:memory: uvicorn responsibleai.dashboard.app:app --port 8765`).

## What was found and fixed (2026-08-18 remediation)

A full scan against all 29 pages before this pass found real, concrete
issues — not zero, and not fixed by excluding pages from the scan:

1. **Insufficient text contrast in dark mode.** The shared design system
   (`src/responsibleai/dashboard/static/css/app.css`) and 9 standalone
   public pages defined `--accent` (link/text color, `#2563eb`) and `--red`
   (error/danger text color, `#dc2626`) once, reused for both text-on-background
   contrast *and* white-text-on-button-background contrast. Neither was ever
   overridden for dark mode, so several links, arrows, and status text
   failed the 4.5:1 contrast requirement against the dark background
   (`#0b0b0c`) — measured ratios as low as 3.44:1. Fixed by introducing
   separate `--link`/`--danger-text` tokens (distinct from `--accent`/`--red`,
   which stay unchanged for button backgrounds) with dark-mode-appropriate
   lighter values (`#60a5fa` / `#f87171`), verified against both the
   pure-dark background and card backgrounds (>6:1 in both cases).
2. **Unlabeled form controls.** Several inputs, selects, and textareas had
   only a `placeholder` — not an accessible name — including the six
   dimension sliders on `/assess`, search/filter fields on `/registry`,
   `/incident-db`, `incidents.html`, and `audit.html`, and the per-payload
   response textareas on `redteam.html`. Fixed with `<label for="...">` where
   a real label element made sense (the `/assess` model-name and
   provider-name fields) and `aria-label` for compact filter UI where a
   visible label isn't the right design (search boxes, severity/type
   selects).
3. **Stale repository links.** Six public pages linked to the pre-rename
   repository name (`Guruprasath-Annadurai/ResponsibleAi`, GitHub-redirected
   but not the canonical name) instead of `Guruprasath-Annadurai/Whitepact`
   — found and fixed alongside the accessibility work since it was in the
   same files.

All 29 pages passed a fresh `pa11y-ci` run after these fixes, verified
before this document was written — not assumed.

## Supported interaction modes

- **Keyboard**: standard tab order; no custom keyboard traps were
  introduced. Not separately re-verified with a dedicated keyboard-only
  walkthrough in this pass — tracked as a known gap below.
- **Screen readers**: form controls have accessible names (see above);
  headings follow a logical order on scanned pages. Not tested against a
  real screen reader (VoiceOver/NVDA) in this pass — automated scanning
  catches missing names/labels/contrast, not full assistive-technology
  usability.
- **Reduced motion**: not audited in this pass. If any page adds
  non-essential animation in the future, honor
  `prefers-reduced-motion: reduce`.

## Known limitations, stated honestly

- **Automated scanning is not a full audit.** `pa11y-ci`/axe-core catches a
  meaningful subset of WCAG success criteria (contrast, missing labels,
  landmark/heading structure, some ARIA misuse) — it does not catch
  everything a full manual audit or real assistive-technology testing
  would (logical reading order for complex layouts, meaningful focus
  management in dynamic UI, screen-reader-specific phrasing quality).
- **Only static/initial markup is scanned.** Content that appears after a
  client-side API call (e.g., populated tables, live scores) is not
  exercised by this scan, since it runs against an in-memory DB with no
  seed data. Pages were reviewed manually for this class of gap during
  this pass, but there's no automated coverage of post-fetch DOM states
  yet — a real gap, tracked here rather than silently assumed clean.
- **No dedicated keyboard-only or screen-reader walkthrough** has been
  performed as of this writing (2026-08-18) — see above.

## Reporting an accessibility issue

Open a [GitHub issue](https://github.com/Guruprasath-Annadurai/Whitepact/issues)
describing the page, the assistive technology or scenario, and what you
expected vs. what happened. Accessibility issues are treated as real bugs,
not feature requests.
