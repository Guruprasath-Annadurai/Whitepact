# M3 full-CI qualification gate (lineage-correct)

## Antigravity freeze (immutable object)

| Field | Value |
|-------|--------|
| **Freeze commit** | `6979a518ee7194dc539f5417384df2f776efd937` |
| **Freeze tree** | `fccf3ada3e173a059095f29bbed83656b3267c2c` |
| **Qualified M2 ancestor** | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` (literal) |

## CI qualification branch

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-m3-qualification-gate-f7a9` |
| PR | **#136** → `main` |
| Policy | Post-M2 DCO replay + signed ruff hygiene; **ours-merge** anchors literal `6979a51` in ancestry |

`git merge-base --is-ancestor 6979a51 <gate-head>` must succeed on the gate branch.

Record **workflow run ID on gate branch head** when **18/18** green, then mark:

**`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`**

(Not independent M3 PASS.)

## Stacked PR #133

Does not run full `ci.yml` against `main`.
