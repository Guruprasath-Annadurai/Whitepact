// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { Component } from "react";
import type { ReactNode } from "react";
import { publicAsset } from "../lib/assets";

export function StaticTrustCore() { return <div className="trust-core trust-core--static" role="img" aria-label="WhitePact Trust Core: request, identity, authority, policy, risk, approval, decision and evidence"><img src={publicAsset("trust-core-head.webp")} alt="" /><div className="trust-core__stage"><span>01—08</span>Governed action lifecycle</div></div>; }

export class TrustCoreBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { /* Render a safe static asset; no user data is logged. */ }
  render() { return this.state.failed ? <StaticTrustCore /> : this.props.children; }
}
