# Historical DCO exception — October 11, 2026

This record documents an owner-approved exception to the Developer
Certificate of Origin check in `.github/workflows/dco.yml`.

An exception is not a retrospective DCO sign-off. None of the four commits below
gained a `Signed-off-by` trailer. The original commit objects are
unchanged.

## Owner decision

Conditional approval granted on October 11, 2026, limited to the four
commit object names in this file. The approval does not authorize a
global production launch, a merge to `main`, deployment, package
publication, or any further exemption.

## Why the history stays

These commits represent published candidate and integration history
created during the Phase 1 and Phase 2 review cycles for FastStart and the
review candidate branch `review/whitepact-production-candidate`. Rewriting them to add
trailers would rewrite published commit history, alter tree relationships, and violate
the repository safety doctrine forbidding force-pushes or destructive history rewriting.
Qualified ancestors and review records are preserved. No rebase, amend, or force-push was
used to create this exception.

## What the workflow does

`.github/workflows/dco.yml` still runs
`git rev-list --no-merges base..head` and still requires this trailer
on every other commit:

```text
^Signed-off-by: .+ <.+@.+>$
```

Before that test, the shell matches the commit name against the approved historical
object names. There is no wildcard, no date cutoff, no bot exemption, and no exemption
by author name. A match prints that the exception is not a sign-off and continues.
Any other missing trailer still fails the check.

## Commit `c176669597c4812f0ab1ead88e4274128d9939c1`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `5e4e7feb138304fc93d1427699654d0fa8fc3fbc` |
| Tree | `ca96897694fdce480f1c209a097b2b312dba19e7` |
| Author | Techezz Infos `<Techezzinfos@gmail.com>` |
| Committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Date | 2026-10-10T23:33:28+05:30 |
| Subject | `fix(faststart): address GPT-6 independent review remediation order (P0-01 - P1-05)` |

## Commit `85a992aab4a1970a0cc25dabc09ef032f0612d15`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `c176669597c4812f0ab1ead88e4274128d9939c1` |
| Tree | `f896f893664cb05e032758c750aad3d83fe3fc4b` |
| Author | Techezz Infos `<Techezzinfos@gmail.com>` |
| Committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Date | 2026-10-11T00:01:00+05:30 |
| Subject | `fix(faststart): comprehensive remediation of findings FST-R01 through FST-R09` |

## Commit `55ab0ca7c01ef1da0f106cd76b21874203b5039e`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `0ab15a68d51f277006236c964a843b46d9559ba2` |
| Tree | `6f9940e51022782d3bd6fa4ae79220c393017f5a` |
| Author | Techezz Infos `<Techezzinfos@gmail.com>` |
| Committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Date | 2026-10-11T16:21:09+05:30 |
| Subject | `docs(review): generate master recovery and GPT-6 independent review handoff documents` |

## Commit `5dcf04238a06813a8782cc8d46e6638396e19aef`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `55ab0ca7c01ef1da0f106cd76b21874203b5039e` |
| Tree | `465792d665a2be78dda7a77bfb3fc92f138fea0a` |
| Author | Techezz Infos `<Techezzinfos@gmail.com>` |
| Committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Date | 2026-10-11T16:53:02+05:30 |
| Subject | `docs(review): record zero-cash staging architecture, full browser matrix, and GPT-6 second-round handoff` |

## Contribution authorization

Inclusion is authorized by the repository founder on October 11, 2026, preserving
published review history without destructive git rebase or force-push.
