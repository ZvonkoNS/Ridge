import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ANNOTATIONS_NOTE, AnnotationsPanel, setLine } from "../components/AnnotationsPanel";
import type { Annotation } from "../ipc/types";
import { axeViolations, ipcError, routes } from "./ipc";

const JOB = "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1";
const SHA = "b".repeat(64);
const FIRST: Annotation = {
  seq: 41,
  ts_utc: "2026-10-24T15:02:11Z",
  actor: "examiner",
  job_id: JOB,
  sha256: SHA,
  role: "print",
  image: { width: 1180, height: 1500 },
  marks: [
    { n: 1, x: 410, y: 620, kind: "ending", label: "left of the core" },
    { n: 2, x: 532, y: 701, kind: "bifurcation", label: null },
    { n: 3, x: 600, y: 480, kind: "ending", label: null },
  ],
  note: "First pass.",
  replaces: null,
  signed_seq: 42,
};
const SECOND: Annotation = {
  ...FIRST,
  seq: 57,
  marks: FIRST.marks.slice(0, 1),
  note: null,
  replaces: 41,
  signed_seq: 58,
};

describe("examiner annotations", () => {
  it("lists the sets of a job, marks replaced ones and saves an annotated image", async () => {
    const notify = vi.fn();
    const mocked = routes({
      list_annotations: () => [FIRST, SECOND],
      export_annotated: (request) => ({
        exported: "a.png",
        sha256: "c".repeat(64),
        seq: request?.seq,
        marks: 3,
      }),
    });
    const { container } = render(<AnnotationsPanel jobId={JOB} onFailure={vi.fn()} notify={notify} />);
    expect(await screen.findByText("First pass.")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("list_annotations", { request: { job_id: JOB, sha256: null } });
    expect(screen.getByText(ANNOTATIONS_NOTE)).toBeInTheDocument();
    expect(
      screen.getByText(/3 marks \(2 endings, 1 bifurcation\) on the print image · signed by entry #42/),
    ).toBeInTheDocument();
    expect(screen.getByText(/replaced by a later set/)).toBeInTheDocument();
    expect(
      screen.getByText(/1 marks \(1 ending\) on the print image · replaces #41 · signed by entry #58/),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Save annotated image of set 41" }));
    expect(mocked).toHaveBeenCalledWith("export_annotated", {
      request: { seq: 41, suggested_name: `annotated-${SHA.slice(0, 12)}-set-41.png` },
    });
    expect(notify).toHaveBeenCalledWith(expect.stringContaining("3 marks"));
    expect(await axeViolations(container)).toEqual([]);
  });

  it("shows the empty state and stays quiet when the save dialog is cancelled", async () => {
    const onFailure = vi.fn();
    routes({
      list_annotations: () => [FIRST],
      export_annotated: () => ipcError("cancelled", "closed"),
    });
    render(<AnnotationsPanel jobId={JOB} onFailure={onFailure} />);
    await userEvent.click(await screen.findByRole("button", { name: "Save annotated image of set 41" }));
    expect(onFailure).not.toHaveBeenCalled();
    routes({ list_annotations: () => [] });
    render(<AnnotationsPanel jobId={JOB} onFailure={onFailure} />);
    expect(await screen.findByText("No marks recorded on this job's images yet.")).toBeInTheDocument();
  });

  it("words a set line", () => {
    expect(setLine({ ...FIRST, signed_seq: null })).toBe(
      "3 marks (2 endings, 1 bifurcation) on the print image · not yet signed",
    );
  });
});
