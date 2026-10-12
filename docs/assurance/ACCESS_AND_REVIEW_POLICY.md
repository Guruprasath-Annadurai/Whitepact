# Access and review policy (DRAFT for founder adoption)

Status: **draft**. States the rules the project intends to follow and the limit it cannot yet meet.

* **Granting elevated permissions:** write, admin, release or secret access is granted only after the person has a
  history of reviewed contributions, a verified identity and MFA, and the maintainer records the decision in
  `MAINTAINERS.md`. Access is removed when no longer needed.
* **Changes to the primary branch:** every change arrives through a pull request (administrators are bound by the rule). The checks
  that are **required to merge today** are: lint/type-check/test on Python 3.11 and 3.12, build, Helm lint, DCO,
  gitleaks, accessibility and i18n. CodeQL, dependency review and the reproducible-build check run on pull requests
  but are **not yet required status checks**; making them required is a founder action on branch protection.
  Required approving reviews are currently **0** and signed commits are not required.
* **Independent review:** the intended rule is at least one approval from a human other than the author.
  **Today the project has one maintainer, so this rule cannot be met and must not be claimed as met.** Until a second
  trusted reviewer exists, security-sensitive changes are additionally reviewed by an independent auditor
  (currently the Antigravity agent, an AI system, which is not a substitute for a human reviewer under OSPS-QA-07.01).
* **Releases:** created only from a signed tag by the trusted builder workflow; provenance and SBOM are attested.
