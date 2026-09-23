# LOG-15.1 / LOG-16.1 — logging vs privacy

**Decision:** Remain **NO** for full input/output content logging. WhitePact records audit **metadata** (grant IDs, policy decisions, timestamps) per `governance/evidence.py` — not prompt/completion bodies. Satisfying content-level CAIQ wording would require product change with privacy review; not done for score.
