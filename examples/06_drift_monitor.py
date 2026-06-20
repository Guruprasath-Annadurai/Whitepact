"""
Example 06 — Trust Drift Monitor
Run: python examples/06_drift_monitor.py
"""

from responsibleai.drift.monitor import TrustDriftMonitor
from responsibleai.trust.score import TrustScoreEngine

engine = TrustScoreEngine()
monitor = TrustDriftMonitor(alert_threshold=5.0)

# Simulate 12 weeks of trust score evaluations for 2 models
gpt4o_scores = [82, 83, 81, 80, 79, 78, 74, 71, 68, 65, 63, 60]  # gradual degradation
claude_scores = [85, 86, 87, 86, 88, 89, 88, 90, 91, 90, 92, 93]  # steady improvement

def make_score(v: float):
    n = v / 100
    return engine.compute(
        fairness=n, privacy=n, security=n,
        robustness=n, compliance=n, authenticity=n,
    )

print("\n" + "=" * 66)
print("  TRUST DRIFT MONITOR — ResponsibleAI v0.4.0")
print("=" * 66)
print(f"\n  Simulating 12 weeks of evaluations for 2 models...\n")

alerts_gpt4o = []
for week, s in enumerate(gpt4o_scores, 1):
    alert = monitor.record("gpt-4o", "openai", make_score(s), metadata={"week": week})
    if alert:
        alerts_gpt4o.append((week, alert))

alerts_claude = []
for week, s in enumerate(claude_scores, 1):
    alert = monitor.record("claude-sonnet-4", "anthropic", make_score(s), metadata={"week": week})
    if alert:
        alerts_claude.append((week, alert))

# Trends
for model, provider in [("gpt-4o", "openai"), ("claude-sonnet-4", "anthropic")]:
    trend = monitor.trend(model, provider)
    history = monitor.history(model, provider)
    scores_display = " → ".join(f"{h['overall']:.0f}" for h in history[-6:])
    print(f"  {model} ({provider})")
    print(f"  Direction  : {trend['direction'].upper()}")
    print(f"  Current    : {trend['current_score']:.1f}  7d avg: {trend['avg_7_day']:.1f}  30d avg: {trend['avg_30_day']:.1f}")
    print(f"  Last 6 wks : {scores_display}")
    print()

# Drift alerts
all_alerts = [("gpt-4o", w, a) for w, a in alerts_gpt4o] + [("claude-sonnet-4", w, a) for w, a in alerts_claude]
if all_alerts:
    print(f"  Drift Alerts ({len(all_alerts)} total)")
    for model, week, alert in all_alerts:
        sev_icon = {"low": "ℹ", "medium": "⚠", "high": "⚠⚠", "critical": "🚨"}.get(alert.severity, "?")
        dims = ", ".join(alert.affected_dimensions) or "overall"
        print(f"  {sev_icon} Week {week:2d} [{alert.severity.upper():8s}] {model}: {alert.delta:.1f} pts  ({dims})")
else:
    print("  No drift alerts triggered.")

# All-models summary
print(f"\n  All Models Summary")
for row in monitor.all_models():
    print(f"  {row['model_name']:20s} {row['provider']:12s} Score: {row['overall']:.1f}  [{row['grade']}]")

print("\n" + "=" * 66 + "\n")
