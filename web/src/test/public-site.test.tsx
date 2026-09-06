// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import App from "../App";

vi.mock("../components/TrustCore", () => ({
  TrustCore: () => <div aria-label="Trust Core test visual" />,
}));

function renderAt(path: string) {
  return render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>);
}

describe("public website", () => {
  it("labels the governance console as simulated and exposes inspectable evidence", async () => {
    const user = userEvent.setup();
    renderAt("/");
    expect(screen.getByText(/Interactive governance demo · Simulated data/i)).toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: /Inspect decision/i });
    trigger.focus();
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: /Decision inspection/i })).toBeInTheDocument();
    expect(screen.getByText("BLOCKED BEFORE EXECUTION")).toBeInTheDocument();
    expect(screen.getByText(/Demonstration record only/i)).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("publishes a truthful trust center without certification overclaims", async () => {
    renderAt("/trust");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Controls, evidence");
    expect(screen.getByText(/SOC 2: not currently certified/i)).toBeInTheDocument();
    expect(screen.getByText(/ISO 27001: not currently certified/i)).toBeInTheDocument();
  });

  it("renders legal routes and updates route metadata", async () => {
    renderAt("/privacy");
    expect(await screen.findByRole("heading", { name: /Privacy Policy/i })).toBeInTheDocument();
    expect(document.title).toBe("Privacy Policy | WhitePact");
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute("href", "https://whitepact.com/privacy");
  });

  it("renders an intentional not-found page", async () => {
    renderAt("/missing-page");
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("This boundary");
    expect(screen.getByRole("link", { name: /Return home/i })).toHaveAttribute("href", "/");
  });
});
