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
      custody_log: () => ({ total: 0, entries: [] }),
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

  it("exports a disclosure package to a new folder", async () => {
    const mocked = routes({
      list_notes: () => [],
      custody_log: () => ({ total: 0, entries: [] }),
      export_package: () => ({
        exported: "D:/out/package",
        package_id: "6f1c2d3e-4b5a-4c6d-8e7f-0a1b2c3d4e5f",
        reports: 3,
        key_id: "0123456789abcdef",
      }),
    });
    const notify = vi.fn();
    render(
      <RecordsSection
        info={INFO}
        items={[]}
        limits={{ configured: false }}
        onInfo={vi.fn()}
        onFailure={vi.fn()}
        notify={notify}
      />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Export disclosure package..." }));
    await waitFor(() => {
      expect(notify).toHaveBeenCalledWith(expect.stringContaining("3 signed report(s)"));
    });
    expect(mocked).toHaveBeenCalledWith("export_package", {});
  });

  it("says when the case was last verified", async () => {
    routes({
      list_notes: () => [],
      custody_log: (request) =>
        request?.action === "case.verify"
          ? {
              total: 1,
              entries: [
                {
                  seq: 7,
                  ts_utc: "2026-10-18T07:00:00Z",
                  actor: "examiner",
                  action: "case.verify",
                  result: "failed",
                  problems: 2,
                },
              ],
            }
          : { total: 0, entries: [] },
    });
    render(
      <RecordsSection
        info={INFO}
        items={[]}
        limits={{ configured: false }}
        onInfo={vi.fn()}
        onFailure={vi.fn()}
        notify={vi.fn()}
      />,
    );
    expect(await screen.findByText(/Last verified/)).toHaveTextContent("FAILED with 2 problem(s)");
  });
});
