from __future__ import annotations

import html
from pathlib import Path

from biasbuster.core.intersectional import IntersectionalReport, compute_intersectional_report
from biasbuster.core.result import ProbeResult, SuiteResult

_SEVERITY_HEX = {
    "none": "#1D9E75",
    "low": "#BA7517",
    "medium": "#D85A30",
    "high": "#E24B4A",
    "critical": "#791F1F",
}

_SEVERITY_BG = {
    "none": "#E1F5EE",
    "low": "#FAEEDA",
    "medium": "#FAECE7",
    "high": "#FCEBEB",
    "critical": "#F7C1C1",
}


def _severity_badge(severity: str) -> str:
    bg = _SEVERITY_BG.get(severity, "#eee")
    fg = _SEVERITY_HEX.get(severity, "#333")
    return (
        f'<span style="background:{bg};color:{fg};font-size:11px;font-weight:600;'
        f'padding:2px 8px;border-radius:12px;text-transform:uppercase;">'
        f"{html.escape(severity)}</span>"
    )


def _score_bar(score: float, threshold: float) -> str:
    pct = min(int(score * 100), 100)
    color = _SEVERITY_HEX.get("none", "#1D9E75")
    if score >= 0.60:
        color = _SEVERITY_HEX["critical"]
    elif score >= 0.30:
        color = _SEVERITY_HEX["high"]
    elif score >= 0.15:
        color = _SEVERITY_HEX["medium"]
    elif score >= 0.05:
        color = _SEVERITY_HEX["low"]

    threshold_pct = min(int(threshold * 100), 100)
    return f"""
    <div style="position:relative;background:#f0f0f0;border-radius:4px;height:10px;width:100%;margin:6px 0;">
      <div style="background:{color};width:{pct}%;height:10px;border-radius:4px;"></div>
      <div style="position:absolute;top:-3px;left:{threshold_pct}%;width:2px;height:16px;background:#444;"></div>
    </div>
    <div style="font-size:11px;color:#666;">score {score:.4f} &nbsp;|&nbsp; threshold {threshold:.2f}</div>
    """


def _probe_section(result: ProbeResult) -> str:
    status = "PASSED" if result.passed else "FAILED"
    status_color = "#1D9E75" if result.passed else "#E24B4A"
    ci_str = ""
    if result.confidence_interval:
        lo, hi = result.confidence_interval
        ci_str = f" &nbsp;<span style='color:#888;font-size:12px;'>95% CI [{lo:.3f}, {hi:.3f}]</span>"

    rows = ""
    for tr in result.template_results:
        pair = " vs ".join(tr.most_divergent_pair) if tr.most_divergent_pair else "—"
        rows += f"""
        <tr>
          <td style="padding:8px;font-size:12px;color:#444;max-width:340px;word-wrap:break-word;">
            {html.escape(tr.template[:120])}{"…" if len(tr.template) > 120 else ""}
          </td>
          <td style="padding:8px;text-align:center;">{_severity_badge(tr.severity)}</td>
          <td style="padding:8px;text-align:right;font-size:13px;font-family:monospace;">
            {tr.divergence_score:.4f}
          </td>
          <td style="padding:8px;font-size:12px;color:#666;">{html.escape(pair)}</td>
        </tr>"""

    responses_html = ""
    for tr in result.template_results[:3]:
        responses_html += f"""
        <details style="margin-top:8px;">
          <summary style="cursor:pointer;font-size:12px;color:#555;padding:4px 0;">
            {html.escape(tr.template[:80])}{"…" if len(tr.template) > 80 else ""}
          </summary>
          <div style="margin-top:8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:8px;">
        """
        for vr in tr.variant_responses:
            responses_html += f"""
            <div style="background:#f9f9f9;border:1px solid #e5e5e5;border-radius:6px;padding:10px;">
              <div style="font-size:11px;font-weight:600;color:#555;margin-bottom:6px;text-transform:uppercase;">
                {html.escape(vr.variant_name)}
              </div>
              <div style="font-size:12px;color:#333;line-height:1.5;">
                {html.escape(vr.response[:300])}{"…" if len(vr.response) > 300 else ""}
              </div>
            </div>"""
        responses_html += "</div></details>"

    return f"""
    <div style="background:#fff;border:1px solid #e5e5e5;border-radius:10px;
                margin-bottom:16px;overflow:hidden;">
      <div style="padding:14px 18px;border-bottom:1px solid #f0f0f0;
                  display:flex;align-items:center;gap:12px;">
        <div style="flex:1;">
          <div style="font-size:15px;font-weight:600;color:#222;">
            {html.escape(result.probe_name)}
          </div>
          <div style="font-size:12px;color:#888;margin-top:2px;">
            {html.escape(result.probe_description[:100])}
          </div>
        </div>
        <div style="text-align:right;">
          {_severity_badge(result.severity)}
          <span style="margin-left:8px;font-weight:700;color:{status_color};">{status}</span>
          {ci_str}
        </div>
      </div>
      <div style="padding:14px 18px;">
        {_score_bar(result.overall_score, result.threshold)}
        <table style="width:100%;border-collapse:collapse;margin-top:12px;">
          <thead>
            <tr style="border-bottom:2px solid #eee;">
              <th style="text-align:left;padding:8px;font-size:12px;color:#888;font-weight:500;">Template</th>
              <th style="text-align:center;padding:8px;font-size:12px;color:#888;font-weight:500;">Severity</th>
              <th style="text-align:right;padding:8px;font-size:12px;color:#888;font-weight:500;">Score</th>
              <th style="text-align:left;padding:8px;font-size:12px;color:#888;font-weight:500;">Divergent pair</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        <div style="margin-top:16px;border-top:1px solid #f0f0f0;padding-top:12px;">
          <div style="font-size:12px;font-weight:600;color:#555;margin-bottom:6px;">
            Sample responses (first 3 templates)
          </div>
          {responses_html}
        </div>
      </div>
    </div>"""


