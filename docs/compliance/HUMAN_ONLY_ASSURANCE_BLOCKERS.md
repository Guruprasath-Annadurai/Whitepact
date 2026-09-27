# Consolidated Register of Human & Governance Assurance Blockers

**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Scope:** Cross-Framework Governance & Human Participation Analysis  
**Date:** 2026-09-28  
**Governing Standard:** Absolute Truth in Public Security Claims  

---

## 1. Executive Summary

A core finding of this assurance qualification audit is that WhitePact has strong repository and release controls, while several technical and human requirements remain. Current Scorecard gaps include continuous fuzzing, incomplete dependency pinning, and vulnerability disposition; these are not human-only blockers.

The table below is intentionally limited to **human, community, and organizational governance requirements**. Technical gaps are tracked in the framework-specific evidence documents.

These blockers exist because WhitePact has been developed primarily by a dedicated solo founder (`Guruprasath-Annadurai`). Under the OpenSSF Code of Conduct, BadgeApp criteria, and industry security ethics, **it is strictly prohibited to fabricate human identities, create puppet GitHub accounts, or use automated AI systems to mimic human peer reviews**.

This document consolidates every human-only blocker across all target frameworks, establishes the immutable boundary between software and human agency, and defines the genuine community roadmap for resolution.

---

## 2. Consolidated Master Table of Human Blockers

| Target Framework | Control / Criterion | Exact Requirement | Current Repository Reality | Why Automation Cannot Resolve | Legitimate Community Resolution Path |
|---|---|---|---|---|---|
| **OpenSSF Best Practices (Gold)** | `bus_factor` | Project MUST have a bus factor of $\ge 2$ knowledgeable maintainers. | Sole primary maintainer (`Guruprasath-Annadurai`). | A human maintainer requires autonomous legal and technical judgment. | Formally onboard a qualified second core maintainer with commit rights. |
| **OpenSSF Best Practices (Gold)** | `contributors_unassociated` | Project MUST have $\ge 2$ unassociated significant contributors. | Commits historically authored by the primary maintainer. | Independent organizational affiliation cannot be simulated. | Attract external contributors from distinct organizations contributing significant PRs. |
| **OpenSSF Best Practices (Gold)** | `two_person_review` | $\ge 50\%$ of merged PRs over past 6 months must be reviewed by someone other than author. | Solo maintainer merges PRs without external human review. | Self-approval or bot approval is explicitly disqualified by OpenSSF. | Enforce mandatory branch protection requiring $\ge 1$ peer review once a co-maintainer joins. |
| **OpenSSF OSPS Baseline (Level 3)** | `OSPS-QA-07.01` | At least one non-author human approval prior to merge. | PRs authored and merged by single maintainer. | Review must be executed by a distinct human being. | Require non-author approval in GitHub branch protection rules with active team. |
| **OpenSSF Scorecard (v5.5.0)** | `Contributors` | Commit history represents contributors from more than one organization. | Current public result reports 0 contributing companies/organizations. | Open-source diversity requires genuine independent participation. | Broader adoption and external contributions. |

---

## 3. Detailed Failure Mode Analysis & Ethical Prohibitions

### 3.1 Prohibition on Artificial Co-Maintainers
Creating a secondary GitHub account under a pseudonym or registering an AI agent as a "reviewer" would deceive consumers, auditors, and enterprises. If a critical vulnerability is disclosed, an artificial persona cannot respond to an emergency or bear legal accountability. WhitePact will only claim a bus factor of 2 when a real, accountable engineer is onboarded.

### 3.2 Distinction Between AI Pair-Programming and Human Code Review
WhitePact utilizes state-of-the-art AI pair programming and independent adversarial verification agents (Antigravity, Cursor, ChatGPT). While these AI systems provide rigorous adversarial testing and formal reasoning, **standards bodies explicitly define "code review" as an independent human cognitive check**. Claiming AI review as "two-person review" violates OpenSSF standards.

### 3.3 The Single-Maintainer Paradox in Open Source
Modern open-source security frameworks (OpenSSF, SLSA, NIST) are increasingly structured around enterprise consortium models where multiple funded engineers collaborate. High-velocity open-source innovations often start with solo founders. WhitePact proudly demonstrates that a solo-maintainer project can achieve **enterprise-grade technical rigor** (SLSA Build L3, 90%+ test coverage, cryptographic attestations, zero CVEs) while remaining 100% honest about human governance limitations.

---

## 4. Operational Roadmap for Overcoming Governance Blockers

1. **Phase 1: Open Governance Charter (Immediate):**
   - Adopt formal governance guidelines (`docs/GOVERNANCE.md`) establishing transparent criteria for contributor promotion to committer and maintainer status.
2. **Phase 2: Working Group Collaboration (Q4 2026):**
   - Present WhitePact's autonomous AI runtime authority model at AI safety and OpenSSF working groups.
   - Invite security researchers and partner organizations to participate in formal triage and review.
3. **Phase 3: Branch Protection Escalation (Upon Onboarding):**
   - Once a second maintainer is onboarded, activate GitHub branch protection requiring `Require pull request reviews before merging` with `Required approving reviews: 1` and `Dismiss stale pull request approvals when new commits are pushed`.
4. **Phase 4: Formal Badge Elevation:**
   - After 6 months of documented multi-party review history, officially apply for OpenSSF Best Practices Gold and OSPS Baseline Level 3.
