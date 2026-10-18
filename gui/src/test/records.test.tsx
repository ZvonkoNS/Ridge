import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RecordsSection } from "../screens/RecordsSection";
import { axeViolations, routes } from "./ipc";

const INFO = {
  case_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
  reference: "KT-2026-0001",
  retention_until: "2027-01-31",
  legal_hold: false,
  legal_basis: "synthetic",
};

describe("records", () => {
  it("exports the custody head for countersigning", async () => {
    const mocked = routes({
      list_notes: () => [],
      export_head: () => ({
        exported: "D:/out/head.json",
        seq: 41,
        head: "a".repeat(64),
        key_id: "0123456789abcdef",
      }),
    });
    const notify = vi.fn();
    const { container } = render(
      <RecordsSection
        info={INFO}
        items={[]}
        limits={{ configured: false }}
        onInfo={vi.fn()}
        onFailure={vi.fn()}
        notify={notify}
      />,
    );
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "Export custody head..." }));
    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(expect.stringContaining("entry 41"));
    });
    expect(mocked).toHaveBeenCalledWith("export_head", {});
  });
});
