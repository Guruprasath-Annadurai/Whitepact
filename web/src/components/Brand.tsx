// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { Link } from "react-router-dom";
import { publicAsset } from "../lib/assets";

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <Link className={`wp-brand ${compact ? "wp-brand--compact" : ""}`} to="/" aria-label="WhitePact home">
      <img src={publicAsset("whitepact-wordmark.png")} alt="WhitePact" />
    </Link>
  );
}
