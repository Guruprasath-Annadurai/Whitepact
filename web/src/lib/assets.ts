// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
export function publicAsset(name: string): string {
  return `${import.meta.env.BASE_URL}assets/${name}`;
}
