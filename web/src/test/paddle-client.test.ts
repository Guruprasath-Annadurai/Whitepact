// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { resolvePaddleClientConfig } from "../lib/paddleClientConfig";
import {
  extractPaddleTransactionId,
  getInitializedPaddle,
  openPaddleTransactionCheckout,
  resetPaddleCheckoutClient,
} from "../lib/paddleCheckout";

const { checkoutOpen, initializePaddleMock } = vi.hoisted(() => {
  const checkoutOpen = vi.fn();
  const initializePaddleMock = vi.fn(async () => ({
    Checkout: { open: checkoutOpen },
  }));
  return { checkoutOpen, initializePaddleMock };
});

vi.mock("@paddle/paddle-js", () => ({
  initializePaddle: initializePaddleMock,
}));

describe("Paddle client configuration", () => {
  it("accepts sandbox configuration with test_ token", () => {
    const result = resolvePaddleClientConfig({
      VITE_WHITEPACT_PADDLE_ENV: "sandbox",
      VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "test_client_token",
    });
    expect(result).toEqual({ ok: true, environment: "sandbox", token: "test_client_token" });
  });

  it("accepts production configuration with live_ token", () => {
    const result = resolvePaddleClientConfig({
      VITE_WHITEPACT_PADDLE_ENV: "production",
      VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "live_client_token",
    });
    expect(result).toEqual({ ok: true, environment: "production", token: "live_client_token" });
  });

  it("fails closed when token is missing", () => {
    expect(resolvePaddleClientConfig({ VITE_WHITEPACT_PADDLE_ENV: "sandbox" }).ok).toBe(false);
  });

  it("fails closed when environment is missing or invalid", () => {
    expect(resolvePaddleClientConfig({ VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "test_x" }).ok).toBe(false);
    expect(resolvePaddleClientConfig({
      VITE_WHITEPACT_PADDLE_ENV: "staging",
      VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "test_x",
    }).ok).toBe(false);
  });

  it("rejects sandbox/live token mismatch", () => {
    expect(resolvePaddleClientConfig({
      VITE_WHITEPACT_PADDLE_ENV: "sandbox",
      VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "live_wrong",
    }).ok).toBe(false);
    expect(resolvePaddleClientConfig({
      VITE_WHITEPACT_PADDLE_ENV: "production",
      VITE_WHITEPACT_PADDLE_CLIENT_TOKEN: "test_wrong",
    }).ok).toBe(false);
  });
});

describe("Paddle checkout helpers", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_WHITEPACT_PADDLE_ENV", "sandbox");
    vi.stubEnv("VITE_WHITEPACT_PADDLE_CLIENT_TOKEN", "test_checkout");
    resetPaddleCheckoutClient();
    checkoutOpen.mockClear();
    initializePaddleMock.mockClear();
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    resetPaddleCheckoutClient();
  });

  it("extracts _ptxn from checkout URL", () => {
    expect(extractPaddleTransactionId(
      "https://sandbox-buy.paddle.com/paddle/paddlejs/v2?_ptxn=txn_01abc",
    )).toBe("txn_01abc");
  });

  it("rejects checkout URLs without _ptxn", () => {
    expect(() => extractPaddleTransactionId("https://checkout.paddle.com/sess_web")).toThrow(/transaction identifier/i);
  });

  it("initializes Paddle.js once and opens transaction checkout", async () => {
    await openPaddleTransactionCheckout("https://sandbox-buy.paddle.com/?_ptxn=txn_server_created");
    expect(initializePaddleMock).toHaveBeenCalledTimes(1);
    expect(initializePaddleMock).toHaveBeenCalledWith({
      environment: "sandbox",
      token: "test_checkout",
    });
    expect(checkoutOpen).toHaveBeenCalledWith({ transactionId: "txn_server_created" });
    expect(checkoutOpen).not.toHaveBeenCalledWith(expect.objectContaining({ items: expect.anything() }));

    await getInitializedPaddle();
    expect(initializePaddleMock).toHaveBeenCalledTimes(1);
  });
});
