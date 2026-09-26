# Post-V1 package strategy (plan only — no split before launch)

The published `rai-governance-platform` package remains the historical MIT
compatibility surface. **No yank, rename, or destructive migration before V1.**

After V1, a gradual path may add:

- clearer SDK/client modules in the public package
- optional hosted/private enforcement behind authenticated APIs

This document does not describe privatizing code already released under MIT.
