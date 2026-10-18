import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Dialog } from "../components/Dialog";

describe("dialog", () => {
  it("keeps focus on Close when the caller re-renders with a new onClose", async () => {
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();
    const first = vi.fn();
    const { rerender, unmount } = render(
      <Dialog title="About Ridge" onClose={first}>
        <p>text</p>
      </Dialog>,
    );
    const close = screen.getByRole("button", { name: "Close" });
    expect(close).toHaveFocus();
    const second = vi.fn();
    const refocused = vi.spyOn(opener, "focus");
    rerender(
      <Dialog title="About Ridge" onClose={second}>
        <p>text</p>
      </Dialog>,
    );
    expect(refocused).not.toHaveBeenCalled(); // a re-render did not hand focus to the opener, even briefly
    expect(close).toHaveFocus();
    await userEvent.keyboard("{Escape}");
    expect(second).toHaveBeenCalledOnce(); // the latest onClose is the one used
    expect(first).not.toHaveBeenCalled();
    unmount();
    expect(opener).toHaveFocus(); // closing returns focus to where it was
    opener.remove();
  });
});
