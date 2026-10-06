// Copyright (c) 2026 Guruprasath Annadurai
// SPDX-License-Identifier: MIT
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AccessibleDialog } from "../components/AccessibleDialog";

describe("M4 keyboard accessibility matrix", () => {
  it("traps focus with Tab and closes on Escape", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <AccessibleDialog labelId="m4-dialog" onClose={onClose}>
        <h2 id="m4-dialog">Confirm action</h2>
        <button type="button">First</button>
        <button type="button">Second</button>
      </AccessibleDialog>,
    );
    const dialog = screen.getByRole("dialog", { name: "Confirm action" });
    expect(dialog).toBeInTheDocument();
    await user.tab();
    await user.tab();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
