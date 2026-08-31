# Hardened Site Verification — whitepact.com

External observation date: 2026-08-30. Source network: maintainer workstation. These are
public-edge observations, not an authenticated application penetration test.

| Test | Result | Date | Evidence | Tool | Limitation |
|---|---|---|---|---|---|
| HTTPS reachability | Pass | 2026-08-30 | GET to `https://whitepact.com/` succeeded | curl | One region/network |
| HTTP to HTTPS | Pass | 2026-08-30 | 301 with `Location: https://whitepact.com/` | curl | Edge behavior can change |
| `www` canonicalization | Pass | 2026-08-30 | `https://www.whitepact.com` redirects to apex | curl | Redirect only |
| Certificate | Pass | 2026-08-30 | CN/SAN `whitepact.com`; Google Trust Services WE1; 2026-08-17–2026-11-15 | OpenSSL | Renewal must be monitored |
| TLS 1.2 / 1.3 | Pass | 2026-08-31 | Both negotiated successfully; ECDHE-ECDSA-AES128-GCM-SHA256 / TLS_AES_256_GCM_SHA384 | OpenSSL `s_client` | Local OpenSSL disabled TLS 1.0/1.1, so server rejection of legacy protocols was not independently demonstrated |
| HSTS | Pass | 2026-08-30 | `max-age=31536000; includeSubDomains` | curl | Not independently checked against preload list |
| CSP | Pass with residual risk | 2026-08-30 | deny-by-default; object/frame/base/form restrictions | curl | `unsafe-inline` remains for script/style and reduces XSS protection |
| MIME sniffing | Pass | 2026-08-30 | `X-Content-Type-Options: nosniff` | curl | Header evidence only |
| Frame protection | Pass | 2026-08-30 | CSP `frame-ancestors 'none'` and `X-Frame-Options: DENY` | curl | Header evidence only |
| Referrer policy | Pass | 2026-08-30 | `strict-origin-when-cross-origin` | curl | Header evidence only |
| Permissions policy | Pass | 2026-08-30 | geolocation, microphone and camera disabled | curl | Other features use browser defaults |
| Cache policy | Pass for public root | 2026-08-30 | `Cache-Control: no-store` | curl | Authenticated/sensitive routes were not exercised |
| Cookies | No cookies observed | 2026-08-30 | no `Set-Cookie` on public root | curl | Secure/HttpOnly/SameSite on authenticated cookies not externally verified |
| Mixed content | None observed | 2026-08-30 | homepage contains no `http://`; scripts use same-origin paths | curl + text inspection | Browser/runtime-generated requests not captured |
| Server disclosure | Partial | 2026-08-30 | Cloudflare plus `x-render-origin-server: uvicorn`, Render/request identifiers | curl | Low-severity fingerprinting remains |

## Conclusion

The public edge is **DEPLOYMENT VERIFIED** for HTTPS redirect, certificate, and the listed
headers. It is not proof of application security. Authenticated cookie behavior, legacy
TLS rejection, origin bypass, CSP effectiveness, and sensitive-route caching remain
**EXTERNAL VERIFICATION REQUIRED** in an independent penetration test. The OpenSSF
BadgeApp must be updated and award the criterion before any official Gold claim.
