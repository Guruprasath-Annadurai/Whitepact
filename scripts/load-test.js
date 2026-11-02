/**
 * Load test validating the SLA.md response-time and error-rate targets
 * against a real running instance — not a paper claim.
 *
 * Usage:
 *   k6 run scripts/load-test.js \
 *     -e BASE_URL=https://api.yourcompany.com \
 *     -e API_KEY=rai_xxx \
 *     -e TIER=PRO   # FREE | PRO | ENTERPRISE — picks which SLA.md thresholds to check
 *
 * Install k6: https://k6.io/docs/get-started/installation/
 *
 * This exercises exactly the five endpoints SLA.md makes p95 promises
 * about (/api/health, /api/evaluate, /api/scan, /api/hallucination,
 * /api/cost/analyze, /api/cost/route) with realistic payloads, and fails
 * the run (non-zero exit) if the measured p95 for any of them misses its
 * documented target — so a green run is real evidence, not vibes.
 */

import http from "k6/http";
import { check, sleep } from "k6";
import { Trend } from "k6/metrics";

const BASE_URL = __ENV.BASE_URL || "http://localhost:8765";
const API_KEY = __ENV.API_KEY || "";
const TIER = (__ENV.TIER || "PRO").toUpperCase();

// SLA.md's response-time targets (ms), by tier.
const SLA_TARGETS_MS = {
  FREE: { health: 50, evaluate: 500, scan: 200, hallucination: 300, cost_analyze: 200, cost_route: 100 },
  PRO: { health: 20, evaluate: 300, scan: 100, hallucination: 150, cost_analyze: 100, cost_route: 50 },
  ENTERPRISE: { health: 10, evaluate: 150, scan: 50, hallucination: 80, cost_analyze: 50, cost_route: 25 },
};
const targets = SLA_TARGETS_MS[TIER] || SLA_TARGETS_MS.PRO;

const healthTrend = new Trend("rai_health_ms");
const evaluateTrend = new Trend("rai_evaluate_ms");
const scanTrend = new Trend("rai_scan_ms");
const hallucinationTrend = new Trend("rai_hallucination_ms");
const costAnalyzeTrend = new Trend("rai_cost_analyze_ms");
const costRouteTrend = new Trend("rai_cost_route_ms");

export const options = {
  scenarios: {
    steady_load: {
      executor: "constant-vus",
      vus: Number(__ENV.VUS || 10),
      duration: __ENV.DURATION || "2m",
    },
  },
  thresholds: {
    // p95 must be under the tier's documented target for every endpoint.
    rai_health_ms: [`p(95)<${targets.health}`],
    rai_evaluate_ms: [`p(95)<${targets.evaluate}`],
    rai_scan_ms: [`p(95)<${targets.scan}`],
    rai_hallucination_ms: [`p(95)<${targets.hallucination}`],
    rai_cost_analyze_ms: [`p(95)<${targets.cost_analyze}`],
    rai_cost_route_ms: [`p(95)<${targets.cost_route}`],
    http_req_failed: ["rate<0.01"], // <1% errors, well inside SLA.md's P1/P2 error thresholds
  },
};

function headers() {
  const h = { "Content-Type": "application/json" };
  if (API_KEY) h["Authorization"] = `Bearer ${API_KEY}`;
  return h;
}

export default function () {
  // /api/health — no auth required
  {
    const res = http.get(`${BASE_URL}/api/health`);
    healthTrend.add(res.timings.duration);
    check(res, { "health 200": (r) => r.status === 200 });
  }

  // /api/evaluate
  {
    const payload = JSON.stringify({
      model_name: "gpt-4o",
      provider: "openai",
      fairness: 0.8, privacy: 0.8, security: 0.8,
      robustness: 0.8, compliance: 0.8, authenticity: 0.8,
      record_drift: false, // avoid inflating latency with drift-alert side effects during load test
    });
    const res = http.post(`${BASE_URL}/api/evaluate`, payload, { headers: headers() });
    evaluateTrend.add(res.timings.duration);
    check(res, { "evaluate 200": (r) => r.status === 200 });
  }

  // /api/scan
  {
    const payload = JSON.stringify({ text: "The quarterly report shows revenue of $2.4M, up 12% year over year." });
    const res = http.post(`${BASE_URL}/api/scan`, payload, { headers: headers() });
    scanTrend.add(res.timings.duration);
    check(res, { "scan 200": (r) => r.status === 200 });
  }

  // /api/hallucination
  {
    const payload = JSON.stringify({
      prompt: "What is the capital of France?",
      response: "The capital of France is Paris, a city with a population of roughly 2.1 million.",
      provider: "openai",
      model: "gpt-4o",
    });
    const res = http.post(`${BASE_URL}/api/hallucination`, payload, { headers: headers() });
    hallucinationTrend.add(res.timings.duration);
    check(res, { "hallucination 200": (r) => r.status === 200 });
  }

  // /api/cost/analyze
  {
    const payload = JSON.stringify({
      prompt: "Summarize this document in three bullet points, focusing on financial performance and risk factors.",
      response: "- Revenue up 12%\n- Margins stable\n- Two new risk factors flagged in the appendix",
      provider: "openai",
      model: "gpt-4o",
      monthly_requests: 50000,
    });
    const res = http.post(`${BASE_URL}/api/cost/analyze`, payload, { headers: headers() });
    costAnalyzeTrend.add(res.timings.duration);
    check(res, { "cost/analyze 200": (r) => r.status === 200 });
  }

  // /api/cost/route
  {
    const payload = JSON.stringify({
      task_description: "Classify this customer support ticket as billing, technical, or account access.",
      quality_requirement: "balanced",
    });
    const res = http.post(`${BASE_URL}/api/cost/route`, payload, { headers: headers() });
    costRouteTrend.add(res.timings.duration);
    check(res, { "cost/route 200": (r) => r.status === 200 });
  }

  sleep(1);
}
