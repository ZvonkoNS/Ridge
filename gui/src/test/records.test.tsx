import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { RecordsSection } from "../screens/RecordsSection";
import { axeViolations, routes } from "./ipc";

const STATUS = {
  case_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
  reference: "KT-2026-0001",
  retention_until: "2027-01-31",
  legal_hold: false,
  retention_reached: false,
  items: { evidence: 2, print: 1 },
  jobs: { ok: 1 },
  signed_reports: 1,
  notes: 3,
  entries: 17,
  last_verified: null,
  last_verify_result: null,
  last_head_export: null,
};

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
      case_status: () => STATUS,
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
      case_status: () => STATUS,
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
      case_status: () => STATUS,
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

  it("summarises the case", async () => {
    routes({
      list_notes: () => [],
      custody_log: () => ({ total: 0, entries: [] }),
      case_status: () => STATUS,
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
    expect(await screen.findByText("2 evidence photo(s), 1 processed print(s)")).toBeInTheDocument();
    expect(screen.getByText("1 ok; 1 signed report(s)")).toBeInTheDocument();
  });

  it("reloads the summary and the log after an action that changes the custody log", async () => {
    const status = vi.fn(() => STATUS);
    const log = vi.fn(() => ({ total: 0, entries: [] }));
    routes({
      list_notes: () => [],
      case_status: status,
      custody_log: log,
      export_head: () => ({
        exported: "D:/h.json",
        seq: 41,
        head: "a".repeat(64),
        key_id: "0123456789abcdef",
      }),
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
    await screen.findByText("2 evidence photo(s), 1 processed print(s)");
    const before = status.mock.calls.length;
    await userEvent.click(screen.getByRole("button", { name: "Export custody head..." }));
    await waitFor(() => {
      expect(status.mock.calls.length).toBeGreaterThan(before);
    });
    expect(log.mock.calls.length).toBeGreaterThan(2); // the log view and the last-verified line reloaded
  });
});
