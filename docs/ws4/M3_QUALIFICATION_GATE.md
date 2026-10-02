# M3 full-CI qualification gate (lineage-correct)

**Frozen M3 engineering head (Antigravity target):** `6979a518ee7194dc539f5417384df2f776efd937`  
**Qualified M2 ancestor (literal):** `893d34a9d009560a3d9f07887c1afa3018f9e6dc`  
**Stacked PR #133** does not run full `ci.yml` (base is WS-3, not `main`).

## Gate mechanism

| Field | Value |
|-------|--------|
| Gate branch | `cursor/whitepact-m3-qualification-gate-f7a9` |
| Gate commit | **must equal** `6979a51` (no production drift; no gate-branch rewrite) |
| M3 tree (freeze) | `fccf3ada3e173a059095f29bbed83656b3267c2c` |
| Target | `main` (full CI matrix) |
| Cursor status | `M3_ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING` |

Mark **`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`** only when this exact commit is **18/18** green — not independent PASS.

**DCO note:** PR #136 may fail DCO until unsigned post-M2 commits in the PR range are signed without changing the `6979a51` object (repository policy). Engineering freeze remains `6979a51`; resolve DCO via signed replay after M2 boundary on a non-freeze branch if required.

## Lineage proof (required)

```bash
git merge-base --is-ancestor 893d34a9d009560a3d9f07887c1afa3018f9e6dc 6979a51
# must exit 0
```

## M5 / M6 policy

History-rewritten integrated branches are **engineering evidence only** unless `893d34a` is a literal ancestor. Final integrated RC must be rebuilt forward from the qualified M2 object without rewriting `893d34a`.
