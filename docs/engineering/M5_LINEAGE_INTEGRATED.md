# M5 lineage-correct integrated RC

**Status:** `IN_PROGRESS` — not frozen until exact-head **18/18** green.

## Ancestry requirements

1. `893d34a9d009560a3d9f07887c1afa3018f9e6dc` must be a **literal** ancestor (`git merge-base --is-ancestor`).
2. M3 freeze target remains `6979a51` until Antigravity qualifies M3 independently.
3. Post-M2 commits may be rewritten for DCO only; **do not** rewrite `893d34a`.

## Branch

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-m5-lineage-integrated-f7a9` |
| Base | `6979a51` (includes literal `893d34a`) |
| PR | Open after first green CI push |

## Non-candidates

- PR **#135** (`cursor/whitepact-m5-integrated-rc-f7a9`) after `filter-branch` — engineering evidence only.
