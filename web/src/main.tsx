// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { StrictMode } from "react";
import { createRoot, hydrateRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./fonts.css";
import "./styles.css";
import "./closure.css";
import "./corporate.css";

const root = document.getElementById("root")!;
const application = (
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
);
// Only the public home build emits a matching React snapshot. Private shells
// remain client rendered; no authenticated state is serialized into HTML.
if (root.dataset.prerendered === "home" && window.location.pathname === "/") hydrateRoot(root, application);
else createRoot(root).render(application);
