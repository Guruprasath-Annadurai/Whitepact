// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT

// Browser seam only: callers must supply reviewed server-issued options. A
// credential is an authenticator response, NEVER server verification or authority.
// No endpoint, session, persistence, retry, or response serialization lives here.
export class PasskeyClientError extends Error {
  constructor(public readonly kind: "unsupported" | "cancelled-or-expired" | "unavailable", message: string) {
    super(message);
  }
}

export function passkeysSupported(): boolean {
  return window.isSecureContext && typeof window.PublicKeyCredential !== "undefined"
    && typeof navigator.credentials?.create === "function" && typeof navigator.credentials?.get === "function";
}

export async function requestPasskey(
  operation: { kind: "enroll"; options: PublicKeyCredentialCreationOptions }
    | { kind: "step-up"; options: PublicKeyCredentialRequestOptions },
  signal: AbortSignal,
): Promise<PublicKeyCredential> {
  if (!passkeysSupported()) throw new PasskeyClientError("unsupported", "Passkeys require a supported browser and a secure connection.");
  try {
    const credential = operation.kind === "enroll"
      ? await navigator.credentials.create({ publicKey: operation.options, signal })
      : await navigator.credentials.get({ publicKey: operation.options, signal });
    if (signal.aborted) throw new DOMException("Cancelled", "AbortError");
    if (!(credential instanceof PublicKeyCredential)) throw new PasskeyClientError("unavailable", "No passkey response was received. No verification is claimed.");
    return credential;
  } catch (error) {
    if (error instanceof PasskeyClientError) throw error;
    if (error instanceof DOMException && ["NotAllowedError", "AbortError"].includes(error.name)) {
      throw new PasskeyClientError("cancelled-or-expired", "The passkey prompt was cancelled or expired. No server verification is claimed.");
    }
    // Never expose authenticator diagnostics, credential material, or raw errors.
    throw new PasskeyClientError("unavailable", "The passkey response could not be obtained. No server verification is claimed.");
  }
}
