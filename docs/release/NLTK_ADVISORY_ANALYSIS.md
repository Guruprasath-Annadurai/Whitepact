# NLTK advisory analysis (Lane D preparation)

## Installed / constrained version

- Extra: `[sentiment]` → `nltk>=3.10.0` (`pyproject.toml`)
- Default install: **no nltk**

## Advisories (authoritative project triage)

- **PYSEC-2026-3740** / CVE-2026-81726 — model-artifact import/export path traversal
- **PYSEC-2026-597** / CVE-2026-12243 — `nltk.data.load` / `find` traversal

CI documents both as open upstream with pip-audit ignores when `[sentiment]` is installed.

## Reachability

**Classification: LIMITED_LEGACY_REACHABILITY**

- Only call site: `src/biasbuster/core/scoring.py` → `nltk.download("vader_lexicon", quiet=True)` hardcoded literal
- Does not call affected `data.load` / model import-export APIs

## Remediation options (investigated)

1. **Safe upgrade** — floor already `>=3.10.0`; no upstream fix for 3740/597 at analysis time
2. **Constraint change** — no safer pin available
3. **Replace usage** — possible future work; not silently removed in prep
4. **Isolate** — already opt-in extra
5. **Documented exception** — CI + `requirements-security.lock` triage

## Lane D implementation

No version bump on prep branch (no new upstream fix). Documentation + OpenVEX template require evidence at final SHA.
