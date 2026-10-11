# Proposal: adding a real, trusted human reviewer

Founder decision 6. **No second maintainer is invented or simulated.** AI reviews (including Antigravity's and
Claude's) do not count as a non-author human approval. **Administrator access will not be handed out to improve a
Scorecard result.** This is a proposal for a real person, to be decided and executed by the founder.

## Why it matters (and what it will not fix)
Unmet today because the project has one maintainer: required human approval before merge (OSPS-QA-07.01 /
Scorecard `Code-Review`), two-person review for risky changes, and bus-factor/continuity. A reviewer closes the
*review* gap; it does not by itself raise Scorecard `Maintained`/`Contributors` or close supply-chain gaps.

## Candidate requirements
1. **Real, verifiable identity** — the founder knows the person and has verified identity out of band; not a
   pseudonymous account or a bot.
2. **Demonstrated competence** in Python/security review, ideally via prior reviewed contributions to this repo.
3. **Conflict of interest handled in writing:** employer relationships, competing products, financial interest in
   WhitePact, or relationship to a customer under review. A reviewer with a conflict recuses from that change.
4. **Agreement to the responsibilities** below.

## Least-privilege plan
| Phase | Access | Gate to next phase |
|---|---|---|
| 1. Reviewer | GitHub *Triage* → *Write* only if they must push branches; **no** admin, no secrets, no release or PyPI rights | 6 months of reviewed activity |
| 2. Required reviewer | Added to CODEOWNERS for security-sensitive paths; branch protection requires 1 approval **from someone other than the last pusher** | founder decision |
| 3. Release co-signer | Added to the approved-signers list used by `publish.yml` *only* after separate verification of their signing key | founder decision, recorded in `MAINTAINERS.md` |

Admin, billing, registrar and hosting access are **never** granted as part of reviewer onboarding.

## Required security controls for the person
MFA on GitHub (hardware key preferred); signed commits or SSH-signed tags if they sign releases; device
encryption; no reuse of work credentials; agreement to the vulnerability-handling confidentiality terms.

## Responsibilities
Independent review (not rubber-stamping) of security-sensitive PRs; right to block a merge with a written reason;
disclose conflicts; respond within an agreed window; take part in release verification.

## Process
1. Founder identifies a person and discusses scope. 2. Written agreement (volunteer terms or contract) incl. IP/DCO
and confidentiality — **legal wording is a founder/legal task**. 3. Verify identity and MFA. 4. Grant Phase 1.
5. Record the decision in `MAINTAINERS.md`. 6. Re-evaluate at 6 months.

## Revocation and continuity
Revocation checklist: remove from the GitHub team/collaborators, remove from CODEOWNERS and the signer list, rotate
any shared credential (none should exist), review recent activity. Continuity: a named successor/trusted contact and
documented access recovery for the registrar, PyPI and hosting held by the founder; a reviewer is not a successor
unless explicitly agreed.

## Honest status of related OpenSSF criteria until this happens
| Criterion | Status |
|---|---|
| OSPS-QA-07.01 non-author human approval | **unmet** |
| Two-person review | **unmet** |
| Bus factor / contributor diversity | **unmet** |
| Branch protection: required reviews | **unmet** (count 0) |
| Gold badge | **not claimed** |
