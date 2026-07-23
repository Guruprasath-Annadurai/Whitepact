"""Embeddable SVG trust badges for a Trust Passport.

The free/paid split this supports (see `STRATEGY_ROADMAP.md` Part 0, Item 3):
- Anyone can self-assess for free (`POST /api/trust-index/assess`) and embed
  the resulting badge immediately — it renders "Self-Assessed", never
  "Certified", so the badge itself is honest about which claim it's making.
- Only a human-reviewed certification (`POST /api/trust-index/certify/{id}`,
  super-admin only, no automated path) flips the badge to "Certified by
  ResponsibleAI" — that's the paid-verification product; the badge mechanism
  here is the same for both, only the underlying `certified` flag differs.

Shields.io-style two-segment badge, generated as plain SVG text — no
external badge-service dependency, no network call, deterministic output
for a given input (cacheable by any CDN in front of this endpoint).
"""

from __future__ import annotations

_GRADE_COLORS: dict[str, str] = {
    "A": "#16a34a",  # green
    "B": "#2563eb",  # blue
    "C": "#d97706",  # amber
    "D": "#dc2626",  # red
    "F": "#dc2626",  # red
}

_CHAR_WIDTH_PX = 6.5  # approximate average glyph width at the badge's font size
_PADDING_PX = 10


def _segment_width(text: str) -> int:
    return int(len(text) * _CHAR_WIDTH_PX) + _PADDING_PX * 2


def render_badge_svg(*, grade: str, overall_score: float, certified: bool) -> str:
    """Render a two-segment SVG badge: 'ResponsibleAI' | 'B · 83.7 (Certified)'.

    Deterministic and dependency-free — safe to call on every request
    without caching, though a reverse proxy/CDN can cache the response
    since it's a pure function of its inputs.
    """
    grade_letter = (grade or "F")[:1].upper()
    color = _GRADE_COLORS.get(grade_letter, "#6b7280")
    status = "Certified" if certified else "Self-Assessed"
    right_text = f"{grade_letter} · {overall_score:.1f} ({status})"

    left_label = "ResponsibleAI"
    left_w = _segment_width(left_label)
    right_w = _segment_width(right_text)
    total_w = left_w + right_w

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="20" role="img" aria-label="{left_label}: {right_text}">
  <linearGradient id="s" x2="0" y2="100%">
    <stop offset="0" stop-color="#bbb" stop-opacity=".1"/>
    <stop offset="1" stop-opacity=".1"/>
  </linearGradient>
  <clipPath id="r">
    <rect width="{total_w}" height="20" rx="3" fill="#fff"/>
  </clipPath>
  <g clip-path="url(#r)">
    <rect width="{left_w}" height="20" fill="#555"/>
    <rect x="{left_w}" width="{right_w}" height="20" fill="{color}"/>
    <rect width="{total_w}" height="20" fill="url(#s)"/>
  </g>
  <g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
    <text x="{left_w / 2}" y="14">{left_label}</text>
    <text x="{left_w + right_w / 2}" y="14">{right_text}</text>
  </g>
</svg>"""
