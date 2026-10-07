// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { StrictMode, Suspense } from "react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { HomePage } from "../src/features/marketing/HomePage";

// Build-time editorial HTML only: no server, credentials or product requests.
// Match the homepage's client tree, including its Suspense boundary.
export function renderHome() {
  return renderToString(<StrictMode><MemoryRouter initialEntries={["/"]}>
    <Suspense fallback={<div className="app-loading" role="status"><span>Loading WhitePact</span></div>}><HomePage /></Suspense>
  </MemoryRouter></StrictMode>);
}
