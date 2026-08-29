# WhitePact is looking for a second maintainer

**Status: open, as of 2026-08-29.**

This is the single biggest gap standing between WhitePact and being
taken seriously by security-literate buyers and the OpenSSF Best
Practices program. It's named plainly, not softened: WhitePact has
exactly one maintainer today (`GOVERNANCE.md`), and that's a real
single point of failure — for the project's continuity, for its
security review process, and for its credibility with anyone
evaluating it for enterprise use.

## What this role actually is

Not a nominal co-maintainer added to satisfy a badge checklist. A real
second person with:
- Standing write access to the repository.
- Enough context to review pull requests independently — including,
  eventually, requiring a second approving review before merge to
  `main` (`compliance/OSPS_BASELINE_BRANCH_PROTECTION.md` explains why
  that's not turned on yet with only one maintainer).
- Enough operational knowledge to follow
  `compliance/PROJECT_CONTINUITY_PLAN.md`'s recovery checklist if the
  founder becomes unavailable.
- A real, ongoing stake in the project — not a one-time PR merged to
  tick a box.

## What it unblocks

- OpenSSF Best Practices **Gold** criteria: `bus_factor` (≥2),
  `contributors_unassociated`, and (once there's real review history)
  `two_person_review`.
- Enabling required PR review on the default branch — currently `0`
  required approvals, deliberately, because with one maintainer that
  setting would lock the founder out of merging their own work
  (`compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`).
- A real answer, instead of "no one but the founder," to the
  governance question every serious security review starts with
  (`GOVERNANCE.md` Section 2).

## What the project is

WhitePact (`responsibleai` on PyPI) is a runtime governance/policy
layer for AI agents and MCP tool calls — authority/delegation
checking, risk-tiered policy evaluation, hash-chained audit evidence,
and a growing "Heart" subsystem for cryptographically-grounded
authority provenance. Python, async-first, SQLAlchemy + Alembic,
FastAPI/Starlette dashboard, a real CI pipeline (ruff, mypy, pytest,
CodeQL, gitleaks, dependency review). See `README.md` and
`docs/heart-production/00_CURRENT_RUNTIME_MAP.md` for what's real
today versus scoped-but-not-built.

## What you'd be looking at day to day

- Reviewing PRs (including ones from the founder — that's the point).
- Weighing in on architecture decisions for the Heart/authority-layer
  work in `docs/heart-production/` and `docs/enterprise-neural/`.
- Being a second set of eyes on security-relevant changes before they
  ship — this project takes an unusually document-heavy, "state the
  gap honestly" approach to its own security posture
  (`compliance/`, `THREAT_MODEL.md`); fitting that culture matters
  more than any single technical skill.

## Who this is a good fit for

Comfortable with Python, async code, and reading dense security/authz
design docs. Interested in AI governance/safety tooling specifically —
this isn't a generic "add a feature" open-source project, it's a
security-and-trust-boundary-heavy one. Available for real, recurring
review time, not a single drive-by contribution.

## How to reach out

Two ways, whichever you prefer:

- **Email**: [hello@whitepact.com](mailto:hello@whitepact.com)
- **GitHub Discussions**: open a thread in this repo's
  [Discussions](https://github.com/Guruprasath-Annadurai/Whitepact/discussions)
  tab — good if you'd rather show your work in the open (a linked PR,
  a public back-and-forth on scope) than send a private note.

---

*This document exists because compliance/PROJECT_CONTINUITY_PLAN.md,
GOVERNANCE.md, and compliance/openssf/OPENSSF_HUMAN_REQUIREMENTS.md
all independently name the same gap. Recruiting the actual person is
founder-only work no engineering pass can substitute for — this is
the tool for doing it, not a claim that the gap is already closed.*
