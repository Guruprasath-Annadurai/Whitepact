# Heart Signing Decision (Phase H1)

## Question

Should `AuthorityConstitutionVersion.canonical_digest` — or any other
Heart artifact — be cryptographically signed (HMAC or asymmetric),
rather than a plain SHA-256 digest?

## Answer for Phase H1: no, not yet, for the same reason `execution.py`
and `authority_passport.py` already give

This codebase has two existing, real precedents for declining to sign
an object, both quoted in full in `docs/heart/HEART_CURRENT_STATE.md`
§5:

- `governance/execution.py`'s `ExecutionAuthorization`: not signed
  because it "never crosses a trust boundary — the gateway constructs
  it and `InternalToolExecutor.execute()` consumes it within the same
  async call stack, in the same process." Signing protects against an
  attacker who can intercept or forge the object in transit or storage
  outside the process that created it; an attacker with arbitrary code
  execution *inside* that same process can forge a Python object
  regardless of any in-process signature.
- `governance/authority_passport.py`'s `AuthorityPassport`: not signed
  for the same reason, generalized — "a forged passport would need the
  same DB write access that could also rewrite its own source
  ceiling/delegation row."

**The constitution is even further from needing a signature than
either of those**, for a stronger reason specific to it: `CONSTITUTION_V1`
is not a database row at all — it is a Python module-level constant,
defined in source code, deployed as part of the application artifact
itself. An attacker who can mutate `CONSTITUTION_V1`'s definition
already has write access to the deployed source, at which point they
could equally remove any signature-verification check that would have
caught the tampering. A signature over a constant baked into the code
that would verify it doesn't protect against the one realistic threat
(a compromised deployment), and does protect against a threat that
doesn't exist today (a constitution served over a network from a
separate, less-trusted service).

## When this decision should be revisited

Per `execution.py`'s own stated condition, generalized: **the moment
any Heart artifact crosses a process or trust boundary** — for
example, if a future architecture serves the constitution (or a
`LegitimacyEnvelope`) from a dedicated Heart service that a separate
Brain process calls over the network, rather than importing it as a
Python module in the same process — signing becomes load-bearing, and
this decision should be revisited with equal rigor, not silently
carried forward past the point where it stopped being true.

## What the digest *does* provide today

Not signing does not mean "no integrity guarantee." `canonical_digest`
still provides:

1. **Change detection** — any test or CI check can assert
   `CONSTITUTION_V1.canonical_digest == "<expected value>"` and fail
   loudly if the constitution's laws, description, or ratification
   date are edited, intentionally or not.
2. **A stable reference for evidence** — a future `LegitimacyEnvelope`
   (Phase H12) stamped with `constitution_version=1` can also record
   `constitution_digest=<CONSTITUTION_V1.canonical_digest>`, so a
   historical decision remains checkable against the *exact* law text
   that was active, not just a version number that could in principle
   (though never should, per `_CONSTITUTION_HISTORY`'s immutability)
   have been silently altered.
3. **Reviewability** — anyone can independently recompute
   `compute_constitution_digest()` from the published law text and
   confirm it matches, without needing any key material at all — a
   real, if weaker, form of independent verifiability that a signature
   would not add much to for source-code-embedded, non-networked data.

## Verdict

**Not cryptographically signed in Phase H1.** Documented explicitly,
not left implicit — the same discipline `execution.py` and
`authority_passport.py` already established for this codebase.
