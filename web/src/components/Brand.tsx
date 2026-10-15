// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { Link } from "react-router-dom";
import { publicAsset } from "../lib/assets";

export function Brand({ compact = false, optimized = false }: { compact?: boolean; optimized?: boolean }) {
  return (
    <Link className={`wp-brand ${compact ? "wp-brand--compact" : ""}`} to="/" aria-label="WhitePact home">
      {optimized ? <picture><source type="image/webp" srcSet={publicAsset("whitepact-wordmark.webp")} /><img src={publicAsset("whitepact-wordmark.png")} alt="WhitePact" width={1200} height={388} /></picture> : <img src={publicAsset("whitepact-wordmark.png")} alt="WhitePact" />}
    </Link>
  );
}
