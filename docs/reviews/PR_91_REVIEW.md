# PR #91 review — docs: sharpen WhitePact GitHub discovery positioning

**Verdict: APPROVE_WITH_CHANGES**

## What works

- Leads with runtime authority instead of a capability catalog.
- Correctly points design partners to issue #87 (black-box, no source access).
- Does not claim certifications or enterprise scale.

## Required changes before merge

1. **Transitional licensing language** — Add one sentence under the hero:  
   *"Core components in this repository are MIT-licensed and historically open source; future hosted enforcement may evolve under a hybrid model without retroactive removal of published code."*  
   Avoid implying the entire future product remains "open-source runtime authority" if hybrid is the direction.

2. **Tool count** — Do not hard-code `30` in new bullets; reference `GET /health` or `mcp/metadata.py` public count (30 public / 31 registered).

3. **Trim marketing tone** — Replace "Why developers are watching" with neutral "Why teams evaluate" unless backed by public metrics.

4. **Preserve accuracy** — Keep the ASCII architecture diagram; PR removes only the long tagline (good).

5. **Ecosystem claims** — "Externally discoverable" is fine; do not imply production SLA or enterprise adoption.

## Do not merge automatically

Product-manager review still required per PR body.
