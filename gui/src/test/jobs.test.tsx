import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { JobsSection } from "../screens/JobsSection";
import { routes } from "./ipc";

const JOB = "7d444840-9dc0-41c3-a1e2-6b4ad9f0c9e1";

describe("jobs list", () => {
  it("shows how many notes each job has", async () => {
    const note = (seq: number) => ({
      seq,
      ts_utc: "2026-10-18T08:00:00Z",
      actor: "examiner",
      text: "synthetic",
      job_id: JOB,
      sha256: null,
      corrects: null,
    });
    routes({
      list_jobs: () => [
        {
          job_id: JOB,
          evidence_sha256: "e".repeat(64),
          started_utc: "2026-10-18T07:00:00Z",
          ended_utc: "2026-10-18T07:00:05Z",
          result: "ok",
          error: null,
          report_sha256: "f".repeat(64),
          key_id: "0123456789abcdef",
        },
      ],
      list_notes: () => [note(5), note(6)],
    });
    render(<JobsSection items={[]} onFailure={vi.fn()} onChanged={vi.fn()} notify={vi.fn()} />);
    expect(await screen.findByText(/2 note\(s\)/)).toBeInTheDocument();
  });
});