def _intersectional_section(report: IntersectionalReport) -> str:
    if not report.probe_correlations:
        return ""

    rows = ""
    for c in sorted(report.probe_correlations, key=lambda x: x.combined_risk, reverse=True):
        status_label = "Both failing" if c.both_failing else "Passing"
        status_color = "#E24B4A" if c.both_failing else "#1D9E75"
        amplified_note = (
            '<span style="font-size:10px;color:#E24B4A;">+15% amplified</span>'
            if c.both_failing
            else ""
        )
        rows += f"""
        <tr style="{'background:#FFF5F5;' if c.both_failing else ''}">
          <td style="padding:8px;font-size:13px;font-family:monospace;">
            {html.escape(c.probe_a)}&nbsp;×&nbsp;{html.escape(c.probe_b)}
          </td>
          <td style="padding:8px;text-align:right;font-size:13px;font-family:monospace;">
            {c.score_a:.4f}
          </td>
          <td style="padding:8px;text-align:right;font-size:13px;font-family:monospace;">
            {c.score_b:.4f}
          </td>
          <td style="padding:8px;text-align:right;font-size:13px;font-family:monospace;
                     font-weight:600;color:{status_color};">
            {c.combined_risk:.4f}&nbsp;{amplified_note}
          </td>
          <td style="padding:8px;font-size:12px;color:{status_color};font-weight:600;">
            {html.escape(status_label)}
          </td>
        </tr>"""

    summary = ""
    if report.co_failing_pairs:
        pairs_str = ", ".join(
            f"{a} &amp; {b}" for a, b in report.co_failing_pairs
        )
        summary = f"""
        <div style="background:#FFF5F5;border:1px solid #F7C1C1;border-radius:6px;
                    padding:10px 14px;margin-bottom:12px;font-size:13px;">
          <strong style="color:#E24B4A;">Co-failing dimensions:</strong>
          <span style="color:#555;">{pairs_str}</span>
          &nbsp;—&nbsp;<span style="color:#888;">intersecting biases compound user-facing risk.</span>
        </div>"""

    return f"""
    <div style="background:#fff;border:1px solid #e5e5e5;border-radius:10px;
                margin-bottom:16px;overflow:hidden;">
      <div style="padding:14px 18px;border-bottom:1px solid #f0f0f0;">
        <div style="font-size:15px;font-weight:600;color:#222;">Intersectional Risk Analysis</div>
        <div style="font-size:12px;color:#888;margin-top:2px;">
          Pairwise combined risk &mdash; co-failing probes apply a 1.15× amplification.
        </div>
      </div>
      <div style="padding:14px 18px;">
        {summary}
        <table style="width:100%;border-collapse:collapse;">
          <thead>
            <tr style="border-bottom:2px solid #eee;">
              <th style="text-align:left;padding:8px;font-size:12px;color:#888;font-weight:500;">Probe pair</th>
              <th style="text-align:right;padding:8px;font-size:12px;color:#888;font-weight:500;">Score A</th>
              <th style="text-align:right;padding:8px;font-size:12px;color:#888;font-weight:500;">Score B</th>
              <th style="text-align:right;padding:8px;font-size:12px;color:#888;font-weight:500;">Combined risk</th>
              <th style="text-align:left;padding:8px;font-size:12px;color:#888;font-weight:500;">Status</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
      </div>
    </div>"""


