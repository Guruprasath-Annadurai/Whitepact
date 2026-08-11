# Deterministic vs. Probabilistic Controls

Last reviewed: 2026-08-11 · Platform version: 1.2.0

This document expands `SPEC.md` Section 6's principle into a standalone
reference. It exists because the distinction between a deterministic check
and a probabilistic (model- or heuristic-driven) judgment is the single
most important property of any control WhitePact ships — a governance
platform that can't tell you which of its own checks are guaranteed-correct
and which are best-effort has no business making that claim about anything
else.

## The rule

**Deterministic**: same input → same output, every time, with no model call
in the decision path. A deterministic check can be unit-tested exhaustively
— every input class has a known, provable output.

**Probabilistic**: a model, statistical heuristic, or scoring function
produces a confidence-scored judgment that can be wrong, drift over time, or
depend on external factors (model version, prompt template, provider
behavior) outside this codebase's control.

**WhitePact must never present a probabilistic evaluation's output as a
guarantee.** Every probabilistic result surfaced through `EvidenceRecord`
carries a confidence or limitation annotation. The fast, low-risk decision
path (`RiskTier.LOW` — see `SPEC.md` Section 9) must be satisfiable using
*deterministic* checks alone: an agent should never be forced through an LLM
call just to get a routine, low-risk action approved. This is also why
`WhitePactRuntimeGateway.evaluate()` itself makes no LLM call — the
governance decision (ALLOW / ALLOW_WITH_REDACTION / REQUIRE_APPROVAL / DENY
/ QUARANTINE) is always computed deterministically from risk tier + policy
+ (optionally) a probabilistic module's *output*, never by asking a model to
decide the outcome directly.

## Why this matters more here than in most systems

A governance layer that itself relies on an LLM to decide ALLOW vs. DENY has
three failure modes ordinary application code doesn't:

1. **Non-reproducibility** — the same action could be approved on one call
   and denied on the next, with no code change, because model sampling or a
   provider-side update changed the answer. That's unauditable.
2. **Prompt injection surface** — if the decision itself runs through a
   model, an adversarial input crafted to manipulate that model's judgment
   becomes a governance bypass, not just a content-quality problem.
3. **False assurance** — a governance decision framed as authoritative
   ("DENY") that actually came from a probabilistic judgment misrepresents
   its own reliability to whoever relies on it.

Keeping the decision engine deterministic and treating every probabilistic
signal as an *input* to that engine, never the engine itself, is how this
platform avoids all three.

## Current inventory

### Deterministic (no model call, provably correct for a given input)

| Component | What it does |
|---|---|
| `governance/risk.py` — `classify_action_risk()` | Hardcoded, drift-tested table mapping each MCP tool to a risk tier |
| `governance/policy.py` — `Policy.evaluate()` | First-match-wins rule matching (`ALLOW`/`DENY`/`REQUIRE_APPROVAL`) |
| `governance/evidence.py` — hash chain | `entry_hash = sha256(prev_hash + fields)`; `verify_chain()` |
| `governance/approval.py` — resolution | SQL-guarded `PENDING → APPROVED/DENIED` state transition |
| `auth`/`rbac` — role checks | `require_role(...)` — a fixed hierarchy comparison, no inference |
| Per-org rate limiting | Token-bucket arithmetic against a fixed limit |
| `guardrails/engine.py`'s PII detection | Regex/pattern-based (SSN, email, phone, credit card, etc.) — not a model classifier |
| `supplychain/scanner.py`'s typosquat check | Bounded Cyrillic/Greek confusable-character lookup table |
| `supplychain/scanner.py`'s known-incident cross-reference | Exact/fuzzy match against `PublicIncidentRepository` records |
| `trust/passport.py`'s hash generation | SHA-256 over passport fields |
| `cost/tracker.py`, `cost/router.py` | Arithmetic over a fixed pricing table, not a learned model |

### Probabilistic (a model or statistical heuristic; confidence-scored, not guaranteed)

| Component | What it does | How its uncertainty is surfaced |
|---|---|---|
| `hallucination/detector.py` — `HallucinationDetector` | Risk score from hedging language, response consistency across candidates, unsupported-claim detection | Returns a `hallucination_risk` float + `risk_level`, never a binary true/false claim of fact |
| `biasbuster` probes | TF-IDF cosine divergence + VADER sentiment divergence across demographic variants | 95% bootstrap confidence intervals reported alongside every score — the CI width is the uncertainty signal |
| `trust/score.py` — `TrustScoreEngine` | Weighted composite of 6 caller-supplied dimension scores | The inputs themselves are often human- or model-judged upstream; the composite is deterministic arithmetic *over* probabilistic inputs — flagged here because the inputs, not the composite formula, carry the uncertainty |
| `redteam/simulator.py` when scoring model *responses* to attack payloads (not the payload library itself, which is static) | Heuristic safe-refusal classification | Reported as a rate (`safe_refusal_rate`), not a pass/fail guarantee |
| `guardrails/engine.py`'s toxicity scanning (as distinct from its regex-based PII detection) | Heuristic/lexicon-based scoring | Threshold-based, tunable — a false negative is possible and not claimed otherwise |
| `supplychain/scanner.py`'s tool-description content scan | Reuses `GuardrailsEngine`'s heuristic scanning against tool descriptions | Returns `INFERRED_SIGNAL`, deliberately never `VERIFIED_FACT`, for anything that came from this path |

### The three-verdict pattern (why the supply-chain scanner never returns a single score)

`SupplyChainScanner` is the clearest example of this principle in the
codebase: instead of collapsing typosquat detection (deterministic),
description scanning (probabilistic), and incident cross-reference
(deterministic, but dependent on an external, possibly incomplete registry)
into one opaque "trust score," it returns one of three explicit verdicts per
check — `VERIFIED_FACT`, `INFERRED_SIGNAL`, or `UNKNOWN` — so a caller can
tell which parts of the assessment are provable and which are a judgment
call. This pattern (explicit verdict provenance rather than a single number)
is the template for any future check that mixes deterministic and
probabilistic signals.

## What this means for contributors

If you're adding a new governance-relevant check:

1. **Default to deterministic.** If the check can be expressed as a rule,
   pattern match, or lookup table, do that instead of calling a model —
   see `CONTRIBUTING.md`'s engineering principles.
2. **If it must be probabilistic**, the output must carry a confidence
   signal (a score, a confidence interval, or an explicit `INFERRED_SIGNAL`
   /`UNKNOWN` verdict) — never a bare boolean presented as fact.
3. **Never let a probabilistic result alone produce a DENY/QUARANTINE
   decision without it flowing through the deterministic policy engine
   first.** The probabilistic signal is an input to `governance/policy.py`,
   not a decision-maker itself.
4. **Document which category your check falls into** in its docstring or
   the relevant `SPEC.md` section, so this inventory doesn't silently go
   stale — the same discipline `GOVERNANCE.md` asks of every other document
   in this repo.
