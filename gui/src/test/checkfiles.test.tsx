import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { CheckFiles } from "../screens/CheckFiles";
import { axeViolations, ipcError, routes } from "./ipc";

describe("check exported files", () => {
  it("shows what was verified and who signed it", async () => {
    const mocked = routes({
      check_exported: () => ({
        kind: "package",
        title: "Disclosure package",
        details: ["Case 0f8fad5b: 2 report(s)", "Key 0123456789abcdef registered to Examiner A"],
        key_id: "0123456789abcdef",
        holder: "Examiner A",
      }),
    });
    const { container } = render(<CheckFiles />);
    await userEvent.click(screen.getByRole("checkbox", { name: /key register/ }));
    await userEvent.click(screen.getByRole("button", { name: "Check a package folder..." }));
    expect(await screen.findByText("Disclosure package: verified.")).toBeInTheDocument();
    expect(screen.getByText(/registered to Examiner A/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("check_exported", { request: { folder: true, with_register: true } });
    expect(await axeViolations(container)).toEqual([]);
  });

  it("says plainly when a file does not verify", async () => {
    routes({ check_exported: () => ipcError("refused", "the signature does not verify") });
    render(<CheckFiles />);
    await userEvent.click(screen.getByRole("button", { name: "Check a file..." }));
    expect(await screen.findByText(/Not verified: the signature does not verify/)).toBeInTheDocument();
  });
});
