# OpenSSF gap analysis

Data read 2026-10-11 from the public sources named in each section. Scorecard and Best Practices results are
about the default branch (`main`, `38f92722`), **not** this candidate branch; items fixed here count only after
they reach `main`. A badge or score is not a penetration test or an audit.

## 1. Scorecard 7.4 (2026-10-06)

| Check | Score | Reason (Scorecard's words, shortened) | What changes it | Owner / blocker |
| --- | --- | --- | --- | --- |
| Code-Review | 10 | all changesets reviewed | n/a | see §3: a solo maintainer's "review" is a platform setting, not independent review |
| Security-Policy, License, Binary-Artifacts, Dangerous-Workflow, Token-Permissions, Dependency-Update-Tool, Maintained, SAST, Packaging, CI-Tests | 10 | pass | keep | |
| CII-Best-Practices | 7 | badge detected: Silver | answer the 31 open criteria (§2) | maintainer web form |
| Pinned-Dependencies | 5 | dependency not pinned by hash | hash-pin every `pip install` in workflows and scripts (`--require-hashes` lock files) and every container base | engineering; CI image digests pinned this pass (3) |
| **Signed-Releases** | **0** | no signed or provenance assets | Scorecard looks for `.sig/.asc/.intoto.jsonl` release assets. WhitePact signs differently (GitHub attestations, SLSA v1 provenance, attested CycloneDX SBOM, signed tag) and those verify (`WHITEPACT_SUPPLY_CHAIN_SECURITY_EVIDENCE.md`). Publishing an `.intoto.jsonl` bundle next to each release would score it. **This is a measurement mismatch, not a missing control; do not describe the score as "signing is absent" or as "signing is proven by Scorecard".** | release workflow change; needs a release to take effect |
| Fuzzing | 0 | not fuzzed | add a property/fuzz harness (e.g. Hypothesis or Atheris) for parsers: policy rules, argument validation, MCP body validator, evidence canonicalization | engineering, not done |
| **Vulnerabilities** | **0** | 21 existing | OSV on `uv.lock`: `main` has 4 packages / 31 advisories (PyJWT 2.13.0 ×28, mako, multidict, nltk); **this branch has 1 (nltk, no patched release)** after PyJWT 2.15.0 (#182 content) and mako 1.4.3 / multidict 6.9.1 (this pass). Reaches `main` only when the branch is merged (not authorized) | merge decision |
| Contributors | 0 | 0 contributing organizations | needs real external contributors; cannot be engineered | organizational |
| Branch-Protection | -1 | scorecard token cannot read the setting | give Scorecard a read-capable token or check settings manually | maintainer |

## 2. Best Practices badge (project 14112, silver, self-attested 2026-08-29): 31 criteria not Met

Gold-tier items that depend on facts about the project, not on code:

| Criterion | Assessment | Honest answer today |
| --- | --- | --- |
| `bus_factor`, `contributors_unassociated`, `two_person_review` | one maintainer | **Unmet**, and must stay unmet until a second trusted person exists. Do not mark Met |
| `copyright_per_file`, `license_per_file` | SPDX header manager and CI check exist (`scripts/manage_license_headers.py`) | verify with `--check` then answer Met |
| `build_reproducible` | CI job "Rebuild artifacts identically" passes | likely Met; cite the job |
| `test_statement_coverage90` | coverage threshold in config; ≥ 90 % statement coverage not verified here | NOT VERIFIED |
| `homepage_url`, `report_url` | homepage is whitepact.com (stale content, §distribution report) | re-check after the site is redeployed |

OSPS Baseline (Level 3) controls reported unmet (text from `ossf/security-baseline`, read 2026-10-11), with the plan:

| Control | Requirement (short) | Plan |
| --- | --- | --- |
| OSPS-AC-04.01 / .02 | CI default and per-job permissions are minimal | workflows declare `permissions:`; audit each job once more (Token-Permissions already 10) |
| OSPS-BR-01.04 | pipelines sanitize collaborator input | workflows pass event data through `env:` not inline expressions (checked); document |
| OSPS-BR-02.02 | release assets tied to the release identifier | wheel/sdist/SBOM names carry the version; document |
| OSPS-BR-07.02 | policy for secrets and credentials | **DRAFT written**: `SECRETS_AND_CREDENTIALS_POLICY.md` |
| OSPS-DO-03.01 / .02 | docs explain how to verify integrity, authenticity and the builder identity | `docs/VERIFY_RELEASE.md` exists and was run; link it from README/SECURITY |
| OSPS-DO-04.01 / DO-05.01 | statement of support scope/duration and when releases stop receiving security fixes | **DRAFT written**: `SUPPORT_AND_END_OF_LIFE_POLICY.md` |
| OSPS-GV-04.01 | policy that collaborators are vetted before elevated permissions | **DRAFT written**: `ACCESS_AND_REVIEW_POLICY.md` |
| OSPS-QA-02.02 | SBOM with each compiled release asset | CycloneDX SBOM attested on v1.2.6 (verified): likely Met; the wheel is pure Python |
| OSPS-QA-04.02 | multi-repo releases | N/A: one repository (SDKs are in-tree) |
| OSPS-QA-06.02 / .03 | documented test environments; policy that major changes add tests | add to `CONTRIBUTING.md` after adoption |
| **OSPS-QA-07.01** | at least one **non-author human approval** before merge to the primary branch | **cannot be met by a sole maintainer.** Do not fake it; see §3 |
| OSPS-SA-03.02 | threat model and attack-surface analysis for releases | `docs/launch/AGENTIC_THREAT_REGISTER.md`, `ENFORCEMENT_PATH_MATRIX.md`; needs a consolidated, versioned threat model |
| OSPS-VM-04.02 | VEX for non-exploitable vulnerable components | **DRAFT written**: `WHITEPACT_VEX.openvex.json` (NLTK) |
| OSPS-VM-05.02 / 05.03 / 06.01 / 06.02 | remediation thresholds for SCA and SAST findings, enforced automatically | **DRAFT written**: `VULNERABILITY_REMEDIATION_POLICY.md`; enforcement exists (dependency-review, pip-audit, Bandit, CodeQL); required-check configuration is a repository setting |

## 3. The governance gap that engineering cannot close

Branch protection that "requires a review" is satisfiable by a repository admin approving their own pull request.
That is not independent review and is not what OSPS-QA-07.01, `two_person_review` or `bus_factor` ask for. Legitimate
options: add a second trusted maintainer (even part-time) with write access and a standing review obligation;
or leave these criteria unmet and say so. **No document in this repository may claim two-person review while there is
one maintainer.**

## 4. Not done in this pass

Maintainer MFA verification (account setting), branch-protection/ruleset export, fuzzing harness, hash-pinning of
the remaining installs, publishing signed-release assets in the Scorecard-recognised form, answering the Best
Practices form (requires the maintainer's login).
