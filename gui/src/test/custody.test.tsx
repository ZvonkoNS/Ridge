import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CustodyLog, entryDetails } from "../screens/CustodyLog";
import { axeViolations, routes } from "./ipc";

const entry = (seq: number, action: string, extra: Record<string, unknown> = {}) => ({
  seq,
  ts_utc: "2026-10-18T08:00:00Z",
  actor: "examiner",
  action,
  result: "ok",
  ...extra,
});

describe("custody log", () => {
  it("lists entries newest first, filters by kind and pages", async () => {
    const mocked = routes({
      custody_log: (request) => {
        if (request?.action === "examiner") {
          return { total: 1, entries: [entry(9, "examiner.note", { text: "Glare on the upper third." })] };
        }
        const offset = Number(request?.offset ?? 0);
        const all = [
          entry(3, "job.end", { result: "failed", error: "NoRidgePatternError" }),
          entry(2, "job.start"),
          entry(1, "case.create"),
        ];
        return { total: 3, entries: all.slice(offset, offset + 2) };
      },
    });
    const { container } = render(<CustodyLog onFailure={vi.fn()} />);
    const rows = await screen.findAllByRole("row");
    expect(rows).toHaveLength(3); // header and two entries
    expect(rows[1]).toHaveTextContent("job.end (failed)");
    expect(rows[1]).toHaveTextContent("error: NoRidgePatternError");
    expect(await axeViolations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: /Show older entries \(1 more\)/ }));
    expect(await screen.findByText("case.create")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Show older/ })).toBeNull();
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Show" }), "examiner");
    const table = await screen.findByRole("table");
    expect(await within(table).findByText(/Glare on the upper third/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("custody_log", {
      request: { offset: 0, limit: 100, action: "examiner" },
    });
  });

  it("summarises an entry in plain words", () => {
    expect(entryDetails(entry(1, "case.hold", { legal_hold: true, reason: "Court order" }))).toBe(
      "reason: Court order · hold placed",
    );
    expect(entryDetails(entry(2, "evidence.import", { label: "IMG_0042.jpg", source: "Exhibit 12" }))).toBe(
      "IMG_0042.jpg · source: Exhibit 12",
    );
  });
});
