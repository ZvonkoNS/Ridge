import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MarkingPanel, useMarking } from "../components/MarkingPanel";
import type { Annotation } from "../ipc/types";
import { routes } from "./ipc";

const JOB = "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1";
const A = "a".repeat(64);
const B = "b".repeat(64);
const onFailure = vi.fn();

/** The hook on a switchable image, with a button that places one mark (what a viewer click does). */
function Harness({ sha256 }: { sha256: string }) {
  const m = useMarking(JOB, { sha256, role: "print" }, { width: 400, height: 500 }, onFailure);
  return (
    <>
      <button
        type="button"
        onClick={() => {
          if (!m.marking) {
            m.toggle();
          }
          m.addAt({ x: 10, y: 10 });
        }}
      >
        place
      </button>
      <MarkingPanel m={m} />
    </>
  );
}

describe("a save that completes after the examiner switched images", () => {
  it("does not install the earlier image's set or clear the later image's marks", async () => {
    let finish: (a: Annotation) => void = () => undefined;
    const pending = new Promise<Annotation>((resolve) => {
      finish = resolve;
    });
    routes({
      list_annotations: () => [],
      add_annotation: () => pending,
    });
    const { rerender } = render(<Harness sha256={A} />);
    await userEvent.click(screen.getByRole("button", { name: "place" })); // turns marking on
    await userEvent.click(screen.getByRole("button", { name: "place" })); // the first placed mark on A
    await userEvent.click(screen.getByRole("button", { name: "Save 1 mark" }));
    rerender(<Harness sha256={B} />); // the examiner moves to image B while A's save is pending
    expect(screen.queryByLabelText("Unsaved marks")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "place" }));
    await userEvent.click(screen.getByRole("button", { name: "place" }));
    expect(screen.getByLabelText("Unsaved marks").textContent).toContain("1: Ending at (10, 10)");
    await act(async () => {
      finish({
        seq: 70,
        ts_utc: "2026-10-25T00:00:00Z",
        actor: "examiner",
        job_id: JOB,
        sha256: A,
        role: "print",
        image: { width: 400, height: 500 },
        marks: [{ n: 1, x: 10, y: 10, kind: "ending", label: null }],
        note: null,
        replaces: null,
        signed_seq: 71,
      });
      await Promise.resolve();
    });
    expect(screen.getByLabelText("Unsaved marks").textContent).toContain("1: Ending at (10, 10)"); // B's mark stays
    expect(screen.queryByLabelText(/Show saved marks \(set #70/)).toBeNull(); // A's set is not shown on B
    expect(onFailure).not.toHaveBeenCalled();
  });
});
