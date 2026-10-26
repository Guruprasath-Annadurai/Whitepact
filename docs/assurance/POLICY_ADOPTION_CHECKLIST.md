# Policy adoption checklist — for founder approval

Founder decision 4: the four drafted policies stay working documents until adopted. This checklist is
the verification the founder asked for: each claimed process was checked against the repository and the
GitHub configuration on 2026-10-11. Unsupported promises were **removed or rewritten in the drafts** in this
change. **No policy is adopted; OpenSSF Gold is not claimed.**

Verdicts: **V** verified in repo/config · **P** partly true, wording corrected · **U** not supported today (removed or
marked a founder commitment) · **F** founder/organizational, not verifiable from code.

## 1. Claim verification

| Policy | Claim | Evidence found | Verdict |
|---|---|---|---|
| Access | PRs required; administrators bound | Branch protection `enforce_admins: true` | V |
| Access | Required checks include CodeQL, dependency review, reproducible build | Required contexts are: lint/type/test (3.11, 3.12), build, Helm lint, DCO, gitleaks, a11y, i18n. CodeQL/dependency-review/reproducible-build are **not** required | **P** — rewritten to the true list |
| Access | Independent human approval | `required_approving_review_count: 0`; one maintainer | U — already stated as unmet; kept honest |
| Access | Signed commits | `required_signatures` false | stated as not required |
| Access | Releases only from signed tag by trusted builder | `publish.yml` has a *Verify signed release tag* job (rejects lightweight tags, verifies SSH signature against approved signers); provenance + SBOM attested | V |
| Secrets | gitleaks on every change and history | `gitleaks.yml` `fetch-depth: 0`; required check | V |
| Secrets | No long-lived PyPI token in release path | `publish.yml` uses `pypa/gh-action-pypi-publish` with `id-token: write`; no password/token reference found | V |
| Secrets | Workflow tokens default read-only | Org/repo default `read`; `ci.yml` `permissions: contents: read` | V |
| Secrets | MFA on GitHub/PyPI/hosting; quarterly verification | Not observable from the repo | **F** — rewritten as founder responsibility; no cadence claimed |
| Secrets | Rotate at least every 12 months; documented rotation procedure | No single documented procedure; only incident runbooks | **U** — rewritten as a proposal pending commitment |
| Vulnerability | SCA: pip-audit, dependency-review | Both in workflows | V |
| Vulnerability | SCA: OSV on lock files | Not in CI; run manually and recorded | **P** — rewritten to say manual |
| Vulnerability | SAST: CodeQL, Bandit | `codeql.yml`, `security-scan.yml` | V |
| Vulnerability | Release gate: no Critical/High open | Not automated | already marked "not automated" — keep |
| Vulnerability | Medium within 30 days / Low next release | No tracking mechanism or owner | **F/U** — see section 3 |
| Support | 90 days of critical fixes after next minor | No process, staffing or tooling behind it | **F** — founder must confirm the commitment is deliverable |
| Support | Python 3.11/3.12 only | CI matrix | V |
| Support | Hosted service: no commitment | Consistent with reality | V |
| `SECURITY.md` | Acknowledge ≤ 48 h, timeline ≤ 7 days | Single maintainer; no on-call; time zone unspecified | **F** — see section 3 |

## 2. Founder responsibilities (cannot be discharged by code)

1. Make CodeQL, dependency-review and the reproducible-build check **required** on `main` (branch protection).
2. Decide whether to add a required reviewer once a second human exists (see `SECOND_MAINTAINER_PROPOSAL.md`);
   until then keep the statement that independent human review is unmet.
3. Enable and verify MFA on GitHub, PyPI, the registrar and hosting; choose and own any recurring check.
4. Write or approve a key-rotation procedure for the field-encryption key and webhook secrets, then commit to a cadence.
5. Confirm you can honour the support window and the response targets below with the time you actually have.
6. Approve the wording of `SECURITY.md` once targets are decided; publish a security contact that is monitored.

## 3. Realistic vulnerability-response targets (proposal)

The current promise (48 h acknowledgement, 7 days timeline) is plausible only if someone watches the inbox
daily, including weekends. For one person, a defensible proposal:

| Stage | Proposed target | Why |
|---|---|---|
| Acknowledge a private report | **3 business days** | achievable with a daily check, no weekend duty |
| Triage / severity + timeline | **10 business days** | allows reproduction |
| Fix, Critical (exploitable, no auth, tenant breach) | **best effort within 14 days**, interim mitigation advice sooner | no team to parallelize |
| Fix, High | **30 days** | matches the SCA table |
| Fix, Medium / Low | **90 days / next release** | existing intent |
| Coordinated disclosure | **90 days** default | industry norm |

These are proposals, not promises, until the founder confirms them. Do not publish targets the founder cannot
keep; a missed published target is worse than a longer honest one.

## 4. Limitations that must stay in the text

* One maintainer ⇒ no independent human review; an AI auditor is not a substitute (OSPS-QA-07.01 stays unmet).
* No external evidence anchor and no hosted-service availability commitment.
* Release gate on open Critical/High is a checklist, not automation.
* OpenSSF: silver self-attested; **Gold not claimed**; criteria needing a second human stay "unmet".

## 5. Adoption steps (founder)

- [ ] Read the four drafts as corrected in this change.
- [ ] Complete section 2 items 1–6 (or strike the sentences they support).
- [ ] Confirm or change section 3 targets; update `SECURITY.md` to match exactly.
- [ ] Move each policy out of DRAFT by editing its status line and recording the adoption date in `MAINTAINERS.md`.
- [ ] Ask Antigravity to re-verify that every sentence still matches practice after the founder's edits.
