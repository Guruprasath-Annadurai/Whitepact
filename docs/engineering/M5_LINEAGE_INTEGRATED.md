# M5 lineage-correct integrated RC

**Status:** `ENGINEERING_IN_PROGRESS — LINEAGE_CI_GREEN` (not M5 freeze)  
**PR:** #137 → `main`  
**Branch:** `cursor/whitepact-m5-lineage-integrated-f7a9`

## Ancestry (required)

```bash
git merge-base --is-ancestor 893d34a9d009560a3d9f07887c1afa3018f9e6dc HEAD
```

Record after each push:

| Field | Value |
|-------|--------|
| HEAD | `90be758e1ee52e5661354e28ed5645be265917d8` |
| Tree | `760160ba32a69db69bd710fa758a072279e13b58` |
| CI (18/18) | run `37058346231` @ `90be758` |
| merge-base with M2 | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` (ancestor OK) |
| Artifact | `/opt/cursor/artifacts/m5_lineage_integrated_pr137_90be758_ci.json` |

## Non-freeze

Green CI on #137 is **engineering evidence only** until qualified M3 + M4 gates close.

PR **#135** is diagnostic / rewritten history — not final RC.

## M3 gate

Independent M3 engineering candidate: PR **#136** (do not mutate while exact-head CI runs).
