# Internationalization (i18n)

**Date established**: 2026-08-18 (OpenSSF Silver `internationalization` remediation — see `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` item 15).

## Approach

The goal here was structural: make the dashboard's frontend genuinely
localizable, prove the mechanism works end-to-end with a real second
locale, and do it without a build step or a heavy framework — the existing
frontend is vanilla JS/HTML with no bundler. This is **not** a claim that
every string in every page is translated; it's a real, working
architecture that a contributor can extend page by page.

## Architecture

- **`src/responsibleai/dashboard/static/js/i18n.js`** — the whole module.
  No dependencies, loads in both a browser and plain Node (guarded via
  `typeof` checks around `document`/`localStorage`/`navigator`/`fetch`).
- **Message catalogs**: plain JSON files under
  `src/responsibleai/dashboard/static/locales/<locale>.json` — one file per
  locale, flat key → string (or `{"one": ..., "other": ...}` for
  pluralized keys).
- **Locale resolution**: `RAI.i18n.detectLocale()` checks, in order, a
  stored preference (`localStorage`), then `navigator.languages`, then
  falls back to `en`. A region subtag (`es-MX`) is stripped before
  matching, so a regional variant still resolves to `es`.
- **Fallback chain**: `RAI.i18n.t(key)` looks up `key` in the current
  locale's catalog, falls back to the default locale (`en`), and finally
  falls back to the key itself — a missing translation degrades to a
  visible-but-harmless string, never a crash or blank UI.
- **Interpolation**: `{placeholder}` tokens in a catalog string are
  replaced from a `params` object, e.g. `t("greeting", {name: "Ada"})`.
- **Pluralization**: `RAI.i18n.tPlural(key, count, params)` for keys whose
  catalog value is `{"one": "...", "other": "..."}` — the simplified
  English/Spanish two-category rule (exactly 1 vs. everything else, per
  CLDR), not a full CLDR plural-rules implementation. If a locale is ever
  added whose plural system doesn't fit this (many languages need more
  than two categories — Arabic, Polish, Russian, etc.), `pluralize()` in
  `i18n.js` is the one place that needs a real CLDR plural-rules library;
  not needed for `en`/`es`.
- **Number/date formatting**: `RAI.i18n.formatNumber()` /
  `RAI.i18n.formatDate()` are thin wrappers around the built-in
  `Intl.NumberFormat`/`Intl.DateTimeFormat`, bound to the current locale —
  no reimplementation, no new dependency.
- **Zero-flash default locale**: `en`'s catalog is embedded directly in
  `i18n.js` (`EMBEDDED_DEFAULT_CATALOG`), not fetched, so the very first
  synchronous render is always correctly translated — never a flash of
  raw `nav.overview`-style keys while a network request is in flight. A
  Node test (`tests/js/i18n.test.js`) asserts this embedded copy never
  drifts from `static/locales/en.json` — update both together.
- **Non-default locales are fetched.** Switching to (or detecting) a
  non-default locale fetches `/static/locales/<locale>.json` once per page
  load and caches it in memory. This means a visitor whose browser prefers
  a non-English locale sees a brief flash of English before the real
  translation loads — a real, honestly-stated limitation of a no-bundler,
  no-SSR static frontend (see "Known limitations" below).

## Wiring into the shared app shell

`src/responsibleai/dashboard/static/js/app.js`'s `shell()` function (the
sidebar/topbar renderer loaded by every dashboard page) is the integration
point: `NAV`'s labels are i18n keys (`labelKey`/`groupKey`), not literal
English strings, and every topbar string (`Toggle theme`, `Logout`,
`Sign up`, `Login`, `Toggle navigation`) goes through `t()`.

A locale `<select>` in the topbar lets a visitor switch languages live,
without a page reload. Two design choices here matter:

1. **`shell()` stays synchronous.** Every existing page's own inline
   `<script>` calls `RAI.shell("pageId")` and then immediately does
   `document.getElementById("rai-page-content")` — a classic synchronous
   DOM-ready contract this codebase already depended on before i18n
   existed. Making `shell()` return a `Promise` broke every page that
   relied on this (a real bug found and fixed during this work — see
   `git log` on `app.js` for the incident). `shell()` renders
   synchronously using whatever catalog is already cached (the embedded
   default, or a previously-fetched locale), then asynchronously upgrades
   to the visitor's real preferred locale if needed.
