# M5 lineage record

| Milestone | SHA | Role |
|-----------|-----|------|
| M3 (qualified) | `620399b7973f5ed058d45218610be228e72d3ed8` | Identity/TOTP/SDK baseline |
| M4 (qualified) | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | WS-5 / enterprise hardening base |
| M5 prep | `635b8120d34f56b27065b771da911c80ff11d5c1` | Docs + test matrices (cherry-picked) |
| M5 integration | `c77bdef42bd01fc079402b56846ba8fa61810830` | Authoritative merge onto M4 |
| M5 gate tip | See `docs/ws6/M5_EXACT_HEAD_CI_EVIDENCE.md` | Engineering freeze + CI |

Literal ancestry: `git merge-base --is-ancestor 52d9b3c <m5-tip>` must hold for Antigravity M5 qualification.
