# Argon independent security retest

Fetched exact PR #212 HEAD `e6af2f86931e5f527768b9c22bf1f0795eb80923`. Its changes after `d0041e4f...` are docs and removal of one unused test import; backend enforcement is unchanged. It descends from I1. Existing PRs and Argon's active branch/directory are untouched.

Preserved original production-origin counterexamples from signed `d1fe6964...` are unchanged on isolated review child `ce41f20487a5e4c4ac6d6932bb665ac1b2c9b667`, tree `33a40b1c35b69f3a744716613284f58028f2e975`. Fresh rerun:1passed/2failed2.83s. Production `_svc` still accepts explicit HTTP and missing-origin fallback. These are constructor/configuration tests with a stub engine, not an authentication exploit or customer journey.

Actual fresh PostgreSQL/Chromium attempt additionally reaches genuine browser credential generation, then registration fails403 assurance. No seeded authority or forged authenticator response. Original+extended PostgreSQL regression execution is recorded as pending until its fresh measured result is appended; no owner result is copied.

Previously identified capability consent/policy/root-expiry, client validation and atomic application-disable/concurrent-registration guarantees remain unqualified because implementation has not changed. Existing3 application tests use SQLite/ASGI fixtures; that historical result is not a new PostgreSQL authority proof. No unqualified security implementation is integrated.

Corrections and exact commits must be independently reviewed before integration. New blocker handoff lives in PR #213/reports; PRs #206–#212 are not modified by I3.
