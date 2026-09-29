# Threat Model (summary)

Assume compromise of: employee account, admin browser session, workstation, app container, agent workload, third-party integration, CI credential, single cloud API token.

**Goal:** No single stolen credential grants all three providers or unrestricted production.

Controls: JIT grants, tier isolation, fail-closed egress, Access JWT validation, separate signing domains, backup credential separation.

See `docs/infrastructure/THREAT_MODEL.md` for infrastructure-specific items.
