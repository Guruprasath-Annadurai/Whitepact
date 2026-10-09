# Historical DCO exception — October 9, 2026

This record documents an owner-approved exception to the Developer
Certificate of Origin check in `.github/workflows/dco.yml`.

An exception is not a retrospective DCO sign-off. Neither commit below
gained a `Signed-off-by` trailer. The original commit objects are
unchanged.

## Owner decision

Conditional approval granted on October 9, 2026, limited to the two
commit object names in this file. The approval does not authorize a
global production launch, a merge to `main`, deployment, package
publication, or any further exemption.

## Why the history stays

Both commits are ancestors of the qualified platform commit
`c1d7803fce0787f9183e18bb38134f73a6c0f57d`. Rewriting them to add a
trailer would change that commit and every descendant, including the
published platform pin. The website parent
`9c43229fa3ce91bdc975240deaa8b0e568871325` does not contain them.
Qualified ancestors are preserved. No rebase, amend, or force-push was
used to create this exception.

## What the workflow does

`.github/workflows/dco.yml` still runs
`git rev-list --no-merges base..head` and still requires this trailer
on every other commit:

```text
^Signed-off-by: .+ <.+@.+>$
```

Before that test, the shell matches the commit name against exactly
these two full object names. There is no wildcard, no date cutoff, no
bot exemption, and no exemption by author name. A match prints that the
exception is not a sign-off and continues. Any other missing trailer
still fails the check.

## Commit `015fab741427a5a9cae5bca7adaa9729c78da9e5`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `5d317d5a03cf335ec8ca09536c2911b5762daa7c` |
| Tree | `e977ecc1810b500b76879a85181aec04462ef586` |
| Author | Cursor Agent `<cursoragent@cursor.com>` |
| Committer | Cursor Agent `<cursoragent@cursor.com>` |
| Author and committer time | 2026-10-05T07:59:57Z |
| Subject | `docs(cloud): Gate 1 pre-apply plan summary and staging plan verifier` |
| Paths | `docs/enterprise/cloud/CLOUD_DEPLOYMENT_EVIDENCE.md`, `infra/terraform/environments/staging/terraform.tfvars.example`, `scripts/cloud/staging-preapply-verify.sh` |

The message has this trailer and no `Signed-off-by` line:

```text
Co-authored-by: Guruprasath Annadurai <Guruprasathannadurai.official@gmail.com>
```

`Co-authored-by` is not a DCO sign-off. The named person is the
repository owner recorded in `.github/CODEOWNERS` (`@Guruprasath-Annadurai`).
The commit was created by the Cursor cloud agent identity in this
repository and is reachable from the qualified platform commit the
owner required to remain unmodified.

## Commit `681ce9566f0ef9b68b6fc97212cc2fb7a44135e3`

| Field | Value |
|---|---|
| Object | commit |
| Parents | `015fab741427a5a9cae5bca7adaa9729c78da9e5` |
| Tree | `5894871c1c7c853245ef6aca1439825cf2431892` |
| Author | Cursor Agent `<cursoragent@cursor.com>` |
| Committer | Cursor Agent `<cursoragent@cursor.com>` |
| Author and committer time | 2026-10-05T13:21:01Z |
| Subject | `chore(terraform/staging): fmt and ignore local plan/state artifacts` |
| Paths | `infra/terraform/environments/staging/.gitignore`, `infra/terraform/environments/staging/main.tf` |

The message has the same `Co-authored-by` trailer and no
`Signed-off-by` line. Same provenance: Cursor Agent author and
committer, owner named only as co-author, ancestor of the qualified
platform commit.

## Contribution authorization

Inclusion is authorized by three facts recorded here, not by inventing
a signature:

1. Both objects already sit in the owner's repository history and are
   ancestors of qualified platform `c1d7803fce0787f9183e18bb38134f73a6c0f57d`.
2. The only human identity on either message is the repository owner,
   as `Co-authored-by`, which does not certify the DCO.
3. On October 9, 2026 the owner conditionally approved a historical
   exception for these two object names and no others.

No separate copyright assignment was attached to the original commits.
This file does not create one. It records that the owner authorized
keeping these exact objects in the candidate instead of rewriting them.
