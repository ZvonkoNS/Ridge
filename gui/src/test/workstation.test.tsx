import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { WorkstationCheck } from "../screens/WorkstationCheck";
import { axeViolations, ipcError, routes } from "./ipc";

describe("workstation check", () => {
  it("lists every finding with its level in words and counts the problems", async () => {
    const mocked = routes({
      workstation_check: () => [
        { topic: "Ridge", level: "ok", text: "Ridge 0.4.0, commit abc (build)" },
        { topic: "Limits of use", level: "note", text: "VR-2027-01, not signed" },
        { topic: "OS keystore", level: "problem", text: "no Ridge device secret" },
      ],
    });
    const { container } = render(<WorkstationCheck />);
    await userEvent.click(screen.getByRole("button", { name: "Check this workstation" }));
    expect(await screen.findByText(/1 problem\(s\) to fix before casework/)).toBeInTheDocument();
    const items = screen.getAllByRole("listitem");
    expect(items.map((li) => li.textContent)).toEqual([
      "OK Ridge: Ridge 0.4.0, commit abc (build)",
      "Note Limits of use: VR-2027-01, not signed",
      "Problem OS keystore: no Ridge device secret",
    ]);
    expect(screen.getByText(/does not validate the method/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("workstation_check", { request: { with_register: false } });
    expect(await axeViolations(container)).toEqual([]);
  });

  it("asks for the key register when chosen, and a closed dialog changes nothing", async () => {
    const mocked = routes({ workstation_check: () => ipcError("cancelled", "no file was chosen") });
    render(<WorkstationCheck />);
    await userEvent.click(screen.getByRole("checkbox", { name: /key register/ }));
    await userEvent.click(screen.getByRole("button", { name: "Check this workstation" }));
    expect(mocked).toHaveBeenCalledWith("workstation_check", { request: { with_register: true } });
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("says when the check itself failed", async () => {
    routes({
      workstation_check: () => ipcError("no_store", "choose a case store first"),
    });
    render(<WorkstationCheck />);
    await userEvent.click(screen.getByRole("button", { name: "Check this workstation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("choose a case store first");
  });
});
