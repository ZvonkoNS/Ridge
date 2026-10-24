import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ImageViewer } from "../components/ImageViewer";
import { latestSet, MarkingPanel, renumber, useMarking } from "../components/MarkingPanel";
import type { Annotation } from "../ipc/types";
import { axeViolations, routes } from "./ipc";

const JOB = "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1";
const SHA = "d".repeat(64);
const SAVED: Annotation = {
  seq: 41,
  ts_utc: "2026-10-24T15:02:11Z",
  actor: "examiner",
  job_id: JOB,
  sha256: SHA,
  role: "print",
  image: { width: 400, height: 500 },
  marks: [{ n: 1, x: 10, y: 20, kind: "ending", label: null }],
  note: null,
  replaces: null,
  signed_seq: 42,
};

const onFailure = vi.fn();
const notify = vi.fn();

/** The panel with a viewer the test can click, as the review panel wires them. */
function Harness() {
  const m = useMarking(JOB, { sha256: SHA, role: "print" }, { width: 400, height: 500 }, onFailure, notify);
  return (
    <>
      <ImageViewer
        title="print output"
        url="blob:test/print"
        bitmap={{ width: 400, height: 500 }}
        source={{ width: 400, height: 500 }}
        tool={m.marking ? "mark" : "pan"}
        onMark={m.addAt}
        examinerMarks={m.examinerMarks}
        label={() => null}
      />
      <MarkingPanel m={m} />
    </>
  );
}

function click(table: HTMLElement, x: number, y: number) {
  fireEvent.pointerDown(table, { button: 0, clientX: x, clientY: y, pointerId: 1 });
  fireEvent.pointerUp(table, { button: 0, clientX: x, clientY: y, pointerId: 1 });
}

describe("marking minutiae", () => {
  it("places, labels, removes and saves marks, replacing the saved set", async () => {
    const mocked = routes({
      list_annotations: () => [SAVED],
      add_annotation: (request) => ({
        ...SAVED,
        seq: 57,
        signed_seq: 58,
        replaces: (request?.replaces as number | null) ?? null,
        marks: (request?.marks as { x: number; y: number; kind: string; label: string | null }[]).map(
          (mk, i) => ({
            ...mk,
            n: i + 1,
          }),
        ),
      }),
    });
    const { container } = render(<Harness />);
    expect(await screen.findByLabelText(/Show saved marks \(set #41, 1 marks\)/)).toBeChecked();
    expect(container.querySelectorAll(".ov-examiner").length).toBe(1); // the saved mark is drawn
    const table = screen.getByRole("application");
    table.setPointerCapture = vi.fn();
    fireEvent.keyDown(table, { key: "1" }); // 1 screen px = 1 image px; the image is centred in 800 x 600
    click(table, 400, 300); // not marking yet: nothing happens
    expect(screen.queryByLabelText("Unsaved marks")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Mark minutiae" }));
    await userEvent.click(screen.getByRole("radio", { name: "Bifurcation" }));
    await userEvent.type(screen.getByLabelText("Label for the next mark (optional)"), "delta");
    click(table, 400, 300);
    await userEvent.click(screen.getByRole("radio", { name: "Other" }));
    await userEvent.clear(screen.getByLabelText("Label for the next mark (optional)"));
    click(table, 410, 310);
    click(table, 420, 320);
    const list = await screen.findByLabelText("Unsaved marks");
    expect(list.textContent).toContain("1: Bifurcation at (200, 250) · delta");
    expect(list.textContent).toContain("3: Other at (220, 270)");
    expect(container.querySelectorAll(".ov-examiner").length).toBe(4); // one saved, three unsaved
    await userEvent.click(screen.getByRole("button", { name: "Remove mark 2" }));
    expect(screen.getByLabelText("Unsaved marks").textContent).toContain("2: Other at (220, 270)");
    await userEvent.type(screen.getByLabelText("Note on this set (optional)"), "second pass");
    await userEvent.click(screen.getByRole("button", { name: "Save 2 marks (replaces set #41)" }));
    expect(await screen.findByLabelText(/Show saved marks \(set #57, 2 marks\)/)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("add_annotation", {
      request: {
        job_id: JOB,
        sha256: SHA,
        marks: [
          { x: 200, y: 250, kind: "bifurcation", label: "delta" },
          { x: 220, y: 270, kind: "other", label: null },
        ],
        note: "second pass",
        replaces: 41,
      },
    });
    expect(screen.queryByLabelText("Unsaved marks")).toBeNull();
    expect(await axeViolations(container)).toEqual([]);
  });

  it("numbers marks in order and picks the latest current set", () => {
    const marks = renumber([
      { x: 1, y: 1, kind: "ending", label: null },
      { x: 2, y: 2, kind: "other", label: "x" },
    ]);
    expect(marks.map((m) => m.n)).toEqual([1, 2]);
    const older = { ...SAVED, seq: 30 };
    const replacing = { ...SAVED, seq: 50, replaces: 41 };
    expect(latestSet([older, SAVED, replacing], SHA)?.seq).toBe(50);
    expect(latestSet([SAVED], "e".repeat(64))).toBeNull();
  });
});
