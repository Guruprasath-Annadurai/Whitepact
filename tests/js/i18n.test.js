"use strict";

/* Tests for the i18n module's pure logic (locale resolution, interpolation,
   catalog lookup/fallback, pluralization) plus a drift guard between the
   embedded default catalog and static/locales/en.json, and a completeness
   check that es.json has no missing keys relative to en.json.

   Uses Node's built-in test runner (node:test) and assert -- no new
   dependency for something this small. Run with: node --test tests/js/ */

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const i18n = require("../../src/responsibleai/dashboard/static/js/i18n.js");
const { resolveLocale, interpolate, lookup, pluralize } = i18n._internal;

// ---- resolveLocale --------------------------------------------------------

test("resolveLocale: a supported stored preference wins over navigator languages", () => {
  const result = resolveLocale(["es", "fr", "en"], ["en", "es"], "en");
  assert.equal(result, "es");
});

test("resolveLocale: falls through candidates to the first supported one", () => {
  const result = resolveLocale(["fr", "de", "es"], ["en", "es"], "en");
  assert.equal(result, "es");
});

test("resolveLocale: strips region subtags before matching (es-MX -> es)", () => {
  const result = resolveLocale(["es-MX"], ["en", "es"], "en");
  assert.equal(result, "es");
});

test("resolveLocale: falls back when nothing is supported", () => {
  const result = resolveLocale(["fr", "de"], ["en", "es"], "en");
  assert.equal(result, "en");
});

test("resolveLocale: falls back on empty/null candidates without throwing", () => {
  assert.equal(resolveLocale([], ["en", "es"], "en"), "en");
  assert.equal(resolveLocale(null, ["en", "es"], "en"), "en");
  assert.equal(resolveLocale([null, undefined, ""], ["en", "es"], "en"), "en");
});

test("resolveLocale: matching is case-insensitive", () => {
  assert.equal(resolveLocale(["ES"], ["en", "es"], "en"), "es");
});

// ---- interpolate ------------------------------------------------------------

test("interpolate: substitutes a single placeholder", () => {
  assert.equal(interpolate("Hello, {name}!", { name: "Ada" }), "Hello, Ada!");
});

test("interpolate: substitutes multiple placeholders", () => {
  assert.equal(
    interpolate("{count} of {total}", { count: 3, total: 10 }),
    "3 of 10",
  );
});

test("interpolate: leaves an unmatched placeholder as-is rather than dropping it", () => {
  assert.equal(interpolate("Hi {name}, you have {count} items", { name: "Bo" }), "Hi Bo, you have {count} items");
});

test("interpolate: returns the template unchanged when params is falsy", () => {
  assert.equal(interpolate("Hello, {name}!", null), "Hello, {name}!");
  assert.equal(interpolate("Hello, {name}!", undefined), "Hello, {name}!");
});

test("interpolate: returns non-string templates unchanged rather than throwing", () => {
  const obj = { one: "x", other: "y" };
  assert.equal(interpolate(obj, { count: 1 }), obj);
});

// ---- lookup -------------------------------------------------------------

test("lookup: returns the locale-specific value when present", () => {
  const catalogs = { en: { greeting: "Hello" }, es: { greeting: "Hola" } };
  assert.equal(lookup(catalogs, "es", "en", "greeting"), "Hola");
});

test("lookup: falls back to the default locale when the key is missing there", () => {
  const catalogs = { en: { greeting: "Hello" }, es: {} };
  assert.equal(lookup(catalogs, "es", "en", "greeting"), "Hello");
});

test("lookup: falls back to the key itself when missing everywhere (never crashes)", () => {
  const catalogs = { en: {}, es: {} };
  assert.equal(lookup(catalogs, "es", "en", "totally.missing.key"), "totally.missing.key");
});

test("lookup: falls back to the key itself when the locale catalog doesn't exist at all", () => {
  const catalogs = { en: { greeting: "Hello" } };
  assert.equal(lookup(catalogs, "fr", "en", "unknown"), "unknown");
});

