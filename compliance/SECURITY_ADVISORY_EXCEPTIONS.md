# WhitePact Security Advisory Exception Register

**Status:** Active first-party vulnerability-risk register  
**Owner:** WhitePact maintainer / service owner  
**Review date:** 2026-09-13

> An exception in this file is not a statement that an upstream vulnerability is harmless. It documents a narrowly scoped, time-bounded decision where the affected package has no patched release and WhitePact's actual reachable API surface does not meet the advisory's exploitation preconditions. A patched upstream release, changed call site, new exploit evidence, or expanded product use triggers immediate re-review.

## Exception process

Every exception must record:

- advisory/CVE identifiers;
- package and installed/allowed versions;
- severity;
- affected upstream API/behavior;
- WhitePact's actual usage;
- exploitability determination and evidence;
- compensating controls;
- CI handling;
- review/expiry trigger;
- owner and decision date.

CI may ignore an advisory only while the corresponding exception is documented and the code boundary supporting the exception is regression-tested where practical.

## EX-2026-001 — NLTK path-security advisories

**Package:** `nltk` (optional `[sentiment]` extra only)  
**Current resolved version in CI:** 3.10.3 as of 2026-09-13  
**Default package dependency:** No  
**Decision:** Temporary accepted exception for the reviewed VADER-only call surface; continue to fail CI on all other known vulnerabilities.

### Advisory A — PYSEC-2026-597 / CVE-2026-12243

The existing WhitePact CI exception covers an NLTK path-traversal issue in data-resource loading/path handling. No patched release is available in the currently supported upstream line as recorded by the existing project triage.

**WhitePact reachability:** WhitePact does not pass attacker-controlled resource paths. The only generic `nltk` call in production source is a hard-coded `nltk.download("vader_lexicon", quiet=True)` fallback used by optional VADER sentiment scoring.

### Advisory B — PYSEC-2026-3740 / CVE-2026-81726 / GHSA-8mgp-746c-j5xp

**Severity:** High (upstream advisory)  
**Affected upstream behavior:** model-artifact APIs can bypass NLTK `pathsec` protections and read/write outside allowed roots when a caller can control model paths. The published advisory names APIs including `TransitionParser.train`, `TransitionParser.parse`, `AveragedPerceptron.save/load`, `PerceptronTagger.save_to_json`, and `save_maxent_params`. As of 2026-09-13, the GitHub advisory lists NLTK `<=3.10.3` as affected and lists no patched version.

Official advisory: https://github.com/nltk/nltk/security/advisories/GHSA-8mgp-746c-j5xp

**WhitePact reachability determination:** The reviewed production call site is `src/biasbuster/core/scoring.py`. It imports `SentimentIntensityAnalyzer` from `nltk.sentiment.vader`; if the VADER lexicon is missing, it imports the top-level `nltk` module and calls only `nltk.download("vader_lexicon", quiet=True)` with a literal resource name. WhitePact does not import or call the model persistence/loading APIs named in this advisory and does not expose an attacker-controlled NLTK model path through this feature.

### Compensating controls

1. NLTK remains opt-in under the `[sentiment]` extra rather than a default dependency.
2. `tests/test_nltk_security_boundary.py` enforces that production source does not expand NLTK usage beyond the reviewed VADER import plus the literal VADER lexicon download without a test/security review change.
3. Main CI still installs the sentiment extra so the optional path is exercised rather than becoming untested.
4. `pip-audit` continues to fail on every other discovered vulnerability; only the explicitly listed advisory IDs are ignored.
5. The exception must be removed when a patched NLTK release becomes available and passes WhitePact tests, or earlier if WhitePact starts using an affected API, an exploit path is demonstrated against the VADER-only usage, or upstream advisory scope changes materially.

### Review cadence and expiry trigger

- Re-check upstream on every dependency-update cycle and at least monthly while the exception remains active.
- Mandatory next manual review no later than **2026-10-13** if no automated dependency update has already triggered review.
- Remove the exception immediately after a suitable patched release is available and validated.

### Claim boundary

This is **risk acceptance for a narrowly reviewed, currently unreachable upstream API path**, not a declaration that NLTK 3.10.3 is vulnerability-free. Enterprise/security materials must continue to disclose that internally accepted dependency exceptions may exist and are tracked to upstream remediation.
