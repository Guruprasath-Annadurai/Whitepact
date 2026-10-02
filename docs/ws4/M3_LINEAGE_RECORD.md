# M3 stack lineage (post–qualified M2)

| Field | SHA |
|-------|-----|
| Qualified M2 (Antigravity) | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` |
| M2 tree | `ef47788f8c6b10f5a34c178588335ce3c8e7c611` |
| M2 CI | [37022536095](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/37022536095) |
| M3 base (merge-base with M2) | record `git merge-base 893d34a HEAD` on PR #133 head |
| M3 head | record PR **#133** `headRefOid` after push |

Ancestry requirement: `git merge-base --is-ancestor 893d34a <M3-head>` must succeed.
