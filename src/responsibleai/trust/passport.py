"""AI Passport — verifiable trust certification artifact."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from responsibleai.trust.score import TrustScore

_GRADE_COLORS: dict[str, str] = {
    "A": "#22c55e",
    "B": "#84cc16",
    "C": "#f59e0b",
    "D": "#f97316",
    "F": "#ef4444",
}


@dataclass(frozen=True)
class AIPassport:
    """
    Verifiable AI trust certificate.

    Contains a SHA-256 verification hash computed from the canonical JSON
    of the model identity and trust score at generation time. Any modification
    to the passport fields will produce a hash mismatch.
    """

    passport_id: str
    model_name: str
    provider: str
    trust_score: TrustScore
    bias_summary: dict[str, Any]
    hallucination_summary: dict[str, Any]
    security_summary: dict[str, Any]
    compliance_summary: dict[str, Any]
    privacy_summary: dict[str, Any]
    generated_at: datetime
    verification_hash: str
    version: str = "1.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "passport_id": self.passport_id,
            "version": self.version,
            "model": {"name": self.model_name, "provider": self.provider},
            "trust_score": self.trust_score.to_dict(),
            "bias_summary": self.bias_summary,
            "hallucination_summary": self.hallucination_summary,
            "security_summary": self.security_summary,
            "compliance_summary": self.compliance_summary,
            "privacy_summary": self.privacy_summary,
            "generated_at": self.generated_at.isoformat(),
            "verification_hash": self.verification_hash,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def verify(self) -> bool:
        """Recompute the hash and confirm it matches the stored value."""
        expected = _compute_hash(
            self.passport_id,
            self.model_name,
            self.provider,
            self.trust_score.overall,
            self.trust_score.grade,
            self.generated_at.isoformat(),
        )
        return expected == self.verification_hash

    def to_html(self) -> str:
        d = self.to_dict()
        ts = d["trust_score"]
        color = _GRADE_COLORS.get(ts["grade"], "#6b7280")
        dims_rows = "".join(
            f"<tr><td>{k.replace('_', ' ').title()}</td>"
            f"<td>{v:.1f} / 100</td>"
            f"<td><div class='bar'><div class='bar-fill' style='width:{v}%;background:{color}'></div></div></td></tr>"
            for k, v in ts["dimensions"].items()
        )
        bias_html = _dict_to_table(d["bias_summary"], "No bias data recorded")
        compliance_html = _dict_to_table(d["compliance_summary"], "No compliance data recorded")
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI Passport — {d['model']['name']}</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
       max-width:820px;margin:48px auto;padding:0 24px;color:#1a1a1a;background:#fff}}
  header{{border-bottom:2px solid #f3f4f6;padding-bottom:28px;margin-bottom:32px}}
  .brand{{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;
          color:#9ca3af;margin-bottom:8px}}
  h1{{font-size:24px;font-weight:800;margin-bottom:4px}}
  .sub{{color:#6b7280;font-size:13px}}
  .score-box{{display:inline-flex;align-items:center;gap:20px;
             padding:16px 24px;border-radius:12px;margin:20px 0;
             background:{color}12;border:2px solid {color}}}
  .score-num{{font-size:52px;font-weight:900;color:{color};line-height:1}}
  .score-meta{{display:flex;flex-direction:column;gap:4px}}
  .grade{{font-size:18px;font-weight:800;color:{color}}}
  .risk-badge{{display:inline-block;padding:2px 10px;border-radius:99px;
              font-size:11px;font-weight:700;background:{color}20;color:{color}}}
  table{{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}}
  th{{font-size:10px;text-transform:uppercase;letter-spacing:.06em;
      color:#9ca3af;font-weight:600;padding:6px 8px;border-bottom:1px solid #f3f4f6;
      text-align:left}}
  td{{padding:8px;border-bottom:1px solid #f9fafb}}
  .bar{{height:6px;background:#f3f4f6;border-radius:3px;width:120px}}
  .bar-fill{{height:100%;border-radius:3px}}
  h2{{font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;
      color:#374151;margin:28px 0 12px}}
  .hash{{font-family:monospace;font-size:10px;color:#9ca3af;
         word-break:break-all;background:#f9fafb;padding:10px 12px;border-radius:6px}}
  .meta{{font-size:11px;color:#9ca3af;margin-top:4px}}
</style>
</head>
<body>
<header>
  <div class="brand">ResponsibleAI — AI Passport v{d['version']}</div>
  <h1>Trust Certificate</h1>
  <p class="sub">Model: <strong>{d['model']['name']}</strong>
     &nbsp;·&nbsp; Provider: <strong>{d['model']['provider']}</strong></p>
  <div class="score-box">
    <div class="score-num">{ts['trust_score']}</div>
    <div class="score-meta">
      <span class="grade">Grade {ts['grade']}</span>
      <span class="risk-badge">{ts['risk']} RISK</span>
    </div>
  </div>
</header>

<h2>Dimension Scores</h2>
<table>
  <tr><th>Dimension</th><th>Score</th><th></th></tr>
  {dims_rows}
</table>

<h2>Bias Assessment</h2>
{bias_html}

<h2>Compliance Assessment</h2>
{compliance_html}

<h2>Verification</h2>
<p class="meta">Passport ID: {d['passport_id']}</p>
<p class="meta">Generated: {d['generated_at']}</p>
<div class="hash" style="margin-top:8px">SHA-256: {d['verification_hash']}</div>
</body>
</html>"""


