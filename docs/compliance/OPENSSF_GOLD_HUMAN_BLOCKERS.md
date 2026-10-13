# OpenSSF Best Practices Gold — Human Governance Blockers

**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Target:** OpenSSF Best Practices Badge — Gold Level  
**Date:** 2026-09-28  
**Scope:** Inviolable Human & Community Governance Boundaries  

---

## 1. Principle of Governance Integrity

The OpenSSF Best Practices Badge Program is an international trust standard administered by the Linux Foundation. Achieving the Gold badge signifies not merely that software code is well-tested and secure, but that the project has achieved **organizational sustainability, decentralized governance, and resilient multi-party stewardship**.

WhitePact is committed to absolute truth in public security claims. Under no circumstances will WhitePact:
- Fabricate secondary maintainer identities or sock-puppet GitHub accounts.
- Generate synthetic PR approvals using automated bots or AI personas.
- Formally associate fictitious organizations to claim contributor diversity.

This document details the three insurmountable human governance criteria that currently block the OpenSSF Gold badge, the exact rationale for why they remain unsatisfied, and the legitimate roadmap for community resolution.

---

## 2. Exhaustive Analysis of Human Blockers

### 2.1 Blocker 1: `bus_factor`
- **OpenSSF Requirement:** The project MUST have a "bus factor" (also called "truck factor") of at least two (2). That is, there must be at least two people who have full administrative and technical capability to maintain the project, review security reports, manage releases, and continue development if one maintainer becomes unavailable.
- **Current Project Status:** `UNSATISFIED (HUMAN_BLOCKED)`
- **Repository Reality:**
  - WhitePact was conceived, architected, and driven by a single founder-maintainer (`Guruprasath-Annadurai`).
  - While comprehensive documentation, automated CI/CD pipelines, reproducible builds, and disaster continuity plans exist (`compliance/PROJECT_CONTINUITY_PLAN.md`), documentation alone does not equal a human being with operational familiarity, cryptographic signing keys, and repository ownership.
- **Why Automation Cannot Resolve This:** A second human maintainer must possess independent legal and operational agency. Automation cannot create a biological human peer.
- **Resolution Criteria:**
  - Onboard a qualified second core maintainer.
  - Grant appropriate administrative permissions on GitHub, PyPI, and security disclosure channels.
  - Demonstrate active, multi-month co-maintenance history in public commit logs and issue triage.

---

### 2.2 Blocker 2: `contributors_unassociated`
- **OpenSSF Requirement:** The project MUST have at least two (2) unassociated significant contributors. Contributors are considered "unassociated" if they are not employed by the same organization, are not related, and work independently. A "significant" contributor is defined by sustained, meaningful contributions (code, architecture, test suites, or documentation) over an extended timeframe.
- **Current Project Status:** `UNSATISFIED (HUMAN_BLOCKED)`
- **Repository Reality:**
  - Virtually all substantive commits, architectural designs, and feature implementations to date originate from the primary maintainer.
  - Outside pull requests have been sporadic, minor, or limited in functional scope.
- **Why Automation Cannot Resolve This:** Claiming bot accounts or one-off typo corrections as "significant unassociated contributors" violates OpenSSF rules.
- **Resolution Criteria:**
  - Attract independent external engineers, researchers, or organizations utilizing WhitePact.
  - Foster substantive external pull requests that land in production releases.
  - Maintain a documented contributor register evidencing independent organizational affiliation.

---

### 2.3 Blocker 3: `two_person_review`
- **OpenSSF Requirement:** At least 50% of all proposed modifications (pull requests / changesets) during the preceding six (6) months MUST be reviewed and approved by at least one person other than the author before being merged into the default branch.
- **Current Project Status:** `UNSATISFIED (HUMAN_BLOCKED)`
- **Repository Reality:**
  - As a solo-maintainer repository, changesets have been authored and merged by `Guruprasath-Annadurai`.
  - Even when working with advanced AI pair-programming systems (Antigravity, Cursor, ChatGPT), AI systems do not count as human reviewers under the OpenSSF standard.
- **Why Automation Cannot Resolve This:** Pull request self-approval or automated bot LGTM approvals are explicitly prohibited by OpenSSF criteria.
- **Resolution Criteria:**
  - Institute a branch protection rule requiring $\ge 1$ mandatory pull request approval from an independent human peer.
  - Accumulate a 6-month verifiable track record where $>50\%$ of merged PRs carry signed approvals from independent humans.

---

## 3. Human Blocker Summary Table

| Criterion | Requirement Description | Technical Fix Possible? | Current Maintainer Count | Required State | Status |
|---|---|---|---:|---|---|
| `bus_factor` | $\ge 2$ knowledgeable maintainers capable of project survival | **NO** | 1 | $\ge 2$ | `HUMAN_BLOCKED` |
| `contributors_unassociated` | $\ge 2$ significant contributors from independent entities | **NO** | 0 | $\ge 2$ | `HUMAN_BLOCKED` |
| `two_person_review` | $\ge 50\%$ changes reviewed by non-author before merge | **NO** | 0% | $\ge 50\%$ | `HUMAN_BLOCKED` |

---

## 4. Legitimate Action Plan for Future Resolution

1. **Enterprise & Academic Outreach:** Engage open-source AI safety working groups and enterprise early-adopters to invite co-maintainers.
2. **Community Governance Charter:** Enact formal Open Governance (`docs/GOVERNANCE.md`) establishing clear merit-based pathways to maintainership.
3. **Strict Policy Preservation:** Preserve verified controls and close the remaining owner/account criteria so that Gold can be pursued honestly after the human criteria are met.
