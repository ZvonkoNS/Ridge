import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NewCaseForm } from "../screens/NewCaseForm";
import { axeViolations } from "./ipc";

describe("new case form", () => {
  it("needs a reference, a legal basis and a retention date, and hands them over", async () => {
    const onCreate = vi.fn();
    const { container } = render(<NewCaseForm busy={false} onCreate={onCreate} />);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Create case..." }));
    expect(onCreate).not.toHaveBeenCalled(); // the browser refuses empty required fields
    await user.type(screen.getByRole("textbox", { name: "Case reference" }), "KT-2026-0009");
    await user.type(screen.getByRole("textbox", { name: "Legal basis" }), "Order 12/2026");
    await user.type(screen.getByLabelText("Keep until (retention date)"), "2031-12-31");
    await user.click(screen.getByRole("button", { name: "Create case..." }));
    expect(onCreate).toHaveBeenCalledWith({
      reference: "KT-2026-0009",
      legalBasis: "Order 12/2026",
      retention: "2031-12-31",
    });
    expect(await axeViolations(container)).toEqual([]);
  });
});
