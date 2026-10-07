# M4 lineage (qualified M3 base)

**Authoritative M3 freeze (do not reinterpret):**

| Field | Value |
|-------|--------|
| M3 HEAD | `620399b7973f5ed058d45218610be228e72d3ed8` |
| M3 tree | `15b7934d93ad8692f5a5e8c2225c5f69c130da00` |
| M3 status | `FULL PASS — EXACT-SHA QUALIFIED` (Antigravity) |
| M2 ancestor | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` |

**M4 successor branch:** `cursor/whitepact-m4-successor-engineering-f7a9`  
**Superseded stacks (non-authoritative):** `cursor/whitepact-ws5-m4-cloud-hardening-f7a9`, old WS-5 / PR #134 history not containing exact `620399b`.

```bash
git merge-base --is-ancestor 620399b7973f5ed058d45218610be228e72d3ed8 HEAD
git merge-base --is-ancestor 893d34a9d009560a3d9f07887c1afa3018f9e6dc HEAD
```
