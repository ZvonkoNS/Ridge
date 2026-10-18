import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { StoreScreen } from "../screens/StoreScreen";
import { axeViolations } from "./ipc";

describe("About Ridge on the store screen", () => {
  it("opens before any store is chosen", async () => {
    const { container } = render(
      <StoreScreen store={null} notice={null} versions="Ridge 0.2.0" onStore={vi.fn()} onOpened={vi.fn()} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "About Ridge" }));
    const dialog = screen.getByRole("dialog", { name: "About Ridge" });
    expect(dialog).toHaveTextContent("Ridge 0.2.0");
    expect(dialog).toHaveTextContent("encrypted in the case store you choose");
    expect(dialog).toHaveTextContent("store backups");
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