def _dict_to_table(data: dict[str, Any], empty_msg: str) -> str:
    if not data:
        return f'<p style="font-size:13px;color:#9ca3af">{empty_msg}</p>'
    rows = "".join(
        f"<tr><td>{k.replace('_', ' ').title()}</td><td>{v}</td></tr>"
        for k, v in data.items()
    )
    return f"<table><tr><th>Field</th><th>Value</th></tr>{rows}</table>"


def _compute_hash(
    passport_id: str,
    model_name: str,
    provider: str,
    trust_score: float,
    grade: str,
    generated_at: str,
) -> str:
    payload = json.dumps(
        {
            "passport_id": passport_id,
            "model_name": model_name,
            "provider": provider,
            "trust_score": round(trust_score, 2),
            "grade": grade,
            "generated_at": generated_at,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class PassportGenerator:
    """Generate AI Passports from trust scores and component summaries."""

    def generate(
        self,
        model_name: str,
        provider: str,
        trust_score: TrustScore,
        bias_summary: dict[str, Any] | None = None,
        hallucination_summary: dict[str, Any] | None = None,
        security_summary: dict[str, Any] | None = None,
        compliance_summary: dict[str, Any] | None = None,
        privacy_summary: dict[str, Any] | None = None,
    ) -> AIPassport:
        """
        Generate a verifiable AI Passport.

        Parameters
        ----------
        model_name : str
            Name of the evaluated model (e.g. "gpt-4o").
        provider : str
            Provider name (e.g. "openai").
        trust_score : TrustScore
            Computed trust score from TrustScoreEngine.
        *_summary : dict | None
            Optional component-level summaries included in the passport.
            Raw data is never stored — only aggregated metadata.
        """
        now = datetime.now(timezone.utc)
        passport_id = str(uuid.uuid4())
        verification_hash = _compute_hash(
            passport_id,
            model_name,
            provider,
            trust_score.overall,
            trust_score.grade,
            now.isoformat(),
        )
        return AIPassport(
            passport_id=passport_id,
            model_name=model_name,
            provider=provider,
            trust_score=trust_score,
            bias_summary=bias_summary or {},
            hallucination_summary=hallucination_summary or {},
            security_summary=security_summary or {},
            compliance_summary=compliance_summary or {},
            privacy_summary=privacy_summary or {},
            generated_at=now,
            verification_hash=verification_hash,
        )