def _build_html(suite: SuiteResult) -> str:
    status = "PASSED" if suite.passed else "FAILED"
    status_color = "#1D9E75" if suite.passed else "#E24B4A"
    ts = suite.timestamp.strftime("%Y-%m-%d %H:%M UTC")

    probe_sections = "".join(_probe_section(r) for r in suite.probe_results)

    intersectional_html = ""
    if len(suite.probe_results) >= 2:
        ix_report = compute_intersectional_report(suite)
        intersectional_html = _intersectional_section(ix_report)

    chart_bars = ""
    for r in suite.probe_results:
        pct = min(int(r.overall_score * 100), 100)
        color = _SEVERITY_HEX.get(r.severity, "#888")
        chart_bars += f"""
        <div style="margin-bottom:10px;">
          <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px;">
            <span style="font-size:12px;color:#444;min-width:180px;">{html.escape(r.probe_name)}</span>
            <span style="font-size:12px;font-family:monospace;color:#666;">{r.overall_score:.4f}</span>
          </div>
          <div style="position:relative;background:#f0f0f0;border-radius:4px;height:14px;width:100%;">
            <div style="background:{color};width:{pct}%;height:14px;border-radius:4px;"></div>
            <div style="position:absolute;top:-2px;left:{min(int(r.threshold*100),100)}%;
                        width:2px;height:18px;background:#333;"></div>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>BiasBuster Report — {html.escape(suite.model_name)}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
           background: #f5f5f5; color: #222; padding: 24px; }}
    .container {{ max-width: 900px; margin: 0 auto; }}
    details summary {{ user-select: none; }}
    details summary::-webkit-details-marker {{ display: none; }}
  </style>
</head>
<body>
<div class="container">

  <div style="background:#fff;border:1px solid #e5e5e5;border-radius:10px;
              padding:20px 24px;margin-bottom:20px;">
    <div style="display:flex;align-items:flex-start;justify-content:space-between;">
      <div>
        <div style="font-size:22px;font-weight:700;color:#111;margin-bottom:4px;">
          BiasBuster Report
        </div>
        <div style="font-size:13px;color:#888;">
          {html.escape(suite.provider_name)} &nbsp;/&nbsp;
          <strong>{html.escape(suite.model_name)}</strong>
          &nbsp;&nbsp;·&nbsp;&nbsp;{ts}
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:28px;font-weight:700;color:{status_color};">{status}</div>
        <div style="font-size:13px;color:#888;">
          overall score: <strong>{suite.overall_score:.4f}</strong>
        </div>
      </div>
    </div>
    <div style="margin-top:20px;background:#f9f9f9;border-radius:8px;padding:16px;">
      <div style="font-size:12px;font-weight:600;color:#777;margin-bottom:10px;
                  text-transform:uppercase;letter-spacing:0.05em;">Score overview</div>
      {chart_bars}
      <div style="font-size:11px;color:#aaa;margin-top:6px;">
        Vertical bar = threshold. Score to the right = failing.
      </div>
    </div>
  </div>

  {probe_sections}

  {intersectional_html}

  <div style="text-align:center;font-size:11px;color:#bbb;margin-top:24px;padding-bottom:12px;">
    Generated by BiasBuster &nbsp;·&nbsp;
    <a href="https://github.com/Guruprasath-Annadurai/BiasBusters"
       style="color:#aaa;">github.com/Guruprasath-Annadurai/BiasBusters</a>
  </div>

</div>
</body>
</html>"""


class HtmlReporter:
    """
    Generates a self-contained HTML report from a SuiteResult.

    No external dependencies at runtime — the file opens in any browser
    without an internet connection.

    Usage::

        HtmlReporter().save(suite_result, Path("report.html"))
    """

    def render(self, suite: SuiteResult) -> str:
        return _build_html(suite)

    def save(self, suite: SuiteResult, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_build_html(suite), encoding="utf-8")