2. **Locale switches never touch `#rai-page-content`.** The chrome
   (sidebar `<nav>` + topbar `.actions`) is re-rendered in place; the
   page's own content area — a filled-in form, a loaded results table —
   is left completely alone. Verified manually: filled a form field,
   switched locale, confirmed the value survived (see the PR that added
   this document for the walkthrough).

## Adding a new locale

1. Copy `static/locales/en.json` to `static/locales/<code>.json` and
   translate every value. Keep the same keys — `tests/js/i18n.test.js`
   fails the build if any key is missing or stale relative to `en.json`.
2. For any pluralized key (an object value), provide both `"one"` and
   `"other"` forms — also enforced by the same test.
3. Add `<code>` to `SUPPORTED_LOCALES` in `i18n.js`.
4. Run `npm run test:i18n` locally, then `npm run a11y` (contrast/label
   fixes sometimes interact with longer translated strings — worth a
   fresh scan).
5. Manually verify in a browser: switch to the new locale via the topbar
   selector, confirm the nav/topbar render correctly, confirm reloading
   the page persists the choice (`localStorage`).

## Extending translation coverage beyond the shared shell

Only the shared app shell (sidebar/topbar, ~18 pages) is wired through
`i18n.js` today. Each page's own content — forms, tables, page-specific
copy — is still literal English. To extend a specific page:

1. Add the new strings as keys to `static/locales/en.json` (and every
   other locale file — the completeness test will catch a miss).
2. Replace the literal string in the page's HTML/inline script with
   `RAI.i18n.t("your.new.key")`.
3. If the string needs to update after a locale switch (most page content
   loads once and doesn't re-render), listen for a locale-change signal —
   not currently emitted by `i18n.js`; adding a simple event
   (`window.dispatchEvent(new CustomEvent("rai:locale-changed"))` inside
   `setLocale()`) is the natural next step if/when page-content
   translation is tackled, not built speculatively here.

## Tests

- **`tests/js/i18n.test.js`** — Node's built-in test runner (`node:test`),
  zero new dependency. Covers: locale resolution (stored preference,
  navigator fallback, region-subtag stripping, unsupported-locale
  fallback), interpolation (substitution, missing-param safety,
  non-string-template safety), catalog lookup (locale hit, default-locale
  fallback, missing-key-returns-key-itself), pluralization (one/other
  selection, missing-form fallback), and two catalog-integrity checks: the
  embedded default catalog matches `en.json` exactly, and `es.json` has no
  missing or stale keys relative to `en.json`.
- **Run locally**: `npm install && npm run test:i18n`.
- **CI**: `.github/workflows/ci.yml`'s `i18n-tests` job — hard gate, no
  Python/dashboard server needed, just Node.

## Known limitations, stated honestly

- **Only the shared app shell is translated** — 21 UI strings (nav labels,
  topbar) across the ~18 pages that use `RAI.shell()`. Page-specific
  content (forms, tables, results) is still English-only. This is a real,
  structural start, not full localization — extending it page by page is
  future work, tracked here rather than implied as done.
- **A brief English flash on non-default locales.** Explained above under
  "Non-default locales are fetched" — inherent to a static-file frontend
  with no server-side rendering, not something this pass tried to hide.
- **Two-category pluralization only** (`one`/`other`). Correct for English
  and Spanish; a locale needing CLDR's fuller plural categories (Arabic,
  Polish, Russian, etc.) would need `pluralize()` in `i18n.js` upgraded to
  a real plural-rules implementation first.
- **`es.json`'s translations were produced by this pass**, not reviewed by
  a native Spanish speaker. Functionally correct and unambiguous, but
  should be treated as a first draft worth a native-speaker pass before
  being presented as production-quality translation, not just a working
  demonstration of the architecture.

## Reporting an issue

Open a [GitHub issue](https://github.com/Guruprasath-Annadurai/Whitepact/issues)
for a missing/incorrect translation, a locale-detection bug, or a request
to extend i18n coverage to a specific page.
