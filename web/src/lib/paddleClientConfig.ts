// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

export type PaddleClientEnvironment = "sandbox" | "production";

export type PaddleClientConfig =
  | { ok: true; environment: PaddleClientEnvironment; token: string }
  | { ok: false; error: string };

/** Fail-closed Paddle.js client configuration from Vite env (browser-only, non-secret). */
export function resolvePaddleClientConfig(
  env: Record<string, string | boolean | undefined> = import.meta.env,
): PaddleClientConfig {
  const rawEnv = String(env.VITE_WHITEPACT_PADDLE_ENV ?? "").trim().toLowerCase();
  const token = String(env.VITE_WHITEPACT_PADDLE_CLIENT_TOKEN ?? "").trim();

  if (rawEnv !== "sandbox" && rawEnv !== "production") {
    return { ok: false, error: "Paddle client environment is not configured." };
  }
  if (!token) {
    return { ok: false, error: "Paddle client token is not configured." };
  }
  if (rawEnv === "sandbox" && !token.startsWith("test_")) {
    return { ok: false, error: "Paddle sandbox client token must start with test_." };
  }
  if (rawEnv === "production" && !token.startsWith("live_")) {
    return { ok: false, error: "Paddle production client token must start with live_." };
  }

  return { ok: true, environment: rawEnv, token };
}
