// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import commerce from "../../content/commerce.json";

export function PricingCards() {
  return <div className="launch-pricing" aria-label="Launch plans">{commerce.pricing.plans.map(plan => <article key={plan.name}>
    <h3>{plan.name}</h3><span className="plan-status">{plan.status}</span>
    <strong>{plan.monthly}</strong><p>{plan.annual}</p><p>{plan.copy}</p>
    <a className="wp-button wp-button--secondary" href={plan.href}>{plan.cta}</a>
  </article>)}</div>;
}
