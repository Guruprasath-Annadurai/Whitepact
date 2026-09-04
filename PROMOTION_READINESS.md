# WhitePact promotion readiness

Point-in-time assessment: 2026-09-04. Base commit:
`8f8ef53f0460c99115f5656dfa4d31775bca4d6a`.

## Status

WhitePact is ready for measured technical promotion after this launch branch is
reviewed and merged. A broad official launch remains blocked by two externally
observable MCP distribution failures:

1. the public hosted MCP endpoint timed out during this assessment;
2. the official MCP Registry's latest published record remains listing `1.2.3`,
   package `1.2.2`, and the superseded twenty-seven-tool surface.

This branch prepares source-consistent `1.2.6` registry metadata for 30 tools and
20 advertised resources. That is implemented repository evidence, not proof that
the registry has published it.

## Promotion-readiness rubric

| Category | Score | Evidence / limitation |
|---|---:|---|
| Brand clarity | 9.7 | Runtime authority leads; supporting governance features follow |
| Public README | 9.5 | First screen answers what, why, difference, trial, and trust |
| Quickstart reproducibility | 9.7 | Fresh PyPI `1.2.6` environment discovered 30/20 and called `rai_health` |
| MCP interoperability | 9.0 | Stdio verified; current hosted HTTP availability failed |
| MCP discoverability | 8.4 | Official listing exists but its latest record is stale |
| Security/trust evidence | 9.3 | Strong repository/release evidence; independent pentest still absent |
| Release verification | 9.7 | v1.2.6 artifacts, hashes, SBOM, tag, and attestations documented |
| Enterprise evaluation surface | 9.5 | One evidence-bound entry path now exists |
| Contributor experience | 8.8 | DCO/setup and real review/client/design-partner issues exist; history is early |
| Documentation consistency | 9.4 | Current 30/20 public surfaces are regression-checked; historical docs remain |
| Public claim integrity | 9.8 | Promotional claim guard added; external claims stay qualified |
| Demo quality | 9.7 | Real no-key decision and evidence summary; execution stays blocked |

**Evidence-based result: 9.3/10.** The requested 9.5 remains a target, not a
fabricated conclusion. The starting estimate supplied for this work was 7.8/10.

## Safe public claims

- WhitePact is an open-source runtime authority layer for AI agents and
  autonomous systems.
- WhitePact v1.2.6 exposes 30 MCP tools and 20 advertised resources when run
  from the published package; this was clean-room verified locally.
- Its deterministic gateway returns ALLOW, ALLOW_WITH_REDACTION,
  REQUIRE_APPROVAL, DENY, or QUARANTINE.
- Release v1.2.6 publishes a wheel, sdist, SBOM, checksums, signed-tag evidence,
  and GitHub attestations with consumer verification instructions.
- OpenSSF Best Practices Silver and OSPS Baseline Level 1 are the official
  awarded levels recorded for project 14112.

## Still unsafe to claim

- universal LLM support or provider approval where only compatibility exists;
- current hosted-MCP availability until a live check passes;
- current official-registry 30-tool publication until the new manifest is live;
- customers, enterprise deployments, partnerships, adoption, or traction;
- independent penetration testing, SOC 2, ISO, CSA, NIST, or EU AI Act
  certification;
- OpenSSF Gold or OSPS L2/L3 award;
- Brain*AI or production neural capabilities as shipped WhitePact features.

The failed scheduled Scorecard run on 2026-09-01 stopped while GitHub attempted
to pull the external Scorecard container. It is an infrastructure/workflow
execution failure, not a WhitePact vulnerability result. Existing Scorecard
hardening remains isolated in PR #79 and is not duplicated here. The official
API's current result remains **6.1**, dated 2026-08-31 for base commit `8f8ef53`.