// ---- pluralize ------------------------------------------------------------

test("pluralize: picks the 'one' form for count === 1", () => {
  assert.equal(pluralize(1, { one: "1 item", other: "{count} items" }), "1 item");
});

test("pluralize: picks the 'other' form for count !== 1, including 0", () => {
  assert.equal(pluralize(0, { one: "1 item", other: "{count} items" }), "{count} items");
  assert.equal(pluralize(2, { one: "1 item", other: "{count} items" }), "{count} items");
  assert.equal(pluralize(100, { one: "1 item", other: "{count} items" }), "{count} items");
});

test("pluralize: falls back to 'other' when 'one' form is absent even for count === 1", () => {
  assert.equal(pluralize(1, { other: "{count} items" }), "{count} items");
});

test("pluralize: returns empty string when neither form is present (never throws)", () => {
  assert.equal(pluralize(1, {}), "");
});

// ---- t() / tPlural() against the real embedded catalog (no DOM/fetch needed) --

test("t(): resolves a real key from the embedded default catalog with zero setup", () => {
  assert.equal(i18n.t("nav.overview"), "Dashboard");
});

test("t(): falls back to the key itself for an unknown key", () => {
  assert.equal(i18n.t("nav.does_not_exist"), "nav.does_not_exist");
});

test("tPlural(): resolves the correct plural form via the real catalog", () => {
  assert.equal(i18n.tPlural("toast.results_count", 1), "1 result");
  assert.equal(i18n.tPlural("toast.results_count", 5), "5 results");
});

test("getLocale(): defaults to 'en' before any setLocale/init call", () => {
  assert.equal(i18n.getLocale(), i18n.DEFAULT_LOCALE);
});

// ---- Catalog integrity: no silent drift between files --------------------

const LOCALES_DIR = path.join(__dirname, "..", "..", "src", "responsibleai", "dashboard", "static", "locales");

test("EMBEDDED_DEFAULT_CATALOG matches static/locales/en.json exactly", () => {
  const fileCatalog = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "en.json"), "utf-8"));
  assert.deepEqual(
    i18n.EMBEDDED_DEFAULT_CATALOG,
    fileCatalog,
    "i18n.js's embedded default catalog has drifted from static/locales/en.json -- " +
      "update both together (see the comment above EMBEDDED_DEFAULT_CATALOG in i18n.js).",
  );
});

test("es.json has no missing keys relative to en.json (translation completeness)", () => {
  const en = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "en.json"), "utf-8"));
  const es = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "es.json"), "utf-8"));
  const missing = Object.keys(en).filter((key) => !Object.prototype.hasOwnProperty.call(es, key));
  assert.deepEqual(missing, [], "static/locales/es.json is missing translations for: " + missing.join(", "));
});

test("es.json has no stale keys that no longer exist in en.json", () => {
  const en = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "en.json"), "utf-8"));
  const es = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "es.json"), "utf-8"));
  const stale = Object.keys(es).filter((key) => !Object.prototype.hasOwnProperty.call(en, key));
  assert.deepEqual(stale, [], "static/locales/es.json has keys no longer present in en.json: " + stale.join(", "));
});

test("every pluralized key (object value) has both 'one' and 'other' forms in every locale", () => {
  const en = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "en.json"), "utf-8"));
  const es = JSON.parse(fs.readFileSync(path.join(LOCALES_DIR, "es.json"), "utf-8"));
  for (const [locale, catalog] of [["en", en], ["es", es]]) {
    for (const [key, value] of Object.entries(catalog)) {
      if (value && typeof value === "object") {
        assert.ok("one" in value, `${locale}.json's "${key}" is missing the "one" plural form`);
        assert.ok("other" in value, `${locale}.json's "${key}" is missing the "other" plural form`);
      }
    }
  }
});
