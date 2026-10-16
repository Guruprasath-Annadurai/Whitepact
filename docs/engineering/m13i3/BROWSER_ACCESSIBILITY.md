# Browser accessibility and uncertainty

Recorded metadata uses semantic labeled regions, headings, definition lists, bounded lists, polite status/alert messages, native buttons and wrapping for long values.401 offers sign-in;403 remains an access refusal; unavailable/invalid data does not become empty or valid consent. Refresh removes stale metadata. Tenant changes abort reads and suppress late results.

Fresh301frontendtests/32files passed; new12 tests cover opt-in keyboard GET, bounded literal scope, absent records, HTTP failures, manual retry, refresh loss, tenant cancellation and malformed metadata. Lint/type/build passed; static assets retained.

`tests/js/m13i3-records.e2e.mjs` adds12 browser UI fixture checks at375/768/1280 widths: long records/scope, lost refresh, foreign tenant and expired session. It enforces zero mutations, zero viewport overflow and zero axe violations. These explicit UI fixtures are separate from the real unmocked CDP customer harness. Runtime results are appended only after execution; existing public/P4/I2 browser assertions remain intact.

Fresh parent runtime: the new12-check records wrapper plus unchanged30-check I2 wrapper **2passed**,2existing deprecation warnings,102.80s. Both enforce their zero-violation/overflow/mutation assertions against real compiled app/static and migrated PostgreSQL, with authenticated UI data explicitly fixture-based.

Automated semantics/keyboard/axe checks are not WCAG certification or a real screen-reader/hardware authenticator test. No such certification is claimed.
