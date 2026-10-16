# Real customer golden journey

**BLOCKED; no milestone completion.** The same fresh account, browser context, organization and PostgreSQL database are used for the supported prefix.

| Stage | Evidence / disposition |
| --- | --- |
| Fresh PostgreSQL migration | Actual migration to head; disposable database cleanup |
| Signup / local mail / verification | Real browser HTTP, actual authenticated local mail receiver, no development token response |
| Login / organization / owner session | Actual cookies, CSRF, server-confirmed membership |
| Recorded authority read | Existing tenant-scoped GET; fresh customer has no root/consent |
| WebAuthn challenge / generated registration | Actual server challenge and Chromium virtual-authenticator response on Argon code; emulator limitations apply |
| Server registration | BLOCKED403 `AUTHENTICATION_ASSURANCE_TOO_LOW`; existing password session cannot consume the TOTP-level ADD_PASSKEY grant |
| Browser assertion / server assertion verification | NOT EXECUTED after registration refusal |
| Consent / root / application / agent / delegation | NOT EXECUTED in the privileged chain |
| Policy / approval / controlled execution / evidence | NOT EXECUTED as authorized action lineage |
| Authority revocation / post-revocation denial | NOT EXECUTED; session logout is not authority revocation |

The source policy requires TOTP assurance for ADD_PASSKEY. The inspected public identity routes expose TOTP enrollment/confirmation but no demonstrated password-to-TOTP session elevation. No assurance is rewritten, fake passkey inserted or security precondition bypassed. Security owner must supply a supported independently qualified first-factor enrollment/step-up contract. Existing I2 normal-session reads/rename evidence is historical and not a replacement for this chain.

Clean-source JSON receipts: product223c74e4 has10confirmed/1blocked at RP/origin; Argon test-only review childce41f204 with unchanged e6af2f8 implementation has13confirmed/1blocked at registration assurance. Fresh account, organization, database and browser context remain the same within each run. The supported passkey-list read returns200/zero credentials after refusal; actual logout200 completes safe cleanup. No server registration or signed assertion verification is claimed.
