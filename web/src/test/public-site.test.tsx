// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen, within } from "@testing-library/react";
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
  it.each(["/", "/pricing"])("shows approved honest launch plans at %s", async (path) => {
    renderAt(path);
    const cards = document.querySelector('.launch-pricing')!;
    expect(cards).toBeInTheDocument();
    for (const price of ["$0 forever", "$0/year", "$29/month", "$290/year", "$99/month", "$990/year", "Custom annual pricing"]) expect(cards).toHaveTextContent(price);
    expect(within(cards as HTMLElement).getAllByText("Early Access")).toHaveLength(2);
    for (const link of within(cards as HTMLElement).getAllByRole("link", { name: /Early Access|Contact Sales/ })) expect(link).toHaveAttribute("href", "/contact");
    expect(cards).not.toHaveTextContent(/SSO|SCIM|SLA|certified|unlimited|Buy now|retention|%/i);
    expect(screen.getByText(/2 months free with annual billing/)).toBeInTheDocument();
  });
  it.each(["/", "/pricing", "/terms", "/privacy", "/refund-policy", "/docs", "/about", "/contact", "/trust"])("links all commerce pages from the footer at %s", async (path) => {
    renderAt(path);
    const footer = within(await screen.findByRole("navigation", { name: "Public footer" }));
    for (const [label, destination] of [["Pricing", "/pricing"], ["Terms", "/terms"], ["Privacy", "/privacy"], ["Refund Policy", "/refund-policy"]]) {
      expect(footer.getByRole("link", { name: label })).toHaveAttribute("href", destination);
    }
  });

  it.each([["/pricing", "Pricing"], ["/terms", "Terms of Service"], ["/privacy", "Privacy Policy"], ["/refund-policy", "Refund Policy"]])("renders canonical commerce content at %s", async (path, title) => {
    renderAt(path);
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent(title);
    expect(document.title).toBe(`${title} | WhitePact`);
    expect(document.querySelector('link[rel="canonical"]')).toHaveAttribute("href", `https://whitepact.com${path}`);
    expect(document.querySelector('meta[name="robots"]')).toHaveAttribute("content", "index, follow");
    expect(screen.queryByText(/repository-maintained draft|lorem ipsum|TODO|TBD/i)).not.toBeInTheDocument();
  });

  it("navigates from the homepage footer to the refund policy", async () => {
    renderAt("/");
    await userEvent.click(within(screen.getByRole("navigation", { name: "Public footer" })).getByRole("link", { name: "Refund Policy" }));
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Refund Policy");
    expect(screen.getByText(/duplicate charges, accidental duplicate purchases/i)).toBeInTheDocument();
  });
  it("labels the governance console as simulated and exposes inspectable evidence", async () => {
    const user = userEvent.setup();
    renderAt("/");
    expect(screen.getByText(/Interactive governance demo · Simulated data/i)).toBeInTheDocument();
    const trigger = screen.getByRole("button", { name: /Inspect decision/i });
    trigger.focus();
    await user.click(trigger);
    expect(screen.getByRole("dialog", { name: /Decision inspection/i })).toBeInTheDocument();
    expect(screen.getByText("Blocked before execution")).toBeInTheDocument();
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
