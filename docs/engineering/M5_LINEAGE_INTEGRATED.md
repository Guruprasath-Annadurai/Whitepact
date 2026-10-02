# M5 lineage-correct integrated RC

**Status:** `ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING`  
**PR:** #137 → `main`  
**Branch:** `cursor/whitepact-m5-lineage-integrated-f7a9`

## Ancestry (required)

```bash
git merge-base --is-ancestor 893d34a9d009560a3d9f07887c1afa3018f9e6dc HEAD
```

Record after each push:

| Field | Value |
|-------|--------|
| HEAD | *(update on push)* |
| Tree | `git rev-parse HEAD^{tree}` |
| merge-base with M2 | `893d34a…` |

## Non-freeze

Green CI on #137 is **engineering evidence only** until qualified M3 + M4 gates close.

PR **#135** is diagnostic / rewritten history — not final RC.

## M3 gate

Independent M3 engineering candidate: PR **#136** (do not mutate while exact-head CI runs).
