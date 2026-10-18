import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { RecoveryCard } from "../screens/RecoveryCard";
import { axeViolations, ipcError, routes } from "./ipc";

const INFO = {
  key_id: "0123456789abcdef",
  fingerprint: "fedcba9876543210",
  created_utc: "2026-10-18T10:00:00Z",
  file: "E:\ridge-recovery.json",
};

describe("device-secret recovery card", () => {
  it("exports and restores, showing the key and fingerprint but never a secret", async () => {
    const mocked = routes({ export_recovery: () => INFO, import_recovery: () => INFO });
    const { container } = render(<RecoveryCard />);
    expect(screen.getByText(/Backups do not hold that secret/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Export recovery file..." }));
    expect(await screen.findByText(/Recovery file for key 0123456789abcdef/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("export_recovery", {});
    await userEvent.click(screen.getByRole("button", { name: "Restore from a recovery file..." }));
    expect(await screen.findByText(/Device secret fedcba9876543210 restored/)).toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("says nothing when a dialog or prompt was cancelled, and shows a refusal", async () => {
    routes({
      export_recovery: () => ipcError("cancelled", "cancelled"),
      import_recovery: () =>
        ipcError("refused", "this account's OS keystore already holds a Ridge device secret"),
    });
    render(<RecoveryCard />);
    await userEvent.click(screen.getByRole("button", { name: "Export recovery file..." }));
    expect(screen.queryByRole("alert")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Restore from a recovery file..." }));
    expect(await screen.findByRole("alert")).toHaveTextContent("already holds a Ridge device secret");
  });
});
