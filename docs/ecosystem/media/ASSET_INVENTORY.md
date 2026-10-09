# Authentic media inventory

Inspected from commit `35488a68e587df2adfdb1ceaad44001faca524a4` on
2026-10-09. No new product screenshot was generated.

| File | Pixels | Bytes | Use |
|---|---|---|---|
| `web/public/assets/whitepact-mark.png` | 512×501 | 88128 | Logo mark on a black background. Usable as a logo if the form accepts a square image. CNCF asks for a non-black, transparent SVG, so this file does not satisfy that rule. |
| `web/public/assets/whitepact-wordmark.png` | 1200×388 | 89222 | Horizontal wordmark. Suitable as a wide logo. |
| `web/public/assets/whitepact-wordmark.webp` | WebP | 43072 | Same family as the PNG wordmark. Prefer the PNG when a form rejects WebP. |
| `web/public/assets/og-whitepact-phase3.png` | 1672×941 | 448345 | Social card: logo, tagline, and whitepact.com. It is not a product UI screenshot. |
| `web/public/assets/trust-core-head.webp` | WebP | 336750 | Decorative illustration of a mechanical head. Do not submit it as a screenshot of the product. |

## Missing

- An authentic screenshot of the live dashboard at https://whitepact.com after it finishes loading data
- An authentic screenshot of the qualified marketing site, which was not the page served by whitepact.com during this audit
- A Product Hunt gallery size (commonly 1270×760) captured from a real screen
- A transparent SVG logo that includes the word WhitePact
- A 240×240 or 128×128 icon exported from the mark

`docs/ecosystem/cncf/whitepact-wordmark-draft.svg` is a text stand-in for
the landscape draft. It is not the qualified brand mark and must not be
sent upstream while the star guideline is unmet.

## Confidential data

The logo files contain no customer data. Do not capture the live dashboard
if the view shows organization names, keys, or spend that you do not want
on a directory.
