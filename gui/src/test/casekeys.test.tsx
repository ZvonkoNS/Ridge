import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { JobReport } from "../ipc/types";
import { CaseScreen } from "../screens/CaseScreen";
import { JobCompare, differences } from "../screens/JobCompare";
import { axeViolations, routes } from "./ipc";

const SESSION = {
  case_id: "0f8fad5b-d9cb-469f-a165-70867728950e",
  reference: "KT-2026-0001",
  retention_until: "2099-01-31",
  legal_hold: false,
};

function caseRoutes(retention: string, hold = false) {
  return routes({
    list_items: () => [],
    list_jobs: () => [],
    list_notes: () => [],
    case_info: () => ({ ...SESSION, retention_until: retention, legal_hold: hold, legal_basis: "synthetic" }),
    limits_of_use: () => ({ configured: false }),
    session_status: () => ({ unlocked: true, idle_timeout_s: 900 }),
  });
}

describe("case keyboard shortcuts", () => {
  it("switches sections with Alt+digit and lists the shortcuts with ?", async () => {
    caseRoutes("2099-01-31");
    const { container } = render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={vi.fn()} />);
    const user = userEvent.setup();
    await user.keyboard("{Alt>}2{/Alt}");
    expect(screen.getByRole("button", { name: /Jobs/ })).toHaveAttribute("aria-current", "page");
    const opener = screen.getByRole("button", { name: /Keyboard shortcuts/ });
    opener.focus();
    await user.keyboard("?");
    const dialog = screen.getByRole("dialog", { name: "Keyboard shortcuts" });
    expect(dialog).toHaveTextContent("Fit the image");
    expect(screen.getByRole("button", { name: "Close" })).toHaveFocus();
    expect(await axeViolations(container)).toEqual([]);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(opener).toHaveFocus(); // focus returns to where it was
  });

  it("says what Ridge is and is not in About Ridge", async () => {
    caseRoutes("2099-01-31");
    const { container } = render(
      <CaseScreen
        session={SESSION}
        storePath="C:/cases"
        versions="Ridge 0.4.0 (abc1234)"
        onClosed={vi.fn()}
      />,
    );
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "About Ridge" }));
    const dialog = screen.getByRole("dialog", { name: "About Ridge" });
    expect(dialog).toHaveTextContent("Ridge 0.4.0 (abc1234)");
    expect(dialog).toHaveTextContent("does not identify anyone");
    expect(dialog).toHaveTextContent("C:/cases");
    expect(dialog).toHaveTextContent("ridge-case check FILE");
    expect(await axeViolations(container)).toEqual([]);
    await user.keyboard("{Alt>}2{/Alt}"); // section keys are off while a dialog is open
    expect(screen.getByRole("button", { name: /Evidence/ })).toHaveAttribute("aria-current", "page");
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("ignores shortcuts while the examiner types", async () => {
    caseRoutes("2099-01-31");
    render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={vi.fn()} />);
    const field = document.createElement("input");
    document.body.append(field);
    field.focus();
    await userEvent.keyboard("?");
    expect(screen.queryByRole("dialog")).toBeNull();
    field.remove();
  });
});

describe("retention", () => {
  it("says when the retention date has passed, unless the case is on hold", async () => {
    caseRoutes("2020-01-01");
    const { unmount } = render(<CaseScreen session={SESSION} storePath="C:/cases" onClosed={vi.fn()} />);
    expect(await screen.findByText(/The retention date \(2020-01-01\) has passed/)).toBeInTheDocument();
    unmount();
    caseRoutes("2020-01-01", true);
    render(<CaseScreen session={{ ...SESSION, legal_hold: true }} storePath="C:/cases" onClosed={vi.fn()} />);
    await screen.findByText("2020-01-01");
    expect(screen.queryByText(/has passed/)).toBeNull();
  });
});

describe("job comparison", () => {
  const base = {
    schema: "ridge.job-report/1",
    job_id: "a",
    case_id: "c",
    case_reference: "KT",
    created_utc: "2026-10-18T08:00:00Z",
    ridge: { version: "0.4.0", python: "3.12", platform: "Windows", machine: "AMD64", dependencies: {} },
    input: { sha256: "e".repeat(64), label: "finger.png" },
    parameters: { period: null, min_quality: 0.2, flip: false },
    measurements: null,
    export: null,
    quality: null,
  } as unknown as JobReport;

  it("lists only the settings that differ", () => {
    const other = {
      ...base,
      job_id: "b",
      parameters: { period: 9, min_quality: 0.2, flip: false, ppi: 500 },
    };
    const { rows, same } = differences(base, other);
    expect(rows).toEqual([
      { name: "period", here: "none", there: "9" },
      { name: "ppi", here: "none", there: "500" },
    ]);
    expect(same).toBe(5);
    expect(differences(base, base).rows).toEqual([]);
  });

  it("reads the other job's verified report and shows the differences", async () => {
    const other = {
      ...base,
      job_id: "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1",
      parameters: { ...base.parameters, flip: true },
    };
    const mocked = routes({
      get_report: () => ({ job_id: other.job_id, key_id: "k", verified: true, report: other }),
    });
    const job = (id: string) => ({
      job_id: id,
      started_utc: "2026-10-18T08:00:00Z",
      ended_utc: "2026-10-18T08:00:05Z",
      result: "ok" as const,
      evidence_sha256: "e".repeat(64),
      report_sha256: "f".repeat(64),
      key_id: "0123456789abcdef",
      error: null,
    });
    const { container } = render(
      <JobCompare report={base} jobs={[job("a"), job(other.job_id)]} onFailure={vi.fn()} />,
    );
    await userEvent.selectOptions(
      screen.getByRole("combobox", { name: "Compare settings with" }),
      other.job_id,
    );
    const table = await screen.findByRole("table");
    expect(table).toHaveTextContent("flip");
    expect(table).toHaveTextContent("Comparing settings does not rank the outputs");
    expect(mocked).toHaveBeenCalledWith("get_report", { request: { job_id: other.job_id } });
    expect(await axeViolations(container)).toEqual([]);
  });
});
