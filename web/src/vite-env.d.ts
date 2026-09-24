// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_WHITEPACT_PADDLE_CLIENT_TOKEN?: string;
  readonly VITE_WHITEPACT_PADDLE_ENV?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
