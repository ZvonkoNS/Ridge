import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import type { Triage, TriageRow } from "../ipc/types";
import { TriageFolder, rowDetail } from "../screens/TriageFolder";
import { axeViolations, ipcError, routes } from "./ipc";

const CHECK: NonNullable<TriageRow["check"]> = {
  schema: "ridge.capture-check/1",
  sha256: "a".repeat(64),
  width: 3024,
  height: 4032,
  finger_located: true,
  finger_share: 0.4,
  ridge_spacing_px: 9.1,
  clarity: 0.051,
  glare_share: 0,
  verdict: "ok",
  findings: [],
};
const ROWS: [TriageRow, TriageRow, TriageRow] = [
  { order: 1, file: "IMG_0003.png", bytes: 1200, group: "finger-ridges", check: CHECK, reason: "" },
  {
    order: 2,
    file: "IMG_0001.png",
    bytes: 1100,
    group: "finger-unclear",
    check: { ...CHECK, clarity: 0.006, verdict: "retake" },
    reason: "",
  },
  {
    order: 3,
    file: "IMG_0005.png",
    bytes: 12,
    group: "refused",
    check: null,
    reason: "not a supported image",
  },
];
const TRIAGE: Triage = {
  schema: "ridge.triage/1",
  ridge_version: "0.2.0",
  folder: "E:/phone-A/DCIM",
  recursive: false,
  photos: 3,
  other_files: 1,
  counts: { "finger-ridges": 1, "ridges-no-finger": 0, "finger-unclear": 1, nothing: 0, refused: 1 },
  groups: {
    "finger-ridges": "a finger was located by skin colour and its patches show a clear ridge wave",
    "ridges-no-finger": "no finger was located by skin colour, but the frame shows a clear ridge-like wave",
    "finger-unclear": "a finger was located, but its ridge pattern is unclear",
    nothing: "no finger was located and no clear ridge-like wave was measured",
    refused: "not read",
  },
  thresholds: { min_clarity: 0.02 },
  rows: ROWS,
  notice: "This is a reading order for the examiner, who still looks at every photo.",
};

describe("which photos first", () => {
  it("lists a folder's photos in reading order with the groups and the notice", async () => {
    const mocked = routes({ triage_folder: () => TRIAGE });
    const { container } = render(<TriageFolder />);
    await userEvent.click(screen.getByRole("checkbox", { name: /subfolders/ }));
    await userEvent.click(screen.getByRole("button", { name: "Check a folder of photos..." }));
    expect(
      await screen.findByText("3 photo(s) checked in E:/phone-A/DCIM, 1 other file(s) not read"),
    ).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("triage_folder", { request: { recursive: true, save_index: false } });
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(4);
    expect(rows[1]).toHaveTextContent("IMG_0003.png");
    expect(rows[1]).toHaveTextContent("clarity 0.051");
    expect(rows[3]).toHaveTextContent("not a supported image");
    expect(screen.getByText(/1: a finger was located by skin colour/)).toBeInTheDocument();
    expect(screen.queryByText(/ridges-no-finger/)).not.toBeInTheDocument(); // empty groups are not listed
    expect(screen.getByText(TRIAGE.notice)).toBeInTheDocument();
    expect(screen.queryByText(/Index saved/)).not.toBeInTheDocument();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("names the saved index with its hash", async () => {
    const index = { path: "D:/triage/phone-A-triage.csv", sha256: "b".repeat(64) };
    const mocked = routes({ triage_folder: () => ({ ...TRIAGE, recursive: true, index }) });
    render(<TriageFolder />);
    await userEvent.click(screen.getByRole("checkbox", { name: /save the index/ }));
    await userEvent.click(screen.getByRole("button", { name: "Check a folder of photos..." }));
    expect(await screen.findByText(/Index saved to D:\/triage\/phone-A-triage.csv/)).toBeInTheDocument();
    expect(screen.getByText("b".repeat(64))).toBeInTheDocument();
    expect(screen.getByText(/subfolders included/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("triage_folder", { request: { recursive: false, save_index: true } });
  });

  it("shows a refusal plainly and says nothing when the dialog is cancelled", async () => {
    routes({ triage_folder: () => ipcError("refused", "E:/phone-A holds 1200 photos; the limit is 300") });
    const { unmount } = render(<TriageFolder />);
    await userEvent.click(screen.getByRole("button", { name: "Check a folder of photos..." }));
    expect(await screen.findByRole("alert")).toHaveTextContent("holds 1200 photos; the limit is 300");
    unmount();
    routes({ triage_folder: () => ipcError("cancelled", "closed") });
    render(<TriageFolder />);
    await userEvent.click(screen.getByRole("button", { name: "Check a folder of photos..." }));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("words the measured column", () => {
    expect(rowDetail(ROWS[0])).toBe("clarity 0.051");
    expect(rowDetail({ ...ROWS[0], check: { ...CHECK, clarity: null } })).toBe("clarity not measured");
    expect(rowDetail(ROWS[2])).toBe("not a supported image");
  });
});
