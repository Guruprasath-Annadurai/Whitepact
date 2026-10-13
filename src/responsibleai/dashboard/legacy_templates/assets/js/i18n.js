// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
/* ResponsibleAI i18n -- lightweight, dependency-free message-catalog
   architecture. Locale catalogs are plain JSON files under
   /static/locales/<locale>.json, fetched on demand and cached in memory.
   Number/date formatting is delegated to the built-in Intl API rather than
   reimplemented.

   The resolution/interpolation/lookup/pluralization logic below is pure
   (no DOM, no fetch, no localStorage) specifically so it's unit-testable
   from plain Node -- see tests/js/i18n.test.js. Only init()/setLocale()/
   loadCatalog() touch the browser environment, guarded so this file also
   loads cleanly under Node for tests.

   Usage: RAI.i18n.t("nav.overview"), RAI.i18n.setLocale("es"),
   RAI.i18n.formatNumber(1234.5), RAI.i18n.formatDate(new Date()). */
(function (global) {
  "use strict";

  const LOCALE_KEY = "rai_locale";
  const DEFAULT_LOCALE = "en";
  const SUPPORTED_LOCALES = ["en", "es"];

  // ---- Pure functions (no browser globals touched) ------------------------

  /** Resolve the first supported locale among `candidates` (e.g. a stored
   * preference followed by navigator.languages), else `fallback`. Each
   * candidate's region subtag is stripped ("es-MX" -> "es") before matching,
   * so a browser reporting a regional variant still resolves correctly. */
  function resolveLocale(candidates, supported, fallback) {
    for (const candidate of candidates || []) {
      if (!candidate) continue;
      const base = String(candidate).split("-")[0].toLowerCase();
      if (supported.indexOf(base) !== -1) return base;
    }
    return fallback;
  }

  /** Replace {placeholder} tokens in `template` with values from `params`.
   * A placeholder with no matching param is left as-is (never throws,
   * never silently drops the token). */
  function interpolate(template, params) {
    if (!params || typeof template !== "string") return template;
    return template.replace(/\{(\w+)\}/g, function (match, key) {
      return Object.prototype.hasOwnProperty.call(params, key) ? String(params[key]) : match;
    });
  }

  /** Look up `key` in `catalogsMap[locale]`, falling back to
   * `catalogsMap[defaultLocale]`, and finally to the key itself so a
   * missing translation degrades to a visible-but-harmless string instead
   * of a crash or blank UI. */
  function lookup(catalogsMap, locale, defaultLocale, key) {
    const localeCatalog = catalogsMap[locale];
    if (localeCatalog && Object.prototype.hasOwnProperty.call(localeCatalog, key)) {
      return localeCatalog[key];
    }
    const fallbackCatalog = catalogsMap[defaultLocale];
    if (fallbackCatalog && Object.prototype.hasOwnProperty.call(fallbackCatalog, key)) {
      return fallbackCatalog[key];
    }
    return key;
  }

  /** Pick the "one" or "other" plural form for `count`. Catalog entries for
   * pluralized keys are objects {"one": "...", "other": "..."} rather than
   * plain strings -- CLDR's simplified two-category English/Spanish plural
   * rule (exactly 1 vs. everything else), sufficient for this UI's actual
   * pluralized strings without pulling in a full CLDR plural-rules library. */
  function pluralize(count, forms) {
    if (count === 1 && forms.one !== undefined) return forms.one;
    return forms.other !== undefined ? forms.other : "";
  }

  // ---- Stateful wrapper (browser-facing) -----------------------------------

  // The default locale's catalog is embedded here, not fetched, so the very
  // first synchronous render (see app.js's shell()) never shows raw
  // "nav.overview"-style keys while a network request is in flight. This is
  // intentionally kept identical to static/locales/en.json --
  // tests/js/i18n.test.js asserts the two never drift apart.
  const EMBEDDED_DEFAULT_CATALOG = {
    "nav.group.overview": "Overview",
    "nav.group.evaluate": "Evaluate",
    "nav.group.cost_trust": "Cost & Trust",
    "nav.group.governance": "Governance",
    "nav.group.account": "Account",
    "nav.overview": "Dashboard",
    "nav.evaluate": "Evaluate Model",
    "nav.guardrails": "Guardrails",
    "nav.hallucination": "Hallucination",
    "nav.eval": "Compare & Benchmark",
    "nav.redteam": "Red Team",
    "nav.cost": "Cost Intelligence",
    "nav.router": "Model Router",
    "nav.trust_scores": "Trust Scores",
    "nav.leaderboard": "Leaderboard",
    "nav.audit": "Audit Log",
    "nav.incidents": "Incidents",
    "nav.incident_db": "Incident Database",
    "nav.webhooks": "Webhooks",
    "nav.organizations": "Organizations & Access",
    "nav.billing": "Billing",
    "nav.settings": "Settings",
    "topbar.toggle_nav": "Toggle navigation",
    "topbar.toggle_theme": "Toggle theme",
    "topbar.logout": "Logout",
    "topbar.signup": "Sign up",
    "topbar.login": "Login",
    "topbar.locale_label": "Language",
    "toast.results_count": { "one": "{count} result", "other": "{count} results" },
  };

  const catalogs = { en: EMBEDDED_DEFAULT_CATALOG };
  let currentLocale = DEFAULT_LOCALE;

  function detectLocale() {
    const hasLocalStorage = typeof localStorage !== "undefined";
    const stored = hasLocalStorage ? localStorage.getItem(LOCALE_KEY) : null;
    const nav = typeof navigator !== "undefined" ? navigator : null;
    const navLangs = (nav && nav.languages && nav.languages.length)
      ? nav.languages
      : (nav && nav.language ? [nav.language] : []);
    return resolveLocale([stored].concat(navLangs), SUPPORTED_LOCALES, DEFAULT_LOCALE);
  }

  async function loadCatalog(locale) {
    if (catalogs[locale]) return catalogs[locale];
    try {
      const res = await fetch("/static/locales/" + locale + ".json");
      const data = await res.json();
      catalogs[locale] = data;
      return data;
    } catch (e) {
      catalogs[locale] = {};
      return catalogs[locale];
    }
  }

  async function setLocale(locale) {
    const resolved = SUPPORTED_LOCALES.indexOf(locale) !== -1 ? locale : DEFAULT_LOCALE;
    await loadCatalog(DEFAULT_LOCALE);
    if (resolved !== DEFAULT_LOCALE) await loadCatalog(resolved);
    currentLocale = resolved;
    if (typeof localStorage !== "undefined") localStorage.setItem(LOCALE_KEY, resolved);
    if (typeof document !== "undefined" && document.documentElement) {
      document.documentElement.setAttribute("lang", resolved);
    }
  }

  function getLocale() {
    return currentLocale;
  }

  /** Synchronous, no-fetch initialization: sets currentLocale to the
   * detected preference if its catalog is already cached in memory
   * (always true for the default locale; true for others only if
   * loadCatalog() already ran earlier this page load), else falls back to
   * the default locale. Returns the locale actually selected. Callers that
   * need the *real* detected locale even when its catalog isn't cached yet
   * should follow up with the async setLocale()/init() once they can
   * tolerate awaiting a fetch -- see app.js's shell(), which renders
   * synchronously via initSync() first (so DOM consumers relying on
   * shell()'s classic synchronous contract keep working), then upgrades
   * to the real locale asynchronously if needed. */
  function initSync() {
    const detected = detectLocale();
    currentLocale = catalogs[detected] ? detected : DEFAULT_LOCALE;
    if (typeof document !== "undefined" && document.documentElement) {
      document.documentElement.setAttribute("lang", currentLocale);
    }
    return currentLocale;
  }

  async function init() {
    await setLocale(detectLocale());
  }

  function t(key, params) {
    return interpolate(lookup(catalogs, currentLocale, DEFAULT_LOCALE, key), params);
  }

  function tPlural(key, count, params) {
    const entry = lookup(catalogs, currentLocale, DEFAULT_LOCALE, key);
    const template = (entry && typeof entry === "object") ? pluralize(count, entry) : entry;
    return interpolate(template, Object.assign({ count: count }, params || {}));
  }

  function formatNumber(value, options) {
    try {
      return new Intl.NumberFormat(currentLocale, options).format(value);
    } catch (e) {
      return String(value);
    }
  }

  function formatDate(value, options) {
    try {
      return new Intl.DateTimeFormat(currentLocale, options).format(value);
    } catch (e) {
      return String(value);
    }
  }

  const i18n = {
    init: init,
    initSync: initSync,
    setLocale: setLocale,
    getLocale: getLocale,
    detectLocale: detectLocale,
    t: t,
    tPlural: tPlural,
    formatNumber: formatNumber,
    formatDate: formatDate,
    SUPPORTED_LOCALES: SUPPORTED_LOCALES,
    DEFAULT_LOCALE: DEFAULT_LOCALE,
    EMBEDDED_DEFAULT_CATALOG: EMBEDDED_DEFAULT_CATALOG,
    // Exposed so tests can exercise the pure logic directly without a DOM.
    _internal: { resolveLocale: resolveLocale, interpolate: interpolate, lookup: lookup, pluralize: pluralize },
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = i18n;
  }
  if (typeof global !== "undefined") {
    global.RAI = global.RAI || {};
    global.RAI.i18n = i18n;
  }
})(typeof window !== "undefined" ? window : globalThis);
