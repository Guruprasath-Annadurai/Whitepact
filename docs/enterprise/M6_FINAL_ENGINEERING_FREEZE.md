# M6 final engineering freeze

**Status:** `M6_ENGINEERING_COMPLETE — READY_FOR_FINAL_ANTIGRAVITY_QUALIFICATION`

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-m6-final-engineering-rc-f7a9` |
| Gate tip SHA | `ac9866b2e4371b99498fcd86fd25a815f1242f80` |
| Frozen engineering SHA | `efd274ded595f8e60e383f1c39bb2fff36f922e6` |
| Qualified M5 ancestor | `46685fad1ad49cfde36341ea1fad146ce1d2e714` |
| CI (engineering) | `37228344452` (**18/18**) |
| CI (gate tip) | `37231118434` (**18/18**) |
| Evidence | `docs/enterprise/M6_EXACT_HEAD_CI_EVIDENCE.md` |

Antigravity may qualify either gate tip or frozen engineering SHA; both share the same product code.

## Local gate

`scripts/release/m6_full_regression_gate.sh`

## Production actions not taken

No merge to `main`, no PyPI/npm publish, no `terraform apply`, no DNS mutation, no production billing activation.
