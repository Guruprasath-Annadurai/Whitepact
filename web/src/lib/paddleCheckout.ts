// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

import { initializePaddle, type Paddle } from "@paddle/paddle-js";

import { resolvePaddleClientConfig } from "./paddleClientConfig";

/** Extract server-issued Paddle transaction id from checkout payment-link URL. */
export function extractPaddleTransactionId(checkoutUrl: string): string {
  let parsed: URL;
  try {
    parsed = new URL(checkoutUrl);
  } catch {
    throw new Error("Invalid Paddle checkout URL.");
  }
  const transactionId = parsed.searchParams.get("_ptxn")?.trim();
  if (!transactionId) {
    throw new Error("Paddle checkout URL did not include a transaction identifier.");
  }
  return transactionId;
}

let paddleInit: Promise<Paddle | undefined> | null = null;

/** Test hook: reset singleton initialization between Vitest cases. */
export function resetPaddleCheckoutClient(): void {
  paddleInit = null;
}

export async function getInitializedPaddle(): Promise<Paddle> {
  const config = resolvePaddleClientConfig();
  if (!config.ok) {
    throw new Error(config.error);
  }
  if (!paddleInit) {
    paddleInit = initializePaddle({
      environment: config.environment,
      token: config.token,
    });
  }
  const paddle = await paddleInit;
  if (!paddle) {
    throw new Error("Paddle.js failed to initialize.");
  }
  return paddle;
}

/** Open Paddle checkout for a backend-created transaction (no browser-side prices). */
export async function openPaddleTransactionCheckout(checkoutUrl: string): Promise<void> {
  const transactionId = extractPaddleTransactionId(checkoutUrl);
  const paddle = await getInitializedPaddle();
  paddle.Checkout.open({ transactionId });
}
