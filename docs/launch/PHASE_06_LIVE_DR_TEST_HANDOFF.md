# Phase 6 — Live disaster-recovery test handoff

**A production or staging recovery drill has not been performed.**

When the owner authorizes a staging drill:

1. Record the SHA and the backup object id.
2. Take an encrypted backup of the staging database.
3. Confirm the backup object is not readable without the separate key.
4. Restore into a new database, not over the source.
5. Compare table counts and a digest of authority and evidence rows.
6. Start the app against the restored database and deny a replayed pre-backup grant if revocation state says it is spent.
7. Destroy the scratch database.
8. Write the elapsed restore time next to the proposed RTO. Do not change the public SLA from this number.

Key-loss case, tabletop only until counsel agrees: if the backup key is destroyed, the object must remain unrecoverable. Do not create a second copy of the key in git or in the object bucket.

## Gate

NOT EXECUTED.
