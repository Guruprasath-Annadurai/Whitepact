# WhitePact 95+ — Integration Strategy

**Analysis only. No integration performed.** This document compares
options and recommends one; it does not execute anything.

## The situation, in evidence

- `main` (`8f8ef53f`) and PR #55 (`22b2c775`, which fully contains PR
  #54's branch tip) share merge-base `9dcdc1be`.
- Since that merge-base: `main` has 12 real commits (462 files touched,
  +4487/-2207 lines); PR #55 has 40+ commits beyond PR #54's tip alone
  (279 files touched relative to the merge-base, cumulative).
- **77 files were touched by both sides independently.** This sounds
  alarming; the actual risk is concentrated in far fewer files than
  that number suggests — see below.
- **A real merge dry-run confirms it, not just inference.**
  `git merge-tree --write-tree origin/main <PR55-head>` (git 2.50.1)
  was actually run — not simulated — and produces exactly **7 real
  textual conflicts**, all in tooling/ops files, **zero in any source
  file under `src/`**:
  `.github/workflows/ci.yml`, `.github/workflows/dependency-review.yml`,
  `.github/workflows/publish.yml`, `.github/workflows/scorecard.yml`,
  `Dockerfile`, `SUPPORT.md` (add/add — both sides independently
  created this file), `scripts/rotate_field_encryption_key.py`. Every
  one of the other ~70 overlapping files — including every core
  security file — auto-merges cleanly with git's own trivial merge
  strategy.
- **The core security files (`execution.py`, `mcp/server.py`,
  `mcp/tools.py`, `mcp/governance_integration.py`,
  `dashboard/app.py`) were touched by `main` only trivially** — a
  repo-wide SPDX copyright-header sweep (`+2` lines per file, confirmed
  by direct diff inspection, not assumed) — consistent with the
  merge-tree result above showing them as clean auto-merges. PR #55's
  changes to the same files are substantial and real (the actual
  Heart/governance work). **This means the 77-file overlap is almost
  entirely false-positive risk, now confirmed by an actual merge
  attempt rather than sampling.**
- **Migrations do not conflict.** `main` has made zero schema changes
  since the merge-base. PR #55's migrations 0001–0029 differ from
  `main`'s copies only in formatting (a `ruff format` pass reflowed
  column alignment — confirmed by direct diff, not assumed); PR #55
  adds 0030–0037 cleanly on top with no renumbering collision.
- **One genuine, unreconciled overlap exists**: `main`'s commit
  `a46980d` ("complete enterprise trust and assurance hardening")
  includes "fail closed on malformed evidence bundles" — evidence-
  handling logic that PR #55 also touches extensively (evidence hash-
  chain, fork-prevention). These two independent changes have never
  been diffed against each other. This is the one place a mechanical
  merge could silently drop or conflict with a real fix, and it is the
  single most important thing any integration attempt must check by
  hand, not by tooling alone.
- **`main` has real, valuable work PR #55 does not**: SLSA Build L3
  evidence, reproducible builds, signed release tags, OpenSSF Scorecard
  hardening, three real releases (v1.2.4–v1.2.6). None of this exists on
  PR #55 — it branched before this landed. Any integration strategy that
  discards or overwrites this is a real regression, not just an
  inconvenience.

## Options compared

**A. Controlled merge** (`git merge main` into the PR #55 stack, or vice
versa). *Pro*: preserves full commit history and DCO trail on both
sides; the actual `git merge-tree` dry-run above confirms only 7 files
need real, hand-resolved conflict resolution (all tooling/ops, not
source), with everything else — including every core security file —
auto-merging cleanly. *Con*: the evidence-bundle overlap (not one of
the 7 textual conflicts — it auto-merges without markers, which is the
more dangerous case) still needs deliberate, manual review precisely
because it *won't* surface as a conflict; a merge commit of this size is
hard for a human reviewer to re-review file-by-file even where
auto-merge succeeds cleanly, because "no conflict markers" isn't the
same as "no semantic interaction."

**B. Cumulative integration branch** (a fresh branch that pulls both
`main`'s and PR #55's changes in, reviewed as a unit before ever
touching `main`). *Pro*: gives the independent security reviewer (still
required — see 00_DEPENDENCY_GRAPH.md) one stable target to review that
already reflects both bodies of work, rather than reviewing PR #55 now
and re-reviewing after a later merge. *Con*: extra branch/PR overhead;
still has to solve the same evidence-bundle reconciliation problem
somewhere.

**C. Selective cherry-pick.** *Pro*: lets the evidence-bundle conflict be
handled commit-by-commit with full context. *Con*: PR #55 is 40+
commits deep with real interdependencies (e.g. the E0–E6 chokepoint
work depends on the earlier Gap A–D primitives) — cherry-picking risks
picking a commit whose prerequisite didn't come along, producing a
codebase that compiles and passes tests but is subtly incomplete. Given
this session's own experience finding wiring gaps exactly this way
(the Heart headline finding: a primitive existed but had zero live call
sites), this is a real, not theoretical, risk for this specific
codebase.

**D. Rebuild high-value changes cleanly on current `main`.** *Pro*:
guarantees the result actually reflects current `main` (including its
SLSA/Scorecard work) with no merge artifacts. *Con*: by far the most
expensive option — effectively redoing 40+ commits' worth of real,
already-tested engineering work from scratch, discarding the existing
DCO/commit trail and this session's entire freeze-and-review evidence
chain (which is itself tied to specific SHAs on the existing branch).
Given the review packet, attack map, and external review are all
SHA-anchored to the existing branch, rebuilding elsewhere would orphan
all of that evidence and require redoing the review-readiness work too.

## Recommendation

**Option B — a cumulative integration branch —** with the evidence-
bundle reconciliation (the one real conflict identified above) done by
hand, reviewed on its own before the branch is presented for
independent review.

Reasoning: Option A's git-mechanical merge is now confirmed (not
estimated) to succeed with only 7 textual conflicts, none in source
code — but "few conflicts" is not the same as "reviewable," and is
actively misleading for the one file that matters most:
`evidence_repository.py` auto-merges with zero conflict markers despite
both sides having independently changed evidence-handling logic. A
security reviewer should see one clean, intentional integration
commit's diff against `main`, not a merge commit whose provenance
requires reconstructing which side each hunk came from — least of all
for the one file where "no conflict" hides a real reconciliation
question rather than answering it. Option C's
interdependency risk is real and specific to this codebase's own history
of wiring gaps. Option D throws away real, tested work and orphans the
existing review evidence for no corresponding safety benefit — the
actual risk (the evidence-bundle overlap) is one file's worth of careful
work, not a reason to rebuild 40 commits.

**Sequencing**: build the integration branch only *after* the
independent human security review closes on the frozen candidate (per
`00_DEPENDENCY_GRAPH.md`) — reviewing, then integrating, then treating
the integration branch as needing its *own* fresh verification pass
(full suite, CI, migration round-trip) rather than assuming the
pre-integration evidence still applies untouched. This mirrors the
project's own established practice this session: never assume a prior
number is still true; reproduce it.

**Not decided by this document**: the exact mechanics of building the
integration branch, who resolves the evidence-bundle conflict, or a
timeline. Those are implementation decisions properly made after this
Phase 0 report is reviewed, not audit conclusions.
