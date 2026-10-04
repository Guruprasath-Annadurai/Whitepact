// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App from "../App";
import corporate from "../content/corporate.json";

vi.mock("../components/TrustCore", () => ({ TrustCore: () => <div /> }));
const at = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);

describe("corporate website truth and navigation", () => {
  it.each(Object.values(corporate))("renders $path with canonical metadata and shared navigation", async (page) => {
    at(page.path);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(page.heading);
    expect(document.title).toBe(page.title);
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute("href", `https://whitepact.com${page.path}`);
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    const nav = within(screen.getByRole("navigation", { name: "Primary navigation" }));
    expect(nav.getByRole("link", { name: new RegExp(`^${page.path.slice(1)}$`, "i") })).toHaveAttribute("aria-current", "page");
  });
  it("closes the mobile disclosure on Escape and restores trigger focus", async () => {
    const user = userEvent.setup();
    at("/docs");
    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("button", { name: "Close menu" })).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveFocus();
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute("aria-expanded", "false");
  });
  it("never represents denied or exceeded authority as an approval path", async () => {
    const user = userEvent.setup();
    at("/");
    await user.click(screen.getByRole("tab", { name: "Delete repository" }));
    expect(screen.getByRole("tabpanel")).toHaveTextContent("DENIED");
    expect(screen.getByRole("tabpanel")).not.toHaveTextContent("REQUIRE APPROVAL");
    await user.click(screen.getByRole("button", { name: /Inspect decision/ }));
    expect(screen.getByRole("dialog")).toHaveTextContent("NOT AVAILABLE FOR DENIED AUTHORITY");
    expect(screen.getByRole("dialog")).toHaveTextContent("Demonstration record only");
  });
  it("supports arrow-key scenario tabs and labels evidence as illustrative", async () => {
    const user = userEvent.setup();
    at("/");
    screen.getByRole("tab", { name: "Transfer funds" }).focus();
    await user.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: "Send sensitive email" })).toHaveFocus();
    expect(screen.getByRole("tab", { name: "Send sensitive email" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText(/Illustrative record only, not live evidence/)).toBeInTheDocument();
  });
  it("does not infer subscription unchanged from a cancellation URL", () => {
    at("/billing/cancelled");
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Verify your billing status");
    expect(screen.queryByText(/No subscription change was made/)).not.toBeInTheDocument();
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex, nofollow");
  });
  it("documents existing evidence interfaces and the baseline SDK limitation", () => {
    at("/docs");
    expect(document.body).toHaveTextContent("GET /api/web/evidence/EVIDENCE_ID");
    expect(document.body).not.toHaveTextContent("GET /api/governance/evidence/EVIDENCE_ID");
    expect(document.body).toHaveTextContent("authenticated browser session");
    expect(document.body).toHaveTextContent("backend does not provide");
    expect(document.body).toHaveTextContent('pip install -e ".[dashboard]"');
  });
  it("qualifies trust controls with status, scope, evidence and limitations", () => {
    at("/trust");
    const cards = document.querySelectorAll(".trust-grid article");
    expect(cards).toHaveLength(12);
    for (const card of cards) {
      expect(card).toHaveTextContent("Status:");
      expect(card).toHaveTextContent("Scope:");
      expect(card).toHaveTextContent("Limitation:");
      expect(within(card as HTMLElement).getByRole("link")).toHaveAttribute("href", expect.stringContaining("52d9b3c5497af24bb7d4a7147e33deaadc64296e"));
    }
  });
});
