import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { NotesPanel } from "../components/NotesPanel";
import { axeViolations, routes } from "./ipc";

const JOB = "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1";
const FIRST = {
  seq: 12,
  ts_utc: "2026-10-18T08:00:00Z",
  actor: "examiner",
  text: "Region chosen to leave out the nail fold.",
  job_id: JOB,
  sha256: null,
  corrects: null,
};

describe("examiner notes", () => {
  it("adds notes and corrections without changing earlier ones", async () => {
    let seq = 12;
    const mocked = routes({
      list_notes: () => [FIRST],
      add_note: (request) => ({ ...FIRST, ...request, seq: ++seq }),
    });
    const { container } = render(<NotesPanel jobId={JOB} onFailure={vi.fn()} />);
    expect(await screen.findByText(FIRST.text)).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("list_notes", { request: { job_id: JOB, sha256: null } });
    const box = screen.getByRole("textbox", { name: "New note" });
    expect(screen.getByRole("button", { name: "Add note" })).toBeDisabled();
    await userEvent.type(box, "Ridge flow unclear near the core.");
    await userEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(await screen.findByText("Ridge flow unclear near the core.")).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("add_note", {
      request: { text: "Ridge flow unclear near the core.", job_id: JOB, sha256: null, corrects: null },
    });
    await userEvent.click(screen.getByRole("button", { name: "Correct note 12" }));
    await userEvent.type(screen.getByRole("textbox", { name: "Correction of note #12" }), "Also the crease.");
    await userEvent.click(screen.getByRole("button", { name: "Add correction" }));
    expect(await screen.findByText(/corrects #12/)).toBeInTheDocument();
    expect(screen.getByText(FIRST.text)).toBeInTheDocument(); // the original stays
    expect(await axeViolations(container)).toEqual([]);
  });

  it("keeps a photo's notes with that photo", async () => {
    const sha = "c".repeat(64);
    const mocked = routes({
      list_notes: () => [],
      add_note: (request) => ({ ...FIRST, ...request, job_id: null, seq: 30 }),
    });
    render(<NotesPanel jobId={null} sha256={sha} onFailure={vi.fn()} />);
    expect(await screen.findByRole("heading", { name: "Examiner notes on this photo" })).toBeInTheDocument();
    expect(mocked).toHaveBeenCalledWith("list_notes", { request: { job_id: null, sha256: sha } });
    await userEvent.type(screen.getByRole("textbox", { name: "New note" }), "Taken through the bag.");
    await userEvent.click(screen.getByRole("button", { name: "Add note" }));
    expect(mocked).toHaveBeenCalledWith("add_note", {
      request: { text: "Taken through the bag.", job_id: null, sha256: sha, corrects: null },
    });
  });
});
